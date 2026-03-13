import os
import json
import logging
import dashscope
from dashscope import Generation
from typing import Dict, Optional, Any, TYPE_CHECKING, AsyncGenerator

if TYPE_CHECKING:
    from src.metadata.retrieval_agent import RetrievalAgent
    from src.metadata.retrieval_models import TableRetrievalResult

from src.context import SlotTracker, QueryRewriter
from src.constraint import TableValidator
from src.monitoring.metrics_collector import get_metrics_collector, CacheMetrics

logger = logging.getLogger(__name__)


class StructuredOutputError(Exception):
    """结构化输出相关错误"""
    pass


class JsonParseError(StructuredOutputError):
    """JSON 解析错误"""
    def __init__(self, message: str, raw_content: str = None):
        super().__init__(message)
        self.raw_content = raw_content

    def __str__(self):
        base_msg = super().__str__()
        if self.raw_content:
            return f"{base_msg} | Raw content: {self.raw_content[:200]}"
        return base_msg


class LLMClient:
    """LLM 客户端 - 支持结构化输出、流式输出、深度思考和上下文缓存"""

    # 配置开关默认值
    DEFAULT_ENABLE_STRUCTURED_OUTPUT = False
    DEFAULT_ENABLE_THINKING = False
    DEFAULT_ENABLE_STREAM = False
    DEFAULT_ENABLE_PROMPT_CACHE = False

    def __init__(self, allowed_tables: Optional[list[str]] = None):
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.client = self._build_chat_client()
        self.last_result = None  # Store last result for transaction preview
        self.conversation_history = []  # Store conversation history (max 5 rounds)
        self.max_history_rounds = 5  # Maximum number of conversation rounds to keep
        self.retrieval_agent: Optional["RetrievalAgent"] = None  # Lazy load

        # 配置开关（从环境变量读取，默认关闭以保持兼容）
        self.enable_structured_output = self._get_env_bool(
            "ENABLE_STRUCTURED_OUTPUT", self.DEFAULT_ENABLE_STRUCTURED_OUTPUT
        )
        self.enable_thinking = self._get_env_bool(
            "ENABLE_THINKING", self.DEFAULT_ENABLE_THINKING
        )
        self.enable_stream = self._get_env_bool(
            "ENABLE_STREAM", self.DEFAULT_ENABLE_STREAM
        )
        self.enable_prompt_cache = self._get_env_bool(
            "ENABLE_PROMPT_CACHE", self.DEFAULT_ENABLE_PROMPT_CACHE
        )

        # 记录配置状态
        logger.info(
            f"LLMClient initialized with config: "
            f"structured_output={self.enable_structured_output}, "
            f"thinking={self.enable_thinking}, "
            f"stream={self.enable_stream}, "
            f"prompt_cache={self.enable_prompt_cache}"
        )

        # Context enhancement components
        self.slot_tracker = SlotTracker()
        self.query_rewriter = QueryRewriter()

        # Table validation
        self.table_validator: Optional[TableValidator] = None
        self._user_provided_tables: Optional[list[str]] = None
        if allowed_tables:
            self.table_validator = TableValidator(allowed_tables)
            self._user_provided_tables = allowed_tables.copy()

        # Metrics collector for cache tracking
        self._metrics_collector = get_metrics_collector()

        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY not found in environment variables.")
            print("⚠️  Warning: DASHSCOPE_API_KEY not found in environment variables.")
        else:
            dashscope.api_key = self.api_key

    def _build_chat_client(self):
        """构建 OpenAI 兼容风格客户端（优先用于 chat_stream）。"""
        if not self.api_key:
            return None
        try:
            from openai import OpenAI
            return OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
        except Exception:
            # 兼容无 openai 依赖场景：保留 None，chat_stream 会自动降级到 Generation.call
            return None

    def _get_env_bool(self, key: str, default: bool = False) -> bool:
        """从环境变量读取布尔值配置"""
        value = os.getenv(key, "").lower()
        if value in ("1", "true", "yes", "on"):
            return True
        if value in ("0", "false", "no", "off"):
            return False
        return default

    def generate_sql(self, user_query: str, schema_context: str, error_context: Optional[str] = None, context: Optional[dict[str, str]] = None) -> dict[str, Any]:
        """
        Translate NL to SQL.
        """
        # Step 1: Extract slots from query and merge with provided context
        extracted_slots = self.slot_tracker.extract(user_query)
        merged_context = {**(context or {}), **extracted_slots}

        # Step 2: Rewrite query using context (pronoun substitution)
        rewritten_query = self.query_rewriter.rewrite(user_query, merged_context)
        if rewritten_query != user_query:
            logger.info(f"Query rewritten: '{user_query}' -> '{rewritten_query}'")

        # Step 3: Get allowed tables (validation logic)
        allowed_tables_from_retrieval = self._get_allowed_tables_from_retrieval()
        if allowed_tables_from_retrieval and not self._user_provided_tables:
            self.table_validator = TableValidator(allowed_tables_from_retrieval)
            logger.debug(f"Auto-created TableValidator with {len(allowed_tables_from_retrieval)} tables")

        # Optional: Enhance schema with retrieval
        retrieval_context = ""
        pipeline = self._get_retrieval_pipeline()
        if pipeline:
            try:
                result = pipeline.search(rewritten_query, top_k=5)
                retrieval_context = "\n" + self._build_retrieval_context(result)
            except Exception as e:
                logger.warning(f"Pipeline retrieval enhancement failed: {e}")

        if not retrieval_context:
            agent = self._get_retrieval_agent()
            if agent and agent.graph:
                try:
                    from src.metadata.retrieval_models import RetrievalRequest, RetrievalLevel
                    result = agent.search(RetrievalRequest(query=rewritten_query, level=RetrievalLevel.TABLE, top_k=5))
                    retrieval_context = "\n" + self._build_retrieval_context(result)
                except Exception as e:
                    logger.warning(f"Retrieval enhancement failed: {e}")

        # Construct System Message (Static Prefix for Caching)
        system_content = f"""You are a MySQL expert. Your task is to translate the user's natural language query into an executable SQL statement.

### Schema Information
{schema_context}{retrieval_context}

### Instructions
1. Generate a valid MySQL SQL query based on the schema and user request.
2. If tables are in different databases, use database prefix.
3. Use JOINs if necessary.
4. **IMPORTANT**: Rename output columns to friendly Chinese names using `AS`.
5. Suggest a filename and sheet name.
6. **Intent**: "query" for SELECT, "mutation" for INSERT/UPDATE/DELETE.
7. For mutations, provide `preview_sql`, `key_columns`, and `warnings`.

### Output Format
Return ONLY a JSON object with keys: `sql`, `filename`, `sheet_name`, `reasoning`, `intent`, `preview_sql`, `key_columns`, `warnings`."""

        messages = [{'role': 'system', 'content': system_content}]

        # 如果启用缓存，在 system message 上添加 cache_control
        if self.enable_prompt_cache:
            messages[0]['cache_control'] = {"type": "ephemeral"}
            logger.debug("在 system message 上启用缓存控制")

        # Add Conversation History (Native Messages)
        if self.conversation_history:
            for prev_query, prev_result in self.conversation_history:
                messages.append({'role': 'user', 'content': prev_query})
                if isinstance(prev_result, dict):
                    # Convert result summary to a string representation for context
                    content = f"SQL: {prev_result.get('sql', 'N/A')}\nReasoning: {prev_result.get('reasoning', 'N/A')}"
                    if not prev_result.get('success'):
                        content = f"Error: {prev_result.get('error', 'Unknown error')}"
                    messages.append({'role': 'assistant', 'content': content})

        # Add Current User Query
        user_content = f"User Query: {rewritten_query}"
        if error_context:
            user_content += f"\n\n### Error from Previous Attempt\n{error_context}"
        
        messages.append({'role': 'user', 'content': user_content})

        try:
            # 构建 API 调用参数
            api_params = {
                'model': 'qwen-plus',
                'messages': messages,
                'result_format': 'message',
            }

            # 深度思考模式
            if self.enable_thinking:
                api_params['stream'] = True
                api_params['enable_thinking'] = True
                logger.debug("启用深度思考模式 (enable_thinking + stream)")
            # 非思考模式下启用结构化输出
            elif self.enable_structured_output:
                api_params['response_format'] = {'type': 'json_object'}
                logger.debug("启用结构化输出模式 (json_object)")

            response = Generation.call(**api_params)

            # 处理流式响应（thinking 模式）
            if self.enable_thinking:
                content = self._handle_thinking_stream(response)
                # 尝试解析 JSON，如果失败则使用双阶段修复
                try:
                    result = self._parse_json_response(content)
                except JsonParseError:
                    logger.warning("Thinking 模式 JSON 解析失败，进入修复流程")
                    result = self._fix_json_with_thinking(content, schema_context, rewritten_query)

                # Apply defaults
                result.setdefault('intent', 'query')
                result.setdefault('preview_sql', None)
                result.setdefault('key_columns', [])
                result.setdefault('warnings', [])

                # Step 4: Validate SQL
                sql = result.get('sql', '')
                if sql and self.table_validator:
                    is_valid, error_msg = self.table_validator.validate(sql)
                    if not is_valid:
                        logger.warning(f"Table validation failed: {error_msg}")
                        result['warnings'].append(f"Table validation: {error_msg}")
                        return {
                            'sql': None,
                            'filename': None,
                            'sheet_name': None,
                            'reasoning': f"Generated SQL contains unauthorized tables: {error_msg}",
                            'intent': 'error',
                            'preview_sql': None,
                            'key_columns': [],
                            'warnings': [f"Table validation failed: {error_msg}"]
                        }

                self.last_result = result
                self._add_to_history(user_query, result)
                return result
            else:
                # 非流式响应处理
                if response.status_code == 200:
                    content = response.output.choices[0].message.content
                    result = self._parse_json_response(content)

                    # 记录缓存指标
                    if self.enable_prompt_cache and hasattr(response, 'usage'):
                        self._record_cache_metrics(response, 'generate_sql')

                    # Apply defaults
                    result.setdefault('intent', 'query')
                    result.setdefault('preview_sql', None)
                    result.setdefault('key_columns', [])
                    result.setdefault('warnings', [])

                    # Step 4: Validate SQL
                    sql = result.get('sql', '')
                    if sql and self.table_validator:
                        is_valid, error_msg = self.table_validator.validate(sql)
                        if not is_valid:
                            logger.warning(f"Table validation failed: {error_msg}")
                            result['warnings'].append(f"Table validation: {error_msg}")
                            return {
                                'sql': None,
                                'filename': None,
                                'sheet_name': None,
                                'reasoning': f"Generated SQL contains unauthorized tables: {error_msg}",
                                'intent': 'error',
                                'preview_sql': None,
                                'key_columns': [],
                                'warnings': [f"Table validation failed: {error_msg}"]
                            }

                    self.last_result = result
                    self._add_to_history(user_query, result)
                    return result
                else:
                    raise Exception(f"API Error: {response.code} - {response.message}")
                
        except JsonParseError as e:
            logger.error(f"JSON 解析错误: {e}")
            raise JsonParseError(f"LLM generation failed: {str(e)}", raw_content=e.raw_content) from e
        except Exception as e:
            raise Exception(f"LLM generation failed: {str(e)}")
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """
        解析 JSON 响应，处理可能的解析错误
        支持双阶段修复：先尝试直接解析，失败则尝试清理后解析

        Args:
            content: API 返回的原始内容

        Returns:
            解析后的字典

        Raises:
            JsonParseError: 当 JSON 解析失败时
        """
        # 第一阶段：直接解析
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass  # 继续第二阶段

        # 第二阶段：清理后解析
        try:
            cleaned_content = content.strip()
            # 移除代码块标记
            if cleaned_content.startswith('```json'):
                cleaned_content = cleaned_content[7:]
            elif cleaned_content.startswith('```'):
                cleaned_content = cleaned_content[3:]
            if cleaned_content.endswith('```'):
                cleaned_content = cleaned_content[:-3]
            cleaned_content = cleaned_content.strip()

            # 尝试找到 JSON 对象
            start = cleaned_content.find('{')
            end = cleaned_content.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = cleaned_content[start:end + 1]
                return json.loads(json_str)

            # 如果找不到对象，尝试解析数组
            start = cleaned_content.find('[')
            end = cleaned_content.rfind(']')
            if start != -1 and end != -1 and end > start:
                json_str = cleaned_content[start:end + 1]
                return json.loads(json_str)

            raise json.JSONDecodeError("无法找到有效的 JSON 内容", cleaned_content, 0)

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.error(f"原始内容: {content[:500]}")
            raise JsonParseError(
                f"JSON parse error: {str(e)}",
                raw_content=content[:500]
            ) from e

    def _fix_json_with_thinking(self, raw_content: str, schema_context: str, user_query: str) -> Dict[str, Any]:
        """
        当 thinking 模式返回非标准 JSON 时，使用非 thinking 模式修复为标准 JSON
        这是双阶段 JSON 修复流程

        Args:
            raw_content: thinking 模式的原始输出（可能包含思考过程和 JSON）
            schema_context: 数据库 schema 上下文
            user_query: 用户查询

        Returns:
            标准格式的 JSON 结果
        """
        logger.info("进入双阶段 JSON 修复流程")

        # 尝试从原始内容中提取 JSON
        result = self._extract_json_from_thinking_output(raw_content)
        if result:
            logger.debug("从 thinking 输出中提取 JSON 成功")
            return result

        # 如果提取失败，使用非 thinking 模式重新生成
        logger.info("提取失败，使用非 thinking 模式重新生成标准 JSON")

        fix_prompt = f"""请将以下内容转换为标准 JSON 格式。

原始内容:
{raw_content[:2000]}

要求:
1. 提取原始内容中的 SQL 查询
2. 返回标准的 JSON 对象，包含以下字段: sql, filename, sheet_name, reasoning, intent, preview_sql, key_columns, warnings
3. 只返回 JSON，不要其他内容

输出格式:
{{"sql": "...", "filename": "...", "sheet_name": "...", "reasoning": "...", "intent": "query", "preview_sql": null, "key_columns": [], "warnings": []}}
"""

        try:
            # 使用非 thinking 模式重新生成
            response = Generation.call(
                model='qwen-plus',
                messages=[
                    {'role': 'system', 'content': 'You are a JSON formatter. Return only valid JSON.'},
                    {'role': 'user', 'content': fix_prompt}
                ],
                result_format='message',
                response_format={'type': 'json_object'}
            )

            if response.status_code == 200:
                content = response.output.choices[0].message.content
                result = self._parse_json_response(content)
                logger.info("JSON 修复成功")
                return result
            else:
                raise JsonParseError(f"修复失败: API 错误 {response.code}")

        except Exception as e:
            logger.error(f"JSON 修复失败: {e}")
            # 返回一个默认的失败结果
            return {
                "sql": None,
                "filename": None,
                "sheet_name": None,
                "reasoning": f"JSON 修复失败: {str(e)}",
                "intent": "error",
                "preview_sql": None,
                "key_columns": [],
                "warnings": [f"JSON 修复失败: {str(e)}"]
            }

    def _extract_json_from_thinking_output(self, content: str) -> Optional[Dict[str, Any]]:
        """
        从 thinking 模式的输出中提取 JSON

        Args:
            content: thinking 模式的输出内容

        Returns:
            提取的 JSON 字典，如果提取失败返回 None
        """
        try:
            # 尝试找到 JSON 对象
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = content[start:end + 1]
                return json.loads(json_str)

            # 尝试找到 JSON 数组
            start = content.find('[')
            end = content.rfind(']')
            if start != -1 and end != -1 and end > start:
                json_str = content[start:end + 1]
                return json.loads(json_str)

            return None
        except json.JSONDecodeError:
            return None

    def _handle_thinking_stream(self, response) -> str:
        """
        处理 thinking 模式的流式响应

        Args:
            response: 流式响应对象

        Returns:
            合并后的内容字符串
        """
        content_parts = []
        reasoning_content = []

        try:
            # 处理流式响应
            for chunk in response:
                if hasattr(chunk, 'output') and chunk.output:
                    if hasattr(chunk.output, 'choices') and chunk.output.choices:
                        choice = chunk.output.choices[0]
                        if hasattr(choice, 'message') and choice.message:
                            message = choice.message
                            # 收集内容
                            if hasattr(message, 'content') and message.content:
                                content_val = message.content if isinstance(message.content, str) else str(message.content)
                                content_parts.append(content_val)
                            # 收集推理过程
                            if hasattr(message, 'reasoning_content') and message.reasoning_content:
                                reasoning_val = message.reasoning_content if isinstance(message.reasoning_content, str) else str(message.reasoning_content)
                                reasoning_content.append(reasoning_val)

            full_content = ''.join(content_parts)
            full_reasoning = ''.join(reasoning_content)

            logger.debug(f"Thinking 模式收集内容长度: {len(full_content)}")
            logger.debug(f"Thinking 模式收集推理长度: {len(full_reasoning)}")

            return full_content

        except Exception as e:
            logger.error(f"处理 thinking 流式响应失败: {e}")
            raise

    def _record_cache_metrics(self, response, operation: str):
        """
        记录缓存指标

        Args:
            response: API 响应对象
            operation: 操作类型
        """
        try:
            usage = getattr(response, 'usage', None)
            if not usage:
                return

            # 提取 token 使用信息
            total_input_tokens = getattr(usage, 'input_tokens', 0)
            total_output_tokens = getattr(usage, 'output_tokens', 0)

            # 检查缓存命中情况
            # DashScope API 在 usage.prompt_tokens_details 中提供缓存信息
            cached_tokens = 0
            cache_creation_tokens = 0

            prompt_tokens_details = getattr(usage, 'prompt_tokens_details', None)
            if prompt_tokens_details:
                cached_tokens = getattr(prompt_tokens_details, 'cached_tokens', 0)
                cache_creation_tokens = getattr(prompt_tokens_details, 'cache_creation_input_tokens', 0)

            # 判断缓存是否命中
            cache_hit = cached_tokens > 0

            # 记录指标
            self._metrics_collector.record_cache_metrics(
                operation=operation,
                cache_hit=cache_hit,
                cache_creation_input_tokens=cache_creation_tokens,
                cached_tokens=cached_tokens,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                model='qwen-plus'
            )

            logger.debug(
                f"缓存指标: operation={operation}, cache_hit={cache_hit}, "
                f"cached_tokens={cached_tokens}, creation_tokens={cache_creation_tokens}"
            )

        except Exception as e:
            logger.warning(f"记录缓存指标失败: {e}")

    def _add_to_history(self, user_query, result):
        """
        Add query and result to conversation history.
        Maintains max_history_rounds by removing oldest entries.
        """
        # Store summary of result (not full SQL to save tokens)
        result_summary = {
            'sql': result.get('sql', ''),
            'reasoning': result.get('reasoning', ''),
            'success': True
        }
        
        # Add new entry
        self.conversation_history.append((user_query, result_summary))
        
        # Trim to max rounds
        if len(self.conversation_history) > self.max_history_rounds:
            self.conversation_history = self.conversation_history[-self.max_history_rounds:]
    
    def add_error_to_history(self, user_query, error_message):
        """
        Add failed query with error to conversation history.
        """
        error_summary = {
            'error': error_message,
            'success': False
        }
        
        # Add new entry
        self.conversation_history.append((user_query, error_summary))
        
        # Trim to max rounds
        if len(self.conversation_history) > self.max_history_rounds:
            self.conversation_history = self.conversation_history[-self.max_history_rounds:]
    
    def clear_history(self):
        """
        Clear conversation history.
        """
        self.conversation_history = []

    def _get_retrieval_agent(self) -> Optional["RetrievalAgent"]:
        """
        Lazy load retrieval agent for schema enhancement.

        Returns:
            RetrievalAgent instance if available, None otherwise.
        """
        if os.getenv("DISABLE_RETRIEVAL") == "1":
            logger.info("Retrieval enhancement disabled by environment flag.")
            return None
        if self.retrieval_agent is None:
            try:
                from src.metadata.retrieval_agent import RetrievalAgent
                self.retrieval_agent = RetrievalAgent(env="dev")
                logger.debug("RetrievalAgent lazy loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load RetrievalAgent: {e}")
                self.retrieval_agent = None
        return self.retrieval_agent

    def _get_retrieval_pipeline(self) -> Optional[Any]:
        """
        Lazy load retrieval pipeline with reranking support.

        Returns:
            RetrievalPipeline instance if available, None otherwise.
        """
        if os.getenv("DISABLE_RETRIEVAL") == "1":
            logger.debug("Retrieval enhancement disabled by environment flag.")
            return None
        if not hasattr(self, "_retrieval_pipeline"):
            self._retrieval_pipeline = None
        if self._retrieval_pipeline is None:
            try:
                from src.metadata.retrieval_pipeline import RetrievalPipeline
                self._retrieval_pipeline = RetrievalPipeline(budget_ms=500, env="dev")
                logger.debug("RetrievalPipeline lazy loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load RetrievalPipeline: {e}")
                self._retrieval_pipeline = None
        return self._retrieval_pipeline

    def _build_retrieval_context(self, result: "TableRetrievalResult") -> str:
        """
        Build schema context from retrieval results.

        Args:
            result: TableRetrievalResult from semantic search.

        Returns:
            Formatted string with retrieved table information.
        """
        lines = ["### Related Tables (Retrieved by Semantic Search)"]
        for match in result.matches[:3]:  # Top 3 matches
            lines.append(
                f"- {match.table_name}: {match.description} (score: {match.similarity_score:.2f})"
            )
        return "\n".join(lines)

    def _get_allowed_tables_from_retrieval(self) -> Optional[list[str]]:
        """
        Get allowed table names from retrieval pipeline or agent.

        Returns:
            List of table names if retrieval is available, None otherwise.
        """
        # Try pipeline first
        pipeline = self._get_retrieval_pipeline()
        if pipeline:
            try:
                # Try to get tables from pipeline's graph store or index
                if hasattr(pipeline, 'graph_store') and pipeline.graph_store:
                    tables = list(pipeline.graph_store._nodes.keys())
                    if tables:
                        return tables
                # Try to get from indexer if available
                if hasattr(pipeline, 'indexer') and pipeline.indexer:
                    if hasattr(pipeline.indexer, 'get_all_tables'):
                        return pipeline.indexer.get_all_tables()
            except Exception as e:
                logger.debug(f"Failed to get tables from pipeline: {e}")

        # Fall back to agent
        agent = self._get_retrieval_agent()
        if agent and agent.graph:
            try:
                # Get all table nodes from the graph
                tables = [node_id for node_id in agent.graph.nodes if node_id.startswith('table:')]
                # Remove prefix
                return [t.replace('table:', '') for t in tables]
            except Exception as e:
                logger.debug(f"Failed to get tables from agent: {e}")

        return None

    def generate_sql_stream(
        self,
        user_query: str,
        schema_context: str,
        error_context: Optional[str] = None,
        context: Optional[dict[str, str]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式生成 SQL

        Args:
            user_query: 用户自然语言查询
            schema_context: 数据库 schema 上下文
            error_context: 可选的错误上下文（用于重试）
            context: 可选的上下文字典

        Yields:
            包含增量内容的字典
        """
        # Step 1: Extract slots from query and merge with provided context
        extracted_slots = self.slot_tracker.extract(user_query)
        merged_context = {**(context or {}), **extracted_slots}

        # Step 2: Rewrite query using context (pronoun substitution)
        rewritten_query = self.query_rewriter.rewrite(user_query, merged_context)
        if rewritten_query != user_query:
            logger.info(f"Query rewritten: '{user_query}' -> '{rewritten_query}'")

        # Construct System Message (Static Prefix for Caching)
        system_content = f"""You are a MySQL expert. Your task is to translate the user's natural language query into an executable SQL statement.

### Schema Information
{schema_context}

### Instructions
1. Generate a valid MySQL SQL query based on the schema and user request.
2. If tables are in different databases, use database prefix.
3. Use JOINs if necessary.
4. **IMPORTANT**: Rename output columns to friendly Chinese names using `AS`.
5. Suggest a filename and sheet name.
6. **Intent**: "query" for SELECT, "mutation" for INSERT/UPDATE/DELETE.
7. For mutations, provide `preview_sql`, `key_columns`, and `warnings`.

### Output Format
Return ONLY a JSON object with keys: `sql`, `filename`, `sheet_name`, `reasoning`, `intent`, `preview_sql`, `key_columns`, `warnings`."""

        messages = [{'role': 'system', 'content': system_content}]

        # 如果启用缓存，在 system message 上添加 cache_control
        if self.enable_prompt_cache:
            messages[0]['cache_control'] = {"type": "ephemeral"}
            logger.debug("流式生成启用缓存控制")

        # Add Conversation History (Native Messages)
        if self.conversation_history:
            for prev_query, prev_result in self.conversation_history:
                messages.append({'role': 'user', 'content': prev_query})
                if isinstance(prev_result, dict):
                    content = f"SQL: {prev_result.get('sql', 'N/A')}\nReasoning: {prev_result.get('reasoning', 'N/A')}" if prev_result.get('success') else f"Error: {prev_result.get('error', 'Unknown error')}"
                    messages.append({'role': 'assistant', 'content': content})

        # Add Current User Query
        user_content = f"User Query: {rewritten_query}"
        if error_context:
            user_content += f"\n\n### Error from Previous Attempt\n{error_context}"
        messages.append({'role': 'user', 'content': user_content})

        try:
            # 构建流式 API 调用参数
            api_params = {
                'model': 'qwen-plus',
                'messages': messages,
                'result_format': 'message',
                'stream': True,
            }

            # 启用 thinking 模式
            if self.enable_thinking:
                api_params['enable_thinking'] = True
                logger.debug("流式生成启用 thinking 模式")

            response = Generation.call(**api_params)

            full_content = []
            full_reasoning = []
            usage_info = {}

            for chunk in response:
                try:
                    if hasattr(chunk, 'output') and chunk.output:
                        if hasattr(chunk.output, 'choices') and chunk.output.choices:
                            choice = chunk.output.choices[0]
                            if hasattr(choice, 'message') and choice.message:
                                message = choice.message
                                delta = {}

                                if hasattr(message, 'content') and message.content:
                                    content_val = message.content if isinstance(message.content, str) else str(message.content)
                                    full_content.append(content_val)
                                    delta['content'] = content_val

                                if hasattr(message, 'reasoning_content') and message.reasoning_content:
                                    reasoning_val = message.reasoning_content if isinstance(message.reasoning_content, str) else str(message.reasoning_content)
                                    full_reasoning.append(reasoning_val)
                                    delta['reasoning'] = reasoning_val

                                if delta:
                                    yield delta

                    # 收集 usage 信息
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage_info = {
                            'input_tokens': getattr(chunk.usage, 'input_tokens', 0),
                            'output_tokens': getattr(chunk.usage, 'output_tokens', 0),
                        }
                        prompt_details = getattr(chunk.usage, 'prompt_tokens_details', None)
                        if prompt_details:
                            usage_info['cached_tokens'] = getattr(prompt_details, 'cached_tokens', 0)

                except Exception as e:
                    logger.warning(f"处理流式 chunk 失败: {e}")
                    continue

            # 发送最终结果
            final_content = ''.join(full_content)
            final_reasoning = ''.join(full_reasoning)

            # 尝试解析 JSON
            try:
                result = self._parse_json_response(final_content)
            except JsonParseError:
                logger.warning("流式输出 JSON 解析失败")
                result = {'raw_content': final_content}

            yield {
                'done': True,
                'result': result,
                'reasoning': final_reasoning if self.enable_thinking else None,
                'usage': usage_info
            }

        except Exception as e:
            logger.error(f"流式生成失败: {e}")
            yield {'error': str(e)}

    def chat_stream(self, messages: list[dict], enable_thinking: bool = False):
        """
        Stream chat response with thinking support

        Args:
            messages: List of message dicts
            enable_thinking: Whether to enable thinking mode

        Yields:
            Dict with type ('thinking', 'content', 'error', 'usage') and content
        """
        # 前置检查
        if not messages:
            logger.error("chat_stream: messages is empty")
            yield {"type": "error", "content": "消息列表为空"}
            return

        if not self.api_key:
            logger.error("chat_stream: API key not configured")
            yield {"type": "error", "content": "API 密钥未配置，请设置 DASHSCOPE_API_KEY 环境变量"}
            return

        try:
            logger.info(f"chat_stream: calling LLM with {len(messages)} messages")
            if self.client:
                response = self.client.chat.completions.create(
                    model="qwen-plus",
                    messages=messages,
                    stream=True,
                    extra_body={"enable_thinking": enable_thinking},
                    stream_options={"include_usage": True}
                )
            else:
                api_params = {
                    'model': 'qwen-plus',
                    'messages': messages,
                    'result_format': 'message',
                    'stream': True,
                }
                if enable_thinking:
                    api_params['enable_thinking'] = True
                response = Generation.call(**api_params)

            # 跟踪是否有实际输出
            has_content = False

            for chunk in response:
                choice = self._extract_stream_choice(chunk)
                if choice:
                    thinking = getattr(choice, "reasoning_content", None)
                    content = getattr(choice, "content", None)
                    if thinking:
                        has_content = True
                        yield {"type": "thinking", "content": str(thinking)}
                    if content:
                        has_content = True
                        yield {"type": "content", "content": str(content)}

                usage = getattr(chunk, "usage", None)
                if usage and hasattr(usage, "input_tokens"):
                    raw_input_tokens = getattr(usage, 'input_tokens', None)
                    raw_output_tokens = getattr(usage, 'output_tokens', None)
                    if not isinstance(raw_input_tokens, int) and not isinstance(raw_output_tokens, int):
                        continue

                    input_tokens = raw_input_tokens if isinstance(raw_input_tokens, int) else 0
                    output_tokens = raw_output_tokens if isinstance(raw_output_tokens, int) else 0
                    if not isinstance(input_tokens, int):
                        input_tokens = 0
                    if not isinstance(output_tokens, int):
                        output_tokens = 0
                    usage_info = {
                        'input_tokens': input_tokens,
                        'output_tokens': output_tokens,
                    }
                    prompt_details = getattr(usage, 'prompt_tokens_details', None)
                    if prompt_details:
                        cached_tokens = getattr(prompt_details, 'cached_tokens', 0)
                        usage_info['cached_tokens'] = cached_tokens if isinstance(cached_tokens, int) else 0

                    self._metrics_collector.record_cache_metrics(
                        operation="chat_stream",
                        cache_hit=usage_info.get("cached_tokens", 0) > 0,
                        cached_tokens=usage_info.get("cached_tokens", 0),
                        total_input_tokens=usage_info["input_tokens"],
                        total_output_tokens=usage_info["output_tokens"],
                        model="qwen-plus"
                    )
                    yield {"type": "usage", "usage": usage_info}

            # 检查是否有输出，无输出时返回降级消息
            if not has_content:
                logger.warning("chat_stream: No content generated from LLM")
                yield {"type": "content", "content": "抱歉，我暂时无法回答这个问题。请稍后再试。"}
        except Exception as e:
            logger.error(f"Chat stream failed: {e}", exc_info=True)
            yield {"type": "error", "content": f"对话服务暂时不可用：{str(e)}"}

    def _extract_stream_choice(self, chunk: Any):
        """兼容 OpenAI/DashScope 两种流式 chunk 结构，返回含 content/reasoning_content 的对象。"""
        if hasattr(chunk, "choices") and chunk.choices:
            delta = getattr(chunk.choices[0], "delta", None)
            if delta:
                return delta
            message = getattr(chunk.choices[0], "message", None)
            if message:
                return message
        if hasattr(chunk, "output") and chunk.output and getattr(chunk.output, "choices", None):
            choice = chunk.output.choices[0]
            message = getattr(choice, "message", None)
            if message:
                return message
        return None

    def chat(self, user_input: str) -> str:
        """
        生成通用对话回复

        Args:
            user_input: 用户输入

        Returns:
            生成的回复文本
        """
        messages = [{'role': 'system', 'content': 'You are a helpful MySQL and data assistant. Answer user questions clearly and concisely.'}]
        
        # Add limited history context
        if self.conversation_history:
            for query, result in self.conversation_history[-3:]:
                messages.append({'role': 'user', 'content': query})
                if isinstance(result, dict) and 'summary' in result:
                    messages.append({'role': 'assistant', 'content': result['summary']})
                elif isinstance(result, dict) and 'sql' in result:
                    messages.append({'role': 'assistant', 'content': f"Generated SQL: {result['sql']}"})
        
        messages.append({'role': 'user', 'content': user_input})

        try:
            response = Generation.call(
                model='qwen-plus',
                messages=messages,
                result_format='message'
            )
            
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                return content
            else:
                logger.error(f"Chat API Error: {response.code} - {response.message}")
                return "抱歉，我现在无法回答这个问题。"
        except Exception as e:
            logger.error(f"Chat generation failed: {e}")
            return "抱歉，发生了一些错误。"

    def recognize_intent(self, user_query: str, operations_context: str,
                         enum_values: Optional[Dict[str, list]] = None) -> Dict[str, Any]:
        """
        识别用户意图，匹配操作模板并提取参数

        Args:
            user_query: 用户输入
            operations_context: 操作模板上下文（由 KnowledgeLoader 生成）
            enum_values: 可用的枚举值（如场库名称、操作员名称等）

        Returns:
            {
                "operation_id": "plate_distribute" | None,  # 匹配的操作ID
                "confidence": 0.95,  # 置信度 0-1
                "params": {  # 提取的参数
                    "plate": "沪ABC1234",
                    "park_name": "国际商务中心"
                },
                "fallback_sql": None,  # 如果没有匹配模板，生成的 SQL
                "reasoning": "用户提到'下发'和'场库'...",  # 推理过程
                "missing_params": ["operator_name"],  # 缺少的必需参数
                "suggestions": []  # 给用户的建议
            }
        """
        # 构建枚举值上下文
        enum_context = ""
        if enum_values:
            enum_context = "\n### Available Values (for validation and auto-complete)\n"
            for enum_name, values in enum_values.items():
                if values:
                    display_values = values[:20]  # 限制显示数量
                    enum_context += f"- {enum_name}: {', '.join(str(v) for v in display_values)}"
                    if len(values) > 20:
                        enum_context += f" ... (and {len(values) - 20} more)"
                    enum_context += "\n"

        prompt = f"""You are an intelligent assistant for a parking management system.
Your task is to understand the user's intent and match it to one of the predefined operation templates.

### Available Operations
{operations_context}
{enum_context}
### Instructions
1. Analyze the user's query and determine which operation they want to perform.
2. Extract parameter values from the query. Pay attention to:
   - Plate numbers (车牌): Format like "沪ABC1234"
   - Park names (场库): Must match one of the available values OR use "全部" for batch operations
     * When user says "所有园区", "全部园区", "所有场库", "全部场库", or simply "所有"/"全部", extract as "全部"
     * "全部" means distribute to ALL active parks
   - Operator names (操作员): Must match one of the available values
   - Dates: Parse relative dates like "30天内" to appropriate values
3. If a parameter value is mentioned but not in the available values list, still extract it but add a warning.
4. If the query doesn't match any operation template:
   - If it is a general question, greeting, or capability query (e.g., "What can you do?", "Hi", "Can you help me?"), return `operation_id: "general_chat"`.
   - If it is a knowledge question about tables or schema (e.g., "What is in table X?", "Does this table exist?"), return `operation_id: "knowledge_qa"`.
   - Otherwise, generate a fallback SQL query.
5. List any required parameters that are missing.

### Output Format
Return ONLY a JSON object with these keys:
- `operation_id`: The matched operation ID, "general_chat", "knowledge_qa", or null if no match
- `confidence`: A number between 0 and 1 indicating confidence in the match
- `params`: An object with extracted parameter values (use null for missing params)
- `fallback_sql`: If no operation matches, generate a SQL query (null if operation matched)
- `reasoning`: Brief explanation of your analysis
- `missing_params`: Array of required parameter names that were not provided
- `suggestions`: Array of helpful suggestions for the user

### User Query
{user_query}

### Output
JSON Object:
"""

        try:
            # 构建消息
            messages = [
                {'role': 'system', 'content': 'You are a helpful assistant. Return only JSON.'},
                {'role': 'user', 'content': prompt}
            ]

            # 如果启用缓存，在 system message 上添加 cache_control
            if self.enable_prompt_cache:
                messages[0]['cache_control'] = {"type": "ephemeral"}
                logger.debug("意图识别启用缓存控制")

            # 构建 API 调用参数
            api_params = {
                'model': 'qwen-plus',
                'messages': messages,
                'result_format': 'message',
            }

            # 非思考模式下启用结构化输出
            if self.enable_structured_output and not self.enable_thinking:
                api_params['response_format'] = {'type': 'json_object'}
                logger.debug("意图识别启用结构化输出模式 (json_object)")

            response = Generation.call(**api_params)

            if response.status_code == 200:
                content = response.output.choices[0].message.content

                # 记录缓存指标
                if self.enable_prompt_cache and hasattr(response, 'usage'):
                    self._record_cache_metrics(response, 'recognize_intent')

                # 使用统一的 JSON 解析方法
                try:
                    result = self._parse_json_response(content)
                except JsonParseError as e:
                    logger.error(f"意图识别 JSON 解析失败: {e}")
                    return {
                        "operation_id": None,
                        "confidence": 0.0,
                        "params": {},
                        "fallback_sql": None,
                        "reasoning": f"解析响应失败: {str(e)}",
                        "missing_params": [],
                        "suggestions": ["请重新描述您的需求"]
                    }

                # Apply defaults
                result.setdefault('operation_id', None)
                result.setdefault('confidence', 0.0)
                result.setdefault('params', {})
                result.setdefault('fallback_sql', None)
                result.setdefault('reasoning', '')
                result.setdefault('missing_params', [])
                result.setdefault('suggestions', [])

                logger.info(f"意图识别结果: operation={result.get('operation_id')}, "
                           f"confidence={result.get('confidence', 0):.2f}")

                return result
            else:
                raise Exception(f"API Error: {response.code} - {response.message}")

        except Exception as e:
            logger.error(f"意图识别失败: {e}")
            raise Exception(f"意图识别失败: {str(e)}")

    def suggest_param_value(self, param_name: str, param_description: str,
                            available_values: list, user_context: str = "") -> Dict[str, Any]:
        """
        智能推荐参数值

        Args:
            param_name: 参数名
            param_description: 参数描述
            available_values: 可用值列表
            user_context: 用户上下文（如之前的查询）

        Returns:
            {
                "suggestions": [
                    {"value": "xxx", "display": "xxx", "reason": "匹配原因"}
                ],
                "best_match": "xxx"  # 最佳匹配
            }
        """
        if not available_values:
            return {"suggestions": [], "best_match": None}

        # 简单实现：返回前几个值
        suggestions = []
        for val in available_values[:5]:
            if isinstance(val, dict):
                suggestions.append({
                    "value": val.get("value", val),
                    "display": val.get("display", val),
                    "reason": ""
                })
            else:
                suggestions.append({
                    "value": val,
                    "display": str(val),
                    "reason": ""
                })

        return {
            "suggestions": suggestions,
            "best_match": suggestions[0]["value"] if suggestions else None
        }

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str = None
    ) -> "ChatResponse":
        """支持工具调用的对话

        Args:
            messages: 对话消息列表
            tools: 工具定义列表
            system_prompt: 系统提示词

        Returns:
            ChatResponse: 包含 content 和 tool_calls 的响应
        """
        from src.llm_tool_models import ChatResponse, ToolCall

        if not self.api_key:
            logger.error("chat_with_tools: API key not configured")
            return ChatResponse(content="API 密钥未配置")

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        try:
            if self.client:
                response = self.client.chat.completions.create(
                    model="qwen-plus",
                    messages=full_messages,
                    tools=tools,
                    tool_choice="auto"
                )
            else:
                # DashScope 原生模式
                api_params = {
                    'model': 'qwen-plus',
                    'messages': full_messages,
                    'tools': tools,
                    'result_format': 'message'
                }
                response = Generation.call(**api_params)

            return self._parse_tool_response(response)

        except Exception as e:
            logger.error(f"chat_with_tools failed: {e}", exc_info=True)
            return ChatResponse(content=f"对话服务异常：{str(e)}")

    def _parse_tool_response(self, response) -> "ChatResponse":
        """解析工具调用响应"""
        from src.llm_tool_models import ChatResponse, ToolCall

        # 提取 message（兼容 OpenAI/DashScope，两者的属性行为不同）
        message = None

        # 优先尝试 OpenAI 兼容响应（直接带 choices）
        try:
            choices = getattr(response, "choices", None)
        except KeyError:
            choices = None

        if choices:
            message = choices[0].message
        else:
            # 兼容 DashScope 原生响应：在 response.output.choices 下
            output = getattr(response, "output", None)
            if output is not None:
                try:
                    output_choices = getattr(output, "choices", None)
                except KeyError:
                    output_choices = None
                if output_choices:
                    message = output_choices[0].message

        if message is None:
            return ChatResponse(content="响应格式异常")

        # 提取 tool_calls（同样需要兼容 DashScope 对缺失字段抛 KeyError 的行为）
        tool_calls = []
        try:
            raw_tool_calls = getattr(message, "tool_calls", None)
        except KeyError:
            raw_tool_calls = None

        if raw_tool_calls:
            for tc in raw_tool_calls:
                # 兼容对象和 dict 两种结构
                if isinstance(tc, dict):
                    tool_calls.append(ToolCall.from_dict(tc))
                else:
                    tool_calls.append(ToolCall.from_openai(tc))

        return ChatResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop"
        )
