"""Agent 上下文定义"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Optional, List
from uuid import uuid4, UUID


class IntentModel(BaseModel):
    """用户意图模型

    Attributes:
        type: 意图类型 (query/mutation/clarify)
        confidence: 置信度 (0-1)
        params: 提取的参数
        operation_id: 操作ID
        reasoning: 推理过程
        sql: 生成的 SQL
        need_clarify: 是否需要澄清
    """
    type: str = Field(..., description="意图类型")
    confidence: float = Field(default=0.0, description="置信度", ge=0.0, le=1.0)
    params: dict = Field(default_factory=dict, description="提取的参数")
    operation_id: Optional[str] = Field(default=None, description="操作ID")
    reasoning: str = Field(default="", description="推理过程")
    sql: Optional[str] = Field(default=None, description="生成的 SQL")
    need_clarify: bool = Field(default=False, description="是否需要澄清")


class AgentContext(BaseModel):
    """Agent 执行上下文

    Attributes:
        user_input: 用户原始输入
        trace_id: 追踪ID (自动生成 UUID)
        step_history: 步骤历史记录
        intent: 解析后的意图 (可选)
        schema_context: Schema 上下文 (可选)
        is_safe: 安全检查结果 (可选)
        preview_data: 预览数据 (可选)
        execution_result: 执行结果 (可选)
    """
    model_config = ConfigDict(json_encoders={})

    user_input: str = Field(..., description="用户原始输入")
    trace_id: UUID = Field(default_factory=uuid4, description="追踪ID")
    step_history: List[str] = Field(default_factory=list, description="步骤历史记录")
    intent: Optional[IntentModel] = Field(default=None, description="解析后的意图")
    schema_context: Optional[str] = Field(default=None, description="Schema 上下文")
    is_safe: Optional[bool] = Field(default=None, description="安全检查结果")
    preview_data: Optional[Any] = Field(default=None, description="预览数据")
    execution_result: Optional[Any] = Field(default=None, description="执行结果")
