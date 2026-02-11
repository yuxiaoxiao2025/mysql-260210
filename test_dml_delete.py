"""
DML 删除操作测试脚本

模拟 "把key为delete-me的记录删除" 的完整流程
"""
from src.db_manager import DatabaseManager
from src.llm_client import LLMClient
from src.schema_loader import SchemaLoader
from src.sql_safety import validate_sql, detect_intent
from src.txn_preview import summarize_diff
from src.preview_renderer import should_render_html
import pandas as pd

print("=" * 60)
print("DML Mutation Preview Test - DELETE Operation")
print("=" * 60)

# 初始化
print("\n1. Initializing components...")
db = DatabaseManager()
llm = LLMClient()
schema_loader = SchemaLoader(db_manager=db)
schema_context = schema_loader.get_schema_context()

# 查看当前数据
print("\n2. Current data in config_copy1 table:")
current_data = db.execute_query('SELECT id, parkNumber, parkName, `key` FROM config_copy1 WHERE parkNumber LIKE "TEST%"')
print(current_data.to_string())
print(f"\nTotal rows: {len(current_data)}")

# 测试自然语言输入
user_query = "把key为delete-me的记录删除掉"
print(f"\n3. User Query: \"{user_query}\"")

# 为了测试，我们直接构造 SQL（模拟 LLM 输出）
# 在实际使用中，这应该由 LLM 生成
print("\n4. Simulated LLM Output (for config_copy1 table)...")
result = {
    'sql': "DELETE FROM config_copy1 WHERE `key` = 'delete-me'",
    'intent': 'mutation',
    'preview_sql': "SELECT * FROM config_copy1 WHERE `key` = 'delete-me'",
    'key_columns': ['id'],
    'warnings': ["This will delete records where key = 'delete-me'"]
}
print(f"   Generated SQL: {result['sql']}")
print(f"   Intent: {result.get('intent', 'query')}")
print(f"   Preview SQL: {result.get('preview_sql', 'N/A')}")
print(f"   Key Columns: {result.get('key_columns', [])}")
print(f"   Warnings: {result.get('warnings', [])}")

# 安全校验
print("\n5. SQL Safety Check...")
sql = result['sql']
intent = detect_intent(sql)
is_valid, reason = validate_sql(sql)
print(f"   Detected Intent: {intent}")
print(f"   Safety Check: {'PASS' if is_valid else 'REJECT'} - {reason}")

if not is_valid:
    print("   ERROR: Dangerous operation detected!")
    exit(1)

# 检查是否为 DML 操作
is_mutation = result.get('intent') == 'mutation' or intent in ['insert', 'update', 'delete']
print(f"\n6. Is Mutation: {is_mutation}")

if is_mutation:
    # 事务预览
    print("\n7. Transaction Preview (First Pass - No Commit)...")
    preview_sql = result.get('preview_sql', f"SELECT * FROM config_copy1 WHERE parkNumber LIKE 'TEST%'")
    key_columns = result.get('key_columns', ['id'])

    if preview_sql:
        # 执行事务预览（不提交）
        txn_result = db.execute_in_transaction(
            mutation_sql=sql,
            preview_sql=preview_sql,
            key_columns=key_columns,
            commit=False  # 不提交，只是预览
        )

        # 显示差异摘要
        diff = txn_result['diff_summary']
        print("\n8. Diff Summary:")
        print(f"   - Inserted: {diff['inserted']} rows")
        print(f"   - Updated: {diff['updated']} rows")
        print(f"   - Deleted: {diff['deleted']} rows")
        print(f"   - Committed: {txn_result['committed']}")

        # 显示变更详情
        print("\n9. Before Data:")
        print(txn_result['before'][['id', 'parkNumber', 'key']].to_string() if not txn_result['before'].empty else "   (Empty)")

        print("\n10. After Data:")
        print(txn_result['after'][['id', 'parkNumber', 'key']].to_string() if not txn_result['after'].empty else "   (Empty)")

        # 渲染决策
        print("\n11. Preview Render Decision:")
        should_html = should_render_html(txn_result['before'], txn_result['after'], max_rows=30)
        print(f"    Should render HTML: {should_html}")

        # 模拟用户确认
        print("\n12. User Confirmation: YES - Commit the changes")

        # 第二次执行（提交）
        print("\n13. Transaction Preview (Second Pass - COMMIT)...")
        txn_result_commit = db.execute_in_transaction(
            mutation_sql=sql,
            preview_sql=preview_sql,
            key_columns=key_columns,
            commit=True  # 提交变更
        )

        print(f"    Changes committed: {txn_result_commit['committed']}")
        print(f"    Summary: {diff['deleted']} rows deleted")

# 验证最终结果
print("\n14. Final Data in config_copy1 table:")
final_data = db.execute_query('SELECT id, parkNumber, parkName, `key` FROM config_copy1 WHERE parkNumber LIKE "TEST%"')
print(final_data.to_string())
print(f"\nTotal rows: {len(final_data)}")

print("\n" + "=" * 60)
print("TEST COMPLETED SUCCESSFULLY!")
print("=" * 60)
