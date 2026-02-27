import sys
import datetime
import shlex
from src.db_manager import DatabaseManager
from src.exporter import ExcelExporter
from src.schema_loader import SchemaLoader
from src.llm_client import LLMClient
from src.sql_safety import validate_sql, detect_intent
from src.preview_renderer import should_render_html

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
            is_sql = first_word in ['select', 'show', 'describe', 'desc', 'explain', 'update', 'delete', 'insert', 'drop', 'alter', 'truncate']

            sql_to_execute = user_input
            base_filename = None
            export_sheet_name = "Sheet1"
            is_mutation = False  # Track if this is a DML operation

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
                    base_filename = result.get('filename', 'query_result')
                    export_sheet_name = result.get('sheet_name', 'Sheet1')
                    is_mutation = result.get('intent') == 'mutation'

                except Exception as e:
                    print(f"❌ AI 生成失败: {e}")
                    llm.add_error_to_history(user_input, str(e))
                    continue
            else:
                # Direct SQL input - detect intent
                intent = detect_intent(user_input)

                # Validate SQL safety first (reject dangerous operations)
                is_valid, reason = validate_sql(user_input)
                if not is_valid:
                    print(f"❌ 危险操作，拒绝执行: {reason}")
                    continue

                # Check if this is a mutation operation
                is_mutation = intent in ['insert', 'update', 'delete']

                if is_mutation:
                    # For direct DML input, we need preview_sql and key_columns
                    # Since we don't have LLM to generate them, ask user or use defaults
                    print("⚠️  检测到数据变更操作 (INSERT/UPDATE/DELETE)")
                    print("⚠️  直接输入的 SQL 缺少预览信息，建议使用自然语言模式。")

                    confirm = input("❓ 仍要继续执行吗？(y/n) > ")
                    if confirm.lower() != 'y':
                        continue

                    # For direct input, we can't provide preview, skip transaction preview
                    is_mutation = False  # Fall back to regular execution

            # Execute based on operation type
            if is_mutation:
                # Handle mutation with transaction preview
                print("🔍 正在预览变更...")
                try:
                    # Get mutation details from LLM result
                    # For direct SQL input, is_mutation would be False due to the check above
                    if isinstance(llm.generate_sql(user_input, schema_context), dict):
                        # This shouldn't happen as we set is_mutation=False for direct input
                        pass

                    # Extract preview information
                    preview_sql = None
                    key_columns = []
                    warnings = []

                    # For LLM-generated queries
                    if hasattr(llm, 'last_result'):
                        result = llm.last_result
                        preview_sql = result.get('preview_sql')
                        key_columns = result.get('key_columns', [])
                        warnings = result.get('warnings', [])

                    # For safety, if we don't have preview info, skip transaction preview
                    if not preview_sql:
                        print("⚠️  缺少预览 SQL，使用常规执行模式")
                        df = db.execute_query(sql_to_execute)
                        print(f"✅ 执行成功！共 {len(df)} 行受影响。")
                    else:
                        # Execute with transaction preview (first pass: no commit)
                        result = db.execute_in_transaction(
                            mutation_sql=sql_to_execute,
                            preview_sql=preview_sql,
                            key_columns=key_columns,
                            commit=False
                        )

                        # Display diff summary
                        diff = result['diff_summary']
                        print("📊 变更预览:")
                        print(f"  - 插入: {diff['inserted']} 行")
                        print(f"  - 更新: {diff['updated']} 行")
                        print(f"  - 删除: {diff['deleted']} 行")

                        # Show warnings if any
                        for warning in warnings:
                            print(f"⚠️  {warning}")

                        # Second confirmation
                        confirm = input("❓ 确认要提交这些变更吗？(y/n) > ")
                        if confirm.lower() == 'y':
                            # Execute again with commit=True
                            result = db.execute_in_transaction(
                                mutation_sql=sql_to_execute,
                                preview_sql=preview_sql,
                                key_columns=key_columns,
                                commit=True
                            )
                            print("✅ 变更已提交！")
                        else:
                            print("❌ 已取消，变更已回滚。")

                except Exception as e:
                    print(f"❌ 执行失败: {e}")
                    # Record error in conversation history
                    if not is_sql:
                        llm.add_error_to_history(user_input, str(e))

            else:
                # Regular query execution
                print("⏳ 正在查询...")
                start_time = datetime.datetime.now()

                try:
                    df = db.execute_query(sql_to_execute)
                    duration = (datetime.datetime.now() - start_time).total_seconds()
                    print(f"✅ 查询成功！耗时 {duration:.2f}秒，共 {len(df)} 行数据。")

                    if not df.empty:
                        # Always use timestamp to avoid file conflicts
                        if not base_filename:
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
                            base_filename = filename_part
                        
                        # Always add timestamp
                        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        export_filename = f"{base_filename}_{timestamp}"

                        print(f"💾 正在导出到 Excel...")
                        filepath = exporter.export(df, export_filename, sheet_name=export_sheet_name)
                        print(f"🎉 导出完成：{filepath}")
                    else:
                        print("⚠️  查询结果为空，未生成文件。")

                except Exception as e:
                    print(f"❌ 查询执行失败: {e}")
                    # Record error in conversation history
                    if not is_sql:
                        llm.add_error_to_history(user_input, str(e))

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生未知错误: {e}")

if __name__ == "__main__":
    main()
