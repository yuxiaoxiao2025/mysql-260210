"""
Database schema change detector.

Detects changes in table structure, field comments, and business semantics
to trigger automatic re-embedding when needed.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from sqlalchemy import text

from src.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class TableVersion:
    """表版本信息"""
    table_name: str
    version_hash: str
    column_count: int
    last_checked: datetime
    columns_hash: str = ""
    comment: str = ""


@dataclass
class ChangeDetectionResult:
    """变化检测结果"""
    added_tables: List[str] = field(default_factory=list)
    removed_tables: List[str] = field(default_factory=list)
    modified_tables: List[str] = field(default_factory=list)
    unchanged_tables: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added_tables or self.removed_tables or self.modified_tables)

    @property
    def total_changes(self) -> int:
        return len(self.added_tables) + len(self.removed_tables) + len(self.modified_tables)


class SchemaChangeDetector:
    """
    表结构变化检测器

    通过计算表结构哈希来检测变化，触发增量同步。
    """

    VERSION_FILE = "data/dev/table_versions.json"

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        version_file: Optional[str] = None
    ):
        """
        初始化变化检测器。

        Args:
            db_manager: 数据库管理器
            version_file: 版本文件路径
        """
        self.db_manager = db_manager or DatabaseManager(specific_db=None)
        self.version_file = Path(version_file or self.VERSION_FILE)
        self.version_file.parent.mkdir(parents=True, exist_ok=True)

        self._versions: Dict[str, TableVersion] = {}
        self._load_versions()

        logger.info(f"SchemaChangeDetector initialized with {len(self._versions)} cached versions")

    def _load_versions(self) -> None:
        """加载版本缓存"""
        if not self.version_file.exists():
            return

        try:
            with open(self.version_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for table_name, version_data in data.items():
                self._versions[table_name] = TableVersion(
                    table_name=table_name,
                    version_hash=version_data.get("version_hash", ""),
                    column_count=version_data.get("column_count", 0),
                    last_checked=datetime.fromisoformat(version_data["last_checked"])
                        if "last_checked" in version_data else datetime.now(),
                    columns_hash=version_data.get("columns_hash", ""),
                    comment=version_data.get("comment", ""),
                )

        except Exception as e:
            logger.warning(f"Failed to load version cache: {e}")

    def _save_versions(self) -> None:
        """保存版本缓存"""
        try:
            data = {}
            for table_name, version in self._versions.items():
                data[table_name] = {
                    "version_hash": version.version_hash,
                    "column_count": version.column_count,
                    "last_checked": version.last_checked.isoformat(),
                    "columns_hash": version.columns_hash,
                    "comment": version.comment,
                }

            with open(self.version_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved {len(data)} table versions")

        except Exception as e:
            logger.error(f"Failed to save version cache: {e}")

    def compute_table_hash(self, db_name: str, table_name: str) -> str:
        """
        计算表结构哈希。

        Args:
            db_name: 数据库名
            table_name: 表名

        Returns:
            哈希值
        """
        # 获取表结构信息
        columns_sql = """
            SELECT
                COLUMN_NAME,
                COLUMN_TYPE,
                COLUMN_COMMENT,
                IS_NULLABLE,
                COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """

        table_sql = """
            SELECT TABLE_COMMENT
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name
        """

        hash_components = []

        with self.db_manager.get_connection() as conn:
            # 获取列信息
            columns_result = conn.execute(
                text(columns_sql),
                {"db_name": db_name, "table_name": table_name}
            )

            for row in columns_result:
                col_info = f"{row[0]}|{row[1]}|{row[2]}|{row[3]}|{row[4]}"
                hash_components.append(col_info)

            # 获取表注释
            table_result = conn.execute(
                text(table_sql),
                {"db_name": db_name, "table_name": table_name}
            )
            table_row = table_result.fetchone()
            if table_row:
                hash_components.append(f"TABLE_COMMENT:{table_row[0] or ''}")

        # 计算哈希
        hash_input = "\n".join(hash_components)
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def detect_changes(
        self,
        db_name: str,
        tables: List[str]
    ) -> ChangeDetectionResult:
        """
        检测表结构变化。

        Args:
            db_name: 数据库名
            tables: 要检测的表列表

        Returns:
            变化检测结果
        """
        result = ChangeDetectionResult()

        current_tables = set(tables)
        cached_tables = set(self._versions.keys())

        # 新增的表
        result.added_tables = list(current_tables - cached_tables)

        # 已删除的表
        result.removed_tables = list(cached_tables - current_tables)

        # 检查现有表的变化
        for table_name in current_tables & cached_tables:
            current_hash = self.compute_table_hash(db_name, table_name)
            cached_hash = self._versions[table_name].version_hash

            if current_hash != cached_hash:
                result.modified_tables.append(table_name)
            else:
                result.unchanged_tables.append(table_name)

        logger.info(
            f"Change detection: {len(result.added_tables)} added, "
            f"{len(result.removed_tables)} removed, "
            f"{len(result.modified_tables)} modified"
        )

        return result

    def update_version(self, db_name: str, table_name: str) -> TableVersion:
        """
        更新表版本信息。

        Args:
            db_name: 数据库名
            table_name: 表名

        Returns:
            新的版本信息
        """
        version_hash = self.compute_table_hash(db_name, table_name)

        # 获取列数
        sql = """
            SELECT COUNT(*) as col_count
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name
        """

        with self.db_manager.get_connection() as conn:
            result = conn.execute(
                text(sql),
                {"db_name": db_name, "table_name": table_name}
            )
            row = result.fetchone()
            column_count = row[0] if row else 0

        version = TableVersion(
            table_name=table_name,
            version_hash=version_hash,
            column_count=column_count,
            last_checked=datetime.now(),
        )

        self._versions[table_name] = version
        self._save_versions()

        logger.info(f"Updated version for {table_name}: {version_hash}")
        return version

    def get_tables_needing_reindex(
        self,
        db_name: str,
        tables: List[str]
    ) -> List[str]:
        """
        获取需要重新索引的表。

        Args:
            db_name: 数据库名
            tables: 表列表

        Returns:
            需要重新索引的表列表
        """
        result = self.detect_changes(db_name, tables)
        return result.added_tables + result.modified_tables

    def clear_cache(self) -> None:
        """清除版本缓存"""
        self._versions.clear()
        if self.version_file.exists():
            self.version_file.unlink()
        logger.info("Cleared version cache")
