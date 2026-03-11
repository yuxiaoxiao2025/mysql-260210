"""Security Agent 单元测试"""
import pytest
from src.agents.impl.security_agent import SecurityAgent
from src.agents.config import SecurityAgentConfig
from src.agents.context import AgentContext, IntentModel


class TestSecurityAgent:
    """Security Agent 测试类"""

    def setup_method(self):
        """测试前置设置"""
        self.agent = SecurityAgent(SecurityAgentConfig(name="sec"))

    def test_security_real_logic_drop_table(self):
        """测试 DROP TABLE 语句被拦截"""
        context = AgentContext(user_input="drop table")
        context.intent = IntentModel(type="mutation", sql="DROP TABLE users")

        result = self.agent.run(context)
        assert result.success is False
        assert "drop" in result.message.lower()
        assert context.is_safe is False

    def test_security_real_logic_alter_table(self):
        """测试 ALTER TABLE 语句被拦截"""
        context = AgentContext(user_input="alter table")
        context.intent = IntentModel(type="mutation", sql="ALTER TABLE users ADD COLUMN age INT")

        result = self.agent.run(context)
        assert result.success is False
        assert "alter" in result.message.lower()
        assert context.is_safe is False

    def test_security_real_logic_truncate(self):
        """测试 TRUNCATE 语句被拦截"""
        context = AgentContext(user_input="truncate table")
        context.intent = IntentModel(type="mutation", sql="TRUNCATE TABLE users")

        result = self.agent.run(context)
        assert result.success is False
        assert "truncate" in result.message.lower()
        assert context.is_safe is False

    def test_security_safe_update(self):
        """测试安全的 UPDATE 语句通过"""
        context = AgentContext(user_input="update user")
        context.intent = IntentModel(type="mutation", sql="UPDATE users SET name='test' WHERE id=1")

        result = self.agent.run(context)
        assert result.success is True
        assert context.is_safe is True

    def test_security_safe_insert(self):
        """测试安全的 INSERT 语句通过"""
        context = AgentContext(user_input="insert user")
        context.intent = IntentModel(type="mutation", sql="INSERT INTO users (name) VALUES ('test')")

        result = self.agent.run(context)
        assert result.success is True
        assert context.is_safe is True

    def test_security_safe_delete(self):
        """测试安全的 DELETE 语句通过"""
        context = AgentContext(user_input="delete user")
        context.intent = IntentModel(type="mutation", sql="DELETE FROM users WHERE id=1")

        result = self.agent.run(context)
        assert result.success is True
        assert context.is_safe is True

    def test_security_safe_select(self):
        """测试安全的 SELECT 语句通过"""
        context = AgentContext(user_input="select users")
        context.intent = IntentModel(type="query", sql="SELECT * FROM users WHERE id=1")

        result = self.agent.run(context)
        assert result.success is True
        assert context.is_safe is True

    def test_security_direct_query_dml_blocked(self):
        """测试直接 SQL 模式下 DML 语句被拦截"""
        context = AgentContext(user_input="update user")
        context.intent = IntentModel(type="query", sql="UPDATE users SET name='test' WHERE id=1")

        result = self.agent.run(context)
        assert result.success is False
        assert "直接 SQL 模式仅允许 SELECT 查询" in result.message
        assert context.is_safe is False

    def test_security_no_intent_sql(self):
        """测试无 SQL 时跳过检查"""
        context = AgentContext(user_input="hello")
        context.intent = IntentModel(type="unknown", sql=None)

        result = self.agent.run(context)
        assert result.success is True
        assert context.is_safe is None  # 未设置安全检查标志

    def test_security_multiple_statements_blocked(self):
        """测试多语句被拦截（当没有危险关键字时通过多语句检测拦截）"""
        context = AgentContext(user_input="select users")
        context.intent = IntentModel(type="query", sql="SELECT * FROM users; SELECT * FROM logs")

        result = self.agent.run(context)
        assert result.success is False
        assert "直接 SQL 模式不允许多语句" in result.message
        assert context.is_safe is False

    def test_security_risky_select_into_outfile_blocked(self):
        """测试 INTO OUTFILE 被拦截"""
        context = AgentContext(user_input="export data")
        context.intent = IntentModel(type="query", sql="SELECT * FROM users INTO OUTFILE '/tmp/data.txt'")

        result = self.agent.run(context)
        assert result.success is False
        assert "禁止" in result.message
        assert context.is_safe is False

    def test_security_risky_select_sleep_blocked(self):
        """测试 SLEEP 函数被拦截"""
        context = AgentContext(user_input="slow query")
        context.intent = IntentModel(type="query", sql="SELECT * FROM users WHERE SLEEP(5)")

        result = self.agent.run(context)
        assert result.success is False
        assert "禁止" in result.message
        assert context.is_safe is False

    def test_security_risky_select_benchmark_blocked(self):
        """测试 BENCHMARK 函数被拦截"""
        context = AgentContext(user_input="benchmark")
        context.intent = IntentModel(type="query", sql="SELECT BENCHMARK(1000000, MD5('test'))")

        result = self.agent.run(context)
        assert result.success is False
        assert "禁止" in result.message
        assert context.is_safe is False

    def test_security_case_insensitive(self):
        """测试关键字检测大小写不敏感"""
        context = AgentContext(user_input="DROP table")
        context.intent = IntentModel(type="mutation", sql="DROP TABLE users")

        result = self.agent.run(context)
        assert result.success is False
        assert "drop" in result.message.lower()
        assert context.is_safe is False

    def test_security_strip_literals_and_comments(self):
        """测试字符串和注释被正确处理"""
        context = AgentContext(user_input="safe query")
        # 字符串中包含 drop 关键字
        context.intent = IntentModel(type="mutation", sql="UPDATE users SET name='drop table' WHERE id=1")

        result = self.agent.run(context)
        assert result.success is True
        assert context.is_safe is True
