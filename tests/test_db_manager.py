import pytest
from src.db_manager import DatabaseManager
import pandas as pd
from sqlalchemy.exc import OperationalError

@pytest.fixture
def db_manager():
    return DatabaseManager()

@pytest.fixture
def db_manager_with_test_table(db_manager):
    """创建带测试表的 DatabaseManager，并在测试后清理"""
    # 创建测试表
    db_manager.execute_update("""
        CREATE TABLE IF NOT EXISTS test_execute_update (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL,
            age INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 清空表
    db_manager.execute_update("DELETE FROM test_execute_update")

    yield db_manager

    # 清理：删除测试表
    try:
        db_manager.execute_update("DROP TABLE IF EXISTS test_execute_update")
    except Exception:
        pass  # 忽略清理错误


class TestExecuteUpdate:
    """execute_update 方法的测试类"""

    def test_execute_update_returns_int(self, db_manager_with_test_table):
        """测试 execute_update 返回整数类型"""
        result = db_manager_with_test_table.execute_update(
            "INSERT INTO test_execute_update (name, age) VALUES ('Alice', 25)"
        )
        assert isinstance(result, int)
        assert result >= 0  # 影响行数应该非负

    def test_execute_update_insert(self, db_manager_with_test_table):
        """测试执行 INSERT 语句"""
        # 插入数据
        result = db_manager_with_test_table.execute_update(
            "INSERT INTO test_execute_update (name, age) VALUES ('Bob', 30)"
        )
        assert result == 1  # INSERT 影响 1 行

        # 验证数据确实插入了
        df = db_manager_with_test_table.execute_query(
            "SELECT * FROM test_execute_update WHERE name = 'Bob'"
        )
        assert len(df) == 1
        assert df.iloc[0]['name'] == 'Bob'
        assert df.iloc[0]['age'] == 30

    def test_execute_update_update(self, db_manager_with_test_table):
        """测试执行 UPDATE 语句并返回影响行数"""
        # 先插入数据
        db_manager_with_test_table.execute_update(
            "INSERT INTO test_execute_update (name, age) VALUES ('Charlie', 20)"
        )

        # 执行 UPDATE
        result = db_manager_with_test_table.execute_update(
            "UPDATE test_execute_update SET age = 25 WHERE name = 'Charlie'"
        )
        assert result == 1  # UPDATE 影响 1 行

        # 验证数据确实更新了
        df = db_manager_with_test_table.execute_query(
            "SELECT * FROM test_execute_update WHERE name = 'Charlie'"
        )
        assert df.iloc[0]['age'] == 25

    def test_execute_update_delete(self, db_manager_with_test_table):
        """测试执行 DELETE 语句"""
        # 先插入数据
        db_manager_with_test_table.execute_update(
            "INSERT INTO test_execute_update (name, age) VALUES ('David', 35)"
        )

        # 验证数据存在
        df_before = db_manager_with_test_table.execute_query(
            "SELECT * FROM test_execute_update WHERE name = 'David'"
        )
        assert len(df_before) == 1

        # 执行 DELETE
        result = db_manager_with_test_table.execute_update(
            "DELETE FROM test_execute_update WHERE name = 'David'"
        )
        assert result == 1  # DELETE 影响 1 行

        # 验证数据确实删除了
        df_after = db_manager_with_test_table.execute_query(
            "SELECT * FROM test_execute_update WHERE name = 'David'"
        )
        assert len(df_after) == 0

    def test_execute_update_syntax_error(self, db_manager_with_test_table):
        """测试异常情况：SQL 语法错误"""
        with pytest.raises(Exception):  # OperationalError 或类似的 SQL 异常
            db_manager_with_test_table.execute_update(
                "INVALID SQL STATEMENT HERE"
            )

    def test_execute_update_parameterized_query(self, db_manager_with_test_table):
        """测试参数化查询（防止 SQL 注入）"""
        # 使用参数化插入数据
        result = db_manager_with_test_table.execute_update(
            "INSERT INTO test_execute_update (name, age) VALUES (:name, :age)",
            params={"name": "Eve", "age": 28}
        )
        assert result == 1

        # 验证数据
        df = db_manager_with_test_table.execute_query(
            "SELECT * FROM test_execute_update WHERE name = 'Eve'"
        )
        assert len(df) == 1
        assert df.iloc[0]['name'] == 'Eve'
        assert df.iloc[0]['age'] == 28

    def test_execute_update_parameterized_update(self, db_manager_with_test_table):
        """测试参数化 UPDATE 查询"""
        # 先插入数据
        db_manager_with_test_table.execute_update(
            "INSERT INTO test_execute_update (name, age) VALUES ('Frank', 40)"
        )

        # 使用参数化更新
        result = db_manager_with_test_table.execute_update(
            "UPDATE test_execute_update SET age = :age WHERE name = :name",
            params={"name": "Frank", "age": 45}
        )
        assert result == 1

        # 验证更新
        df = db_manager_with_test_table.execute_query(
            "SELECT * FROM test_execute_update WHERE name = 'Frank'"
        )
        assert df.iloc[0]['age'] == 45

    def test_execute_update_with_special_characters(self, db_manager_with_test_table):
        """测试特殊字符处理（防止 SQL 注入攻击）"""
        # 尝试 SQL 注入攻击
        malicious_name = "'); DROP TABLE test_execute_update; --"

        # 使用参数化查询，应该安全处理
        result = db_manager_with_test_table.execute_update(
            "INSERT INTO test_execute_update (name, age) VALUES (:name, :age)",
            params={"name": malicious_name, "age": 99}
        )
        assert result == 1  # 应该成功插入，而不是执行恶意 SQL

        # 验证表仍然存在
        tables = db_manager_with_test_table.get_all_tables()
        assert 'test_execute_update' in tables

        # 验证恶意字符串被原样插入
        df = db_manager_with_test_table.execute_query(
            "SELECT * FROM test_execute_update WHERE age = 99"
        )
        assert len(df) == 1
        assert df.iloc[0]['name'] == malicious_name

    def test_execute_update_empty_params(self, db_manager_with_test_table):
        """测试空参数情况"""
        # 不使用参数的 INSERT
        result = db_manager_with_test_table.execute_update(
            "INSERT INTO test_execute_update (name, age) VALUES ('NoParam', 18)"
        )
        assert result == 1

    def test_execute_update_multiple_rows(self, db_manager_with_test_table):
        """测试影响多行的情况"""
        # 插入多行
        for i in range(5):
            db_manager_with_test_table.execute_update(
                "INSERT INTO test_execute_update (name, age) VALUES (:name, :age)",
                params={"name": f"User{i}", "age": 20 + i}
            )

        # UPDATE 多行
        result = db_manager_with_test_table.execute_update(
            "UPDATE test_execute_update SET age = 99 WHERE age >= 20 AND age <= 24"
        )
        assert result == 5  # 应该影响 5 行

        # DELETE 多行
        result = db_manager_with_test_table.execute_update(
            "DELETE FROM test_execute_update WHERE age = 99"
        )
        assert result == 5  # 应该影响 5 行

def test_connection(db_manager):
    """测试能否成功连接"""
    with db_manager.get_connection() as conn:
        assert conn is not None

def test_execute_query(db_manager):
    """测试执行简单查询"""
    # 假设 config 表存在 (从 mysql.md 可知)
    # 或者用 SELECT 1
    df = db_manager.execute_query("SELECT 1 as val")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.iloc[0]['val'] == 1

def test_get_all_tables(db_manager):
    """测试获取表列表"""
    tables = db_manager.get_all_tables()
    assert isinstance(tables, list)
    # 只要列表不报错即可，数据库可能为空，但至少应该能跑通
    print(f"Found tables: {tables}")

def test_get_table_schema(db_manager):
    """测试获取表结构"""
    tables = db_manager.get_all_tables()
    if tables:
        table_name = tables[0]
        schema = db_manager.get_table_schema(table_name)
        assert isinstance(schema, list)
        if schema:
            col = schema[0]
            assert 'name' in col
            assert 'type' in col


@pytest.fixture
def db_manager_with_txn_test_table(db_manager):
    """创建带事务测试表的 DatabaseManager，并在测试后清理"""
    # 创建测试表
    db_manager.execute_update("""
        CREATE TABLE IF NOT EXISTS test_txn (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL,
            age INT,
            status VARCHAR(20) DEFAULT 'active'
        )
    """)
    # 清空表
    db_manager.execute_update("DELETE FROM test_txn")

    yield db_manager

    # 清理：删除测试表
    try:
        db_manager.execute_update("DROP TABLE IF EXISTS test_txn")
    except Exception:
        pass  # 忽略清理错误


class TestExecuteInTransaction:
    """execute_in_transaction 方法的测试类"""

    def test_execute_in_transaction_no_params(self, db_manager_with_txn_test_table):
        """测试无参数的事务执行（向后兼容性）"""
        # 先插入一些测试数据
        db_manager_with_txn_test_table.execute_update(
            "INSERT INTO test_txn (name, age) VALUES ('Alice', 25)"
        )
        db_manager_with_txn_test_table.execute_update(
            "INSERT INTO test_txn (name, age) VALUES ('Bob', 30)"
        )

        # 执行事务：更新 Alice 的年龄
        result = db_manager_with_txn_test_table.execute_in_transaction(
            mutation_sql="UPDATE test_txn SET age = 26 WHERE name = 'Alice'",
            preview_sql="SELECT * FROM test_txn WHERE name = 'Alice'",
            key_columns=['id'],
            commit=False  # 不提交，会回滚
        )

        # 验证返回结果
        assert 'before' in result
        assert 'after' in result
        assert 'diff_summary' in result
        assert 'committed' in result
        assert result['committed'] is False  # 未提交

        # 验证 Before 数据
        assert len(result['before']) == 1
        assert result['before'].iloc[0]['name'] == 'Alice'
        assert result['before'].iloc[0]['age'] == 25

        # 验证 After 数据（事务内已更新）
        assert len(result['after']) == 1
        assert result['after'].iloc[0]['name'] == 'Alice'
        assert result['after'].iloc[0]['age'] == 26

        # 验证差异摘要
        assert result['diff_summary']['updated'] == 1
        assert result['diff_summary']['inserted'] == 0
        assert result['diff_summary']['deleted'] == 0

        # 验证数据已回滚（Alice 的年龄应该还是 25）
        df = db_manager_with_txn_test_table.execute_query(
            "SELECT * FROM test_txn WHERE name = 'Alice'"
        )
        assert df.iloc[0]['age'] == 25

    def test_execute_in_transaction_with_mutation_params(self, db_manager_with_txn_test_table):
        """测试带 mutation_params 的事务执行"""
        # 先插入测试数据
        db_manager_with_txn_test_table.execute_update(
            "INSERT INTO test_txn (name, age) VALUES ('Charlie', 20)"
        )

        # 使用参数化查询更新
        result = db_manager_with_txn_test_table.execute_in_transaction(
            mutation_sql="UPDATE test_txn SET age = :new_age WHERE name = :name",
            preview_sql="SELECT * FROM test_txn WHERE name = :name",
            key_columns=['id'],
            commit=False,
            mutation_params={"new_age": 25, "name": "Charlie"},
            preview_params={"name": "Charlie"}
        )

        # 验证更新成功
        assert result['before'].iloc[0]['age'] == 20
        assert result['after'].iloc[0]['age'] == 25
        assert result['diff_summary']['updated'] == 1

    def test_execute_in_transaction_with_preview_params(self, db_manager_with_txn_test_table):
        """测试带 preview_params 的事务执行"""
        # 插入多条数据
        db_manager_with_txn_test_table.execute_update(
            "INSERT INTO test_txn (name, age) VALUES ('David', 30)"
        )
        db_manager_with_txn_test_table.execute_update(
            "INSERT INTO test_txn (name, age) VALUES ('Eve', 28)"
        )

        # 只查询特定状态的数据
        result = db_manager_with_txn_test_table.execute_in_transaction(
            mutation_sql="UPDATE test_txn SET age = age + 1",
            preview_sql="SELECT * FROM test_txn WHERE name = :name",
            key_columns=['id'],
            commit=False,
            mutation_params=None,
            preview_params={"name": "David"}
        )

        # 验证只返回了 David 的数据
        assert len(result['before']) == 1
        assert result['before'].iloc[0]['name'] == 'David'
        assert result['before'].iloc[0]['age'] == 30
        assert result['after'].iloc[0]['age'] == 31

    def test_execute_in_transaction_commit_true(self, db_manager_with_txn_test_table):
        """测试 commit=True 的情况"""
        # 先插入测试数据
        db_manager_with_txn_test_table.execute_update(
            "INSERT INTO test_txn (name, age) VALUES ('Frank', 40)"
        )

        # 执行事务并提交
        result = db_manager_with_txn_test_table.execute_in_transaction(
            mutation_sql="UPDATE test_txn SET age = :new_age WHERE name = :name",
            preview_sql="SELECT * FROM test_txn WHERE name = :name",
            key_columns=['id'],
            commit=True,
            mutation_params={"new_age": 45, "name": "Frank"},
            preview_params={"name": "Frank"}
        )

        # 验证已提交
        assert result['committed'] is True

        # 验证数据确实更新了（事务已提交）
        df = db_manager_with_txn_test_table.execute_query(
            "SELECT * FROM test_txn WHERE name = 'Frank'"
        )
        assert df.iloc[0]['age'] == 45

    def test_execute_in_transaction_insert_operation(self, db_manager_with_txn_test_table):
        """测试 INSERT 操作的事务"""
        # 执行 INSERT 操作
        result = db_manager_with_txn_test_table.execute_in_transaction(
            mutation_sql="INSERT INTO test_txn (name, age, status) VALUES (:name, :age, :status)",
            preview_sql="SELECT * FROM test_txn WHERE name = :name",
            key_columns=['id'],
            commit=False,
            mutation_params={"name": "Grace", "age": 27, "status": "active"},
            preview_params={"name": "Grace"}
        )

        # 验证操作结果
        assert len(result['before']) == 0  # Before 为空
        assert len(result['after']) == 1  # After 有 1 条
        assert result['diff_summary']['inserted'] == 1
        assert result['after'].iloc[0]['name'] == 'Grace'

    def test_execute_in_transaction_delete_operation(self, db_manager_with_txn_test_table):
        """测试 DELETE 操作的事务"""
        # 先插入测试数据
        db_manager_with_txn_test_table.execute_update(
            "INSERT INTO test_txn (name, age) VALUES ('Henry', 35)"
        )

        # 执行 DELETE 操作
        result = db_manager_with_txn_test_table.execute_in_transaction(
            mutation_sql="DELETE FROM test_txn WHERE name = :name",
            preview_sql="SELECT * FROM test_txn WHERE name = :name",
            key_columns=['id'],
            commit=False,
            mutation_params={"name": "Henry"},
            preview_params={"name": "Henry"}
        )

        # 验证操作结果
        assert len(result['before']) == 1  # Before 有 1 条
        assert len(result['after']) == 0  # After 为空
        assert result['diff_summary']['deleted'] == 1
        assert result['before'].iloc[0]['name'] == 'Henry'

    def test_execute_in_transaction_empty_params(self, db_manager_with_txn_test_table):
        """测试空参数字典的情况"""
        # 先插入测试数据
        db_manager_with_txn_test_table.execute_update(
            "INSERT INTO test_txn (name, age) VALUES ('Ivy', 22)"
        )

        # 使用空参数字典
        result = db_manager_with_txn_test_table.execute_in_transaction(
            mutation_sql="UPDATE test_txn SET age = 23 WHERE name = 'Ivy'",
            preview_sql="SELECT * FROM test_txn WHERE name = 'Ivy'",
            key_columns=['id'],
            commit=False,
            mutation_params={},
            preview_params={}
        )

        # 验证操作成功
        assert result['before'].iloc[0]['age'] == 22
        assert result['after'].iloc[0]['age'] == 23


@pytest.fixture
def db_manager_with_multi_step_test_table(db_manager):
    """创建带多步骤事务测试表的 DatabaseManager，并在测试后清理"""
    # 创建测试表
    db_manager.execute_update("""
        CREATE TABLE IF NOT EXISTS test_multi_step (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL,
            value INT,
            category VARCHAR(50)
        )
    """)
    # 清空表
    db_manager.execute_update("DELETE FROM test_multi_step")

    yield db_manager

    # 清理：删除测试表
    try:
        db_manager.execute_update("DROP TABLE IF EXISTS test_multi_step")
    except Exception:
        pass  # 忽略清理错误


class TestExecuteMultiStepTransaction:
    """execute_multi_step_transaction 方法的测试类"""

    def test_execute_multi_step_transaction_success(self, db_manager_with_multi_step_test_table):
        """测试成功执行多步骤事务"""
        sql_steps = [
            ("INSERT INTO test_multi_step (name, value, category) VALUES (:name, :value, :category)",
             {"name": "Alice", "value": 100, "category": "A"}),
            ("INSERT INTO test_multi_step (name, value, category) VALUES (:name, :value, :category)",
             {"name": "Bob", "value": 200, "category": "B"}),
            ("UPDATE test_multi_step SET value = value + 50 WHERE category = 'A'", None),
        ]

        result = db_manager_with_multi_step_test_table.execute_multi_step_transaction(
            sql_steps=sql_steps,
            commit=True
        )

        # 验证返回结果
        assert result['success'] is True
        assert result['steps_executed'] == 3
        assert len(result['affected_rows']) == 3
        assert result['affected_rows'] == [1, 1, 1]
        assert result['committed'] is True

        # 验证数据确实插入了
        df = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step"
        )
        assert len(df) == 2

        # 验证 Alice 的值被更新了
        alice_df = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step WHERE name = 'Alice'"
        )
        assert len(alice_df) == 1
        assert alice_df.iloc[0]['value'] == 150

    def test_execute_multi_step_transaction_rollback_on_failure(self, db_manager_with_multi_step_test_table):
        """测试失败时事务回滚"""
        # 先插入一些数据
        db_manager_with_multi_step_test_table.execute_update(
            "INSERT INTO test_multi_step (name, value) VALUES ('Initial', 10)"
        )

        # 记录初始数据
        df_before = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step"
        )
        initial_count = len(df_before)

        # 执行包含失败步骤的事务
        sql_steps = [
            ("INSERT INTO test_multi_step (name, value) VALUES (:name, :value)",
             {"name": "Step1", "value": 20}),
            ("INSERT INTO test_multi_step (name, value) VALUES (:name, :value)",
             {"name": "Step2", "value": 30}),
            ("INVALID SQL STATEMENT HERE", None),  # 这会失败
            ("INSERT INTO test_multi_step (name, value) VALUES (:name, :value)",
             {"name": "Step4", "value": 40}),
        ]

        result = db_manager_with_multi_step_test_table.execute_multi_step_transaction(
            sql_steps=sql_steps,
            commit=True
        )

        # 验证返回结果
        assert result['success'] is False
        assert result['failed_at_step'] == 2  # 第 2 个步骤失败（0-based）
        assert result['steps_executed'] == 2  # 前 2 个步骤执行成功
        assert len(result['affected_rows']) == 2
        assert result['committed'] is False
        assert 'error' in result

        # 验证事务已回滚 - 新数据未插入
        df_after = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step"
        )
        assert len(df_after) == initial_count

        # 验证失败的数据不存在
        step1_df = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step WHERE name = 'Step1'"
        )
        step2_df = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step WHERE name = 'Step2'"
        )
        assert len(step1_df) == 0
        assert len(step2_df) == 0

    def test_execute_multi_step_transaction_commit_false(self, db_manager_with_multi_step_test_table):
        """测试 commit=False 的情况（回滚）"""
        # 先插入一些数据
        db_manager_with_multi_step_test_table.execute_update(
            "INSERT INTO test_multi_step (name, value) VALUES ('Original', 50)"
        )

        # 记录初始数据
        df_before = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step"
        )
        initial_count = len(df_before)

        # 执行事务但不提交
        sql_steps = [
            ("INSERT INTO test_multi_step (name, value) VALUES (:name, :value)",
             {"name": "New1", "value": 100}),
            ("INSERT INTO test_multi_step (name, value) VALUES (:name, :value)",
             {"name": "New2", "value": 200}),
        ]

        result = db_manager_with_multi_step_test_table.execute_multi_step_transaction(
            sql_steps=sql_steps,
            commit=False
        )

        # 验证返回结果
        assert result['success'] is True
        assert result['steps_executed'] == 2
        assert result['committed'] is False

        # 验证事务已回滚 - 新数据未持久化
        df_after = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step"
        )
        assert len(df_after) == initial_count

        # 验证新数据不存在
        new1_df = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step WHERE name = 'New1'"
        )
        new2_df = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step WHERE name = 'New2'"
        )
        assert len(new1_df) == 0
        assert len(new2_df) == 0

    def test_execute_multi_step_transaction_empty_steps(self, db_manager_with_multi_step_test_table):
        """测试空步骤列表"""
        result = db_manager_with_multi_step_test_table.execute_multi_step_transaction(
            sql_steps=[],
            commit=True
        )

        # 验证返回结果
        assert result['success'] is True
        assert result['steps_executed'] == 0
        assert result['affected_rows'] == []
        assert result['committed'] is True

    def test_execute_multi_step_transaction_mixed_operations(self, db_manager_with_multi_step_test_table):
        """测试混合操作（INSERT, UPDATE, DELETE）"""
        # 先插入一些数据
        db_manager_with_multi_step_test_table.execute_update(
            "INSERT INTO test_multi_step (name, value) VALUES ('ToDelete', 999)"
        )

        # 执行混合操作
        sql_steps = [
            ("INSERT INTO test_multi_step (name, value) VALUES (:name, :value)",
             {"name": "NewRecord", "value": 100}),
            ("UPDATE test_multi_step SET value = 50 WHERE name = 'NewRecord'", None),
            ("DELETE FROM test_multi_step WHERE name = 'ToDelete'", None),
        ]

        result = db_manager_with_multi_step_test_table.execute_multi_step_transaction(
            sql_steps=sql_steps,
            commit=True
        )

        # 验证返回结果
        assert result['success'] is True
        assert result['steps_executed'] == 3
        assert result['affected_rows'] == [1, 1, 1]
        assert result['committed'] is True

        # 验证数据状态
        df = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step"
        )
        assert len(df) == 1
        assert df.iloc[0]['name'] == 'NewRecord'
        assert df.iloc[0]['value'] == 50

    def test_execute_multi_step_transaction_batch_insert(self, db_manager_with_multi_step_test_table):
        """测试批量插入（模拟"批量下发到所有场库"场景）"""
        # 模拟批量插入多条记录
        sql_steps = [
            ("INSERT INTO test_multi_step (name, value, category) VALUES (:name, :value, :category)",
             {"name": f"Site{i}", "value": i * 10, "category": "production"})
            for i in range(1, 11)  # 插入 10 条记录
        ]

        result = db_manager_with_multi_step_test_table.execute_multi_step_transaction(
            sql_steps=sql_steps,
            commit=True
        )

        # 验证返回结果
        assert result['success'] is True
        assert result['steps_executed'] == 10
        assert result['affected_rows'] == [1] * 10  # 每条记录影响 1 行
        assert result['committed'] is True

        # 验证所有数据都已插入
        df = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step WHERE category = 'production'"
        )
        assert len(df) == 10

    def test_execute_multi_step_transaction_parameterized_queries(self, db_manager_with_multi_step_test_table):
        """测试参数化查询（防止 SQL 注入）"""
        # 使用参数化查询
        malicious_name = "'); DROP TABLE test_multi_step; --"

        sql_steps = [
            ("INSERT INTO test_multi_step (name, value) VALUES (:name, :value)",
             {"name": malicious_name, "value": 100}),
            ("UPDATE test_multi_step SET value = :value WHERE name = :name",
             {"value": 200, "name": malicious_name}),
        ]

        result = db_manager_with_multi_step_test_table.execute_multi_step_transaction(
            sql_steps=sql_steps,
            commit=True
        )

        # 验证执行成功
        assert result['success'] is True
        assert result['steps_executed'] == 2

        # 验证表仍然存在（未被恶意 SQL 删除）
        tables = db_manager_with_multi_step_test_table.get_all_tables()
        assert 'test_multi_step' in tables

        # 验证恶意字符串被原样处理
        df = db_manager_with_multi_step_test_table.execute_query(
            "SELECT * FROM test_multi_step WHERE name = :name",
            params={"name": malicious_name}
        )
        assert len(df) == 1
        assert df.iloc[0]['name'] == malicious_name
        assert df.iloc[0]['value'] == 200

    def test_execute_multi_step_transaction_early_failure(self, db_manager_with_multi_step_test_table):
        """测试第一步就失败的情况"""
        sql_steps = [
            ("INVALID SQL HERE", None),  # 第一步就失败
            ("INSERT INTO test_multi_step (name, value) VALUES ('ShouldNotInsert', 1)", None),
        ]

        result = db_manager_with_multi_step_test_table.execute_multi_step_transaction(
            sql_steps=sql_steps,
            commit=True
        )

        # 验证返回结果
        assert result['success'] is False
        assert result['failed_at_step'] == 0
        assert result['steps_executed'] == 0
        assert result['affected_rows'] == []

    def test_execute_multi_step_transaction_multiple_row_operations(self, db_manager_with_multi_step_test_table):
        """测试影响多行的操作"""
        # 先插入多条数据
        for i in range(5):
            db_manager_with_multi_step_test_table.execute_update(
                "INSERT INTO test_multi_step (name, value) VALUES (:name, :value)",
                {"name": f"User{i}", "value": i * 10}
            )

        # 执行影响多行的操作
        sql_steps = [
            ("UPDATE test_multi_step SET value = value + 100 WHERE name LIKE 'User%'", None),
            ("DELETE FROM test_multi_step WHERE value > 100", None),
        ]

        result = db_manager_with_multi_step_test_table.execute_multi_step_transaction(
            sql_steps=sql_steps,
            commit=True
        )

        # 验证返回结果
        assert result['success'] is True
        assert result['steps_executed'] == 2
        assert result['affected_rows'][0] == 5  # UPDATE 影响了 5 行
        assert result['affected_rows'][1] == 4  # DELETE 影响了 4 行（value=0 的未被删除）
