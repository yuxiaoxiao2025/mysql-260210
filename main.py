import sys
import datetime
import shlex
from src.db_manager import DatabaseManager
from src.exporter import ExcelExporter
from src.schema_loader import SchemaLoader
from src.llm_client import LLMClient

def print_welcome():
    print("=" * 50)
    print("🚗 漕河泾停车云数据导出工具 v2.0 (AI Enhanced)")
    print("=" * 50)
    print("可以直接输入自然语言进行查询，例如：")
    print("  '帮我导出登录人员表'")
    print("  '查询所有固定车牌并导出'")
    print("-" * 50)
    print("输入 SQL 查询语句，或者使用以下命令：")
    print("  list tables       - 列出所有表")
    print("  desc <table>      - 查看表结构")
    print("  exit / quit       - 退出程序")
    print("=" * 50)

def main():
    try:
        print("正在连接数据库...")
        db = DatabaseManager()
        exporter = ExcelExporter()
        print("✅ 数据库连接成功！")
        
        print("正在加载 AI 模块...")
        llm = LLMClient()
        schema_loader = SchemaLoader(db_manager=db)
        # Pre-load schema context
        schema_context = schema_loader.get_schema_context()
        print("✅ AI 模块加载成功！")
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return

    print_welcome()

    while True:
        try:
            user_input = input("\n[MySQL/AI] > ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ('exit', 'quit'):
                print("👋 再见！")
                break
                
            if user_input.lower() == 'list tables':
                tables = db.get_all_tables()
                print("\n📊 数据库中的表：")
                for i, t in enumerate(tables):
                    print(f"  {i+1}. {t}")
                continue
                
            if user_input.lower().startswith('desc '):
                table_name = user_input.split()[1]
                try:
                    schema = db.get_table_schema(table_name)
                    print(f"\n📋 表 {table_name} 结构：")
                    print(f"{'字段名':<20} {'类型':<15} {'注释'}")
                    print("-" * 50)
                    for col in schema:
                        print(f"{col['name']:<20} {col['type']:<15} {col['comment']}")
                except Exception as e:
                    print(f"❌ 获取表结构失败: {e}")
                continue

            # Check if it looks like SQL
            first_word = user_input.lower().split()[0] if user_input else ""
            is_sql = first_word in ['select', 'show', 'describe', 'desc', 'explain', 'update', 'delete', 'insert']
            
            sql_to_execute = user_input
            export_filename = None
            export_sheet_name = "Sheet1"
            
            if not is_sql:
                if not llm.api_key:
                    print("❌ 未配置 API Key，无法使用自然语言查询。请在 .env 中设置 DASHSCOPE_API_KEY。")
                    continue
                    
                print("🧠 正在思考您的需求...")
                try:
                    result = llm.generate_sql(user_input, schema_context)
                    print("-" * 30)
                    print(f"🤖 生成的 SQL:\n{result['sql']}")
                    print(f"💡 思考过程: {result.get('reasoning', '无')}")
                    print("-" * 30)
                    
                    confirm = input("❓ 是否执行此查询？(y/n) > ")
                    if confirm.lower() != 'y':
                        continue
                        
                    sql_to_execute = result['sql']
                    export_filename = result.get('filename')
                    export_sheet_name = result.get('sheet_name', 'Sheet1')
                    
                except Exception as e:
                    print(f"❌ AI 生成失败: {e}")
                    continue
            else:
                 # Standard SQL execution
                 if not user_input.lower().startswith('select') and not user_input.lower().startswith('show'):
                    confirm = input("⚠️  这不是一个查询语句 (SELECT/SHOW)。确定要执行吗？(y/n) > ")
                    if confirm.lower() != 'y':
                        continue

            print("⏳ 正在查询...")
            start_time = datetime.datetime.now()
            
            try:
                df = db.execute_query(sql_to_execute)
                duration = (datetime.datetime.now() - start_time).total_seconds()
                print(f"✅ 查询成功！耗时 {duration:.2f}秒，共 {len(df)} 行数据。")
                
                if not df.empty:
                    if not export_filename:
                         # Fallback to existing filename generation
                         filename_part = "query_result"
                         tokens = sql_to_execute.lower().split()
                         if 'from' in tokens:
                            try:
                                idx = tokens.index('from') + 1
                                if idx < len(tokens):
                                    filename_part = tokens[idx].replace('`', '').replace(';', '')
                            except:
                                pass
                         timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                         export_filename = f"{filename_part}_{timestamp}"
                    
                    print(f"💾 正在导出到 Excel...")
                    filepath = exporter.export(df, export_filename, sheet_name=export_sheet_name)
                    print(f"🎉 导出完成：{filepath}")
                else:
                    print("⚠️  查询结果为空，未生成文件。")
                    
            except Exception as e:
                print(f"❌ 查询执行失败: {e}")

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生未知错误: {e}")

if __name__ == "__main__":
    main()
