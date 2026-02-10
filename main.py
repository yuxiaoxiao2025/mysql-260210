import sys
from src.db_manager import DatabaseManager
from src.exporter import ExcelExporter
import datetime
import shlex

def print_welcome():
    print("=" * 50)
    print("🚗 漕河泾停车云数据导出工具 v1.0")
    print("=" * 50)
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
    except Exception as e:
        print(f"❌ 无法连接数据库: {e}")
        return

    print_welcome()

    while True:
        try:
            user_input = input("\n[MySQL] > ").strip()
            
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

            # 默认视为 SQL 查询
            # 如果不是 SELECT 开头，给予警告但允许执行（如果是为了导出，通常是 SELECT）
            if not user_input.lower().startswith('select') and not user_input.lower().startswith('show'):
                confirm = input("⚠️  这不是一个查询语句 (SELECT/SHOW)。确定要执行吗？(y/n) > ")
                if confirm.lower() != 'y':
                    continue

            print("⏳ 正在查询...")
            start_time = datetime.datetime.now()
            
            try:
                df = db.execute_query(user_input)
                duration = (datetime.datetime.now() - start_time).total_seconds()
                print(f"✅ 查询成功！耗时 {duration:.2f}秒，共 {len(df)} 行数据。")
                
                if not df.empty:
                    # 自动生成文件名
                    # 尝试从 SQL 中提取表名作为文件名的一部分
                    filename_part = "query_result"
                    tokens = user_input.lower().split()
                    if 'from' in tokens:
                        try:
                            idx = tokens.index('from') + 1
                            if idx < len(tokens):
                                filename_part = tokens[idx].replace('`', '').replace(';', '')
                        except:
                            pass
                            
                    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{filename_part}_{timestamp}.xlsx"
                    
                    print(f"💾 正在导出到 Excel...")
                    filepath = exporter.export(df, filename)
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
