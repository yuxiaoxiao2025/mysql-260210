# -*- coding: utf-8 -*-
"""
SchemaCache 三层缓存架构
内存缓存 -> 文件缓存 -> 数据库查询
"""
from collections import OrderedDict
import json
import os
import logging

class SchemaCache:
    class LRUCache:
        """LRU 缓存实现"""
        def __init__(self, capacity: int):
            self.capacity = capacity
            self.cache = OrderedDict()
        
        def get(self, key: str):
            if key in self.cache:
                # 将访问的键移到末尾（最近使用）
                self.cache.move_to_end(key)
                return self.cache[key]
            return None
        
        def put(self, key: str, value):
            if key in self.cache:
                # 如果键已存在，移动到末尾并更新值
                self.cache.move_to_end(key)
            elif len(self.cache) >= self.capacity:
                # 如果达到容量上限，删除最久未使用的项
                self.cache.popitem(last=False)
            self.cache[key] = value
        
        def clear(self):
            self.cache.clear()

    def __init__(self, db_manager, cache_file="schema_cache.json", memory_capacity=100):
        self.db_manager = db_manager
        self.cache_file = cache_file
        self.memory_cache = self.LRUCache(memory_capacity)
        # 加载文件缓存到内存中
        self._load_file_cache()
    
    def _load_file_cache(self):
        """从文件加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for table_name, table_info in data.items():
                        self.memory_cache.put(table_name, table_info)
            except Exception as e:
                logging.warning(f"加载缓存文件失败: {e}")
    
    def _save_file_cache(self):
        """保存缓存到文件"""
        try:
            # 获取内存中的所有缓存数据
            cache_data = dict(self.memory_cache.cache)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存缓存文件失败: {e}")
    
    def get_table_info(self, table_name: str):
        """获取表信息，按三层缓存顺序：内存 -> 文件 -> 数据库"""
        # 1. 先从内存缓存获取
        table_info = self.memory_cache.get(table_name)
        if table_info is not None:
            return table_info
        
        # 2. 内存中没有，从数据库获取
        columns = self.db_manager.get_table_schema(table_name)
        table_info = {
            "table_name": table_name,
            "columns": columns
        }
        
        # 3. 存入内存缓存
        self.memory_cache.put(table_name, table_info)
        
        # 4. 保存到文件缓存
        self._save_file_cache()
        
        return table_info
    
    def warm_up(self, force=False):
        """预热缓存，加载所有表结构"""
        if force or len(self.memory_cache.cache) == 0:
            tables = self.db_manager.get_all_tables()
            for table in tables:
                # 通过调用get_table_info来填充缓存
                self.get_table_info(table)

    def search_tables(self, keyword, limit=10):
        """基于关键词搜索表名和列名

        Args:
            keyword (str): 搜索关键词
            limit (int): 返回结果的最大数量
        Returns:
            list: 匹配的表信息列表
        """
        results = []
        keyword_lower = keyword.lower()
        
        # 遍历缓存中的所有表
        for table_name, table_info in self.memory_cache.cache.items():
            # 检查表名是否包含关键词
            if keyword_lower in table_name.lower():
                results.append(table_info)
                continue
            
            # 检查列名和列注释是否包含关键词
            if "columns" in table_info:
                for column in table_info["columns"]:
                    if keyword_lower in column.get("name", "").lower() or \
                       keyword_lower in column.get("comment", "").lower():
                        results.append(table_info)
                        break
            
            # 检查是否有超过限制的结果
            if len(results) >= limit:
                break
        
        # 如果结果少于限制，尝试从数据库获取更多匹配的表
        if len(results) < limit:
            all_tables = self.db_manager.get_all_tables()
            matched_table_names = {table["table_name"] for table in results}
            for table_name in all_tables:
                if (keyword_lower in table_name.lower() and 
                    table_name not in matched_table_names):
                    table_info = self.get_table_info(table_name)
                    results.append(table_info)
                    matched_table_names.add(table_name)
                    
                    if len(results) >= limit:
                        break
        
        return results[:limit]


    def get_related_tables(self, table_name, max_depth=2):
        """获取关联表（通过外键）

        Args:
            table_name (str): 表名
            max_depth (int): 最大搜索深度
        Returns:
            list: 关联表信息列表
        """
        visited = set()
        related_tables = []
        queue = [(table_name, 0)]  # (table_name, depth)
        
        while queue:
            current_table, depth = queue.pop(0)
            
            if current_table in visited or depth >= max_depth + 1:
                continue
            visited.add(current_table)
            
            # 获取当前表的信息
            table_info = self.get_table_info(current_table)
            related_tables.append(table_info)
            
            if depth < max_depth:
                # 查找引用此表的外键（反向关联）
                for other_table_name, other_table_info in self.memory_cache.cache.items():
                    if other_table_name not in visited:
                        foreign_keys = other_table_info.get("foreign_keys", [])
                        for fk in foreign_keys:
                            if "references" in fk:
                                # 解析引用，格式通常是 'table.column'
                                referenced_table, referenced_column = fk["references"].split(".")
                                if referenced_table == current_table:
                                    queue.append((other_table_name, depth + 1))
                
                # 查找从此表指向其他表的外键（正向关联）
                foreign_keys = table_info.get("foreign_keys", [])
                for fk in foreign_keys:
                    if "references" in fk:
                        referenced_table, referenced_column = fk["references"].split(".")
                        if referenced_table not in visited:
                            queue.append((referenced_table, depth + 1))
        
        # 移除原始表，只返回相关联的表
        return [tbl for tbl in related_tables if tbl["table_name"] != table_name]

    def invalidate(self, table_name=None):
        """使缓存失效

        Args:
            table_name (str, optional): 表名，如果为None则清除所有缓存
        """
        if table_name:
            # 清除特定表的缓存
            if table_name in self.memory_cache.cache:
                del self.memory_cache.cache[table_name]
        else:
            # 清除所有缓存
            self.memory_cache.clear()
        
        # 保存更新后的缓存到文件
        self._save_file_cache()
