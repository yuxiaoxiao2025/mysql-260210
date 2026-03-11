import os
import json
import logging
import dashscope
from dashscope import Generation
from typing import Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.metadata.retrieval_agent import RetrievalAgent
    from src.metadata.retrieval_models import TableRetrievalResult

from src.context import SlotTracker, QueryRewriter
from src.constraint import TableValidator

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, allowed_tables: Optional[list[str]] = None):
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.last_result = None  # Store last result for transaction preview
        self.conversation_history = []  # Store conversation history (max 5 rounds)
        self.max_history_rounds = 5  # Maximum number of conversation rounds to keep
        self.retrieval_agent: Optional["RetrievalAgent"] = None  # Lazy load

        # Context enhancement components
        self.slot_tracker = SlotTracker()
        self.query_rewriter = QueryRewriter()

        # Table validation
        self.table_validator: Optional[TableValidator] = None
        self._user_provided_tables: Optional[list[str]] = None
        if allowed_tables:
            self.table_validator = TableValidator(allowed_tables)
            self._user_provided_tables = allowed_tables.copy()

        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY not found in environment variables.")
            print("⚠️  Warning: DASHSCOPE_API_KEY not found in environment variables.")
        else:
            dashscope.api_key = self.api_key

    def generate_sql(self, user_query: str, schema_context: str, error_context: Optional[str] = None, context: Optional[dict[str, str]] = None) -> dict[str, Any]:
        """
        Translate NL to SQL.

        Args:
            user_query: The natural language query from the user.
            schema_context: Database schema information for SQL generation.
            error_context: Optional error message from a previous attempt.
            context: Optional context dictionary for query enhancement (e.g., {"plate": "沪A12345"}).

        Returns a dict: {
            "sql": "SELECT ...",
            "filename": "suggested_filename",
            "sheet_name": "suggested_sheet_name",
            "reasoning": "Explanation...",
            "intent": "query" | "mutation",
            "preview_sql": "SELECT ... (for mutation operations)",
            "key_columns": ["col1", "col2"],
            "warnings": ["warning1", "warning2"]
        }
        """
        # Step 1: Extract slots from query and merge with provided context
        extracted_slots = self.slot_tracker.extract(user_query)
        merged_context = {**(context or {}), **extracted_slots}

        # Step 2: Rewrite query using context (pronoun substitution)
        rewritten_query = self.query_rewriter.rewrite(user_query, merged_context)
        if rewritten_query != user_query:
            logger.info(f"Query rewritten: '{user_query}' -> '{rewritten_query}'")

        # Step 3: Get allowed tables from retrieval pipeline for validation
        # Only use retrieval tables if user didn't provide explicit allowed_tables
        allowed_tables_from_retrieval = self._get_allowed_tables_from_retrieval()
        if allowed_tables_from_retrieval and not self._user_provided_tables:
            # Auto-create validator if retrieval provides tables and no user-provided tables exist
            self.table_validator = TableValidator(allowed_tables_from_retrieval)
            logger.debug(f"Auto-created TableValidator with {len(allowed_tables_from_retrieval)} tables from retrieval")

        # Build conversation history context
        history_context = ""
        if self.conversation_history:
            history_context = "\n### Conversation History (Previous queries and results)\n"
            for i, (prev_query, prev_result) in enumerate(self.conversation_history, 1):
                history_context += f"Round {i}:\n"
                history_context += f"  User: {prev_query}\n"
                if prev_result:
                    history_context += f"  Result: {prev_result}\n"
                history_context += "\n"
        
        # Build error context if provided
        error_text = ""
        if error_context:
            error_text = f"\n### Error from Previous Attempt\n{error_context}\n"

        # Optional: Enhance schema with retrieval
        # First try the RetrievalPipeline (with reranking support)
        retrieval_context = ""
        pipeline = self._get_retrieval_pipeline()
        if pipeline:
            try:
                result = pipeline.search(rewritten_query, top_k=5)
                # Add retrieved tables to schema_context
                retrieval_context = "\n" + self._build_retrieval_context(result)
                logger.debug(
                    f"Enhanced schema with {len(result.matches)} retrieved tables via pipeline"
                )
            except Exception as e:
                logger.warning(f"Pipeline retrieval enhancement failed: {e}")
                # Continue without enhancement or fall back to agent

        # Fall back to RetrievalAgent if pipeline is not available
        if not retrieval_context:
            agent = self._get_retrieval_agent()
            if agent and agent.graph:  # Graph exists (indexing done)
                try:
                    from src.metadata.retrieval_models import RetrievalRequest, RetrievalLevel
                    result = agent.search(RetrievalRequest(
                        query=rewritten_query,
                        level=RetrievalLevel.TABLE,
                        top_k=5
                    ))
                    # Add retrieved tables to schema_context
                    retrieval_context = "\n" + self._build_retrieval_context(result)
                    logger.debug(f"Enhanced schema with {len(result.matches)} retrieved tables via agent")
                except Exception as e:
                    logger.warning(f"Retrieval enhancement failed: {e}")
                    # Retrieval is optional enhancement, continue without it

        prompt = f"""You are a MySQL expert. Your task is to translate the user's natural language query into an executable SQL statement.

### Schema Information
{schema_context}{retrieval_context}
{history_context}
{error_text}
### Instructions
1. Generate a valid MySQL SQL query based on the schema and user request.
2. If tables are in different databases (e.g., cloudinterface vs parkcloud), ensure you use the database prefix (e.g., `parkcloud.table_name`) if necessary.
3. Use JOINs if the data is distributed across tables.
4. **IMPORTANT**: The user wants "customized" and "readable" exports. Rename the output columns to friendly Chinese names using `AS` (e.g., `SELECT name AS '姓名'`). Use the descriptions provided in the schema context or infer reasonable names.
5. Suggest a filename (without extension) and a sheet name for the Excel export.
6. If there's an error from a previous attempt, analyze the error and fix the SQL accordingly.
7. **CRITICAL**: Pay attention to conversation history. If the user is correcting or refining a previous query, use that context to improve your response.

### DML Operations Support (INSERT/UPDATE/DELETE)
8. Determine the operation **intent**:
   - Use `"intent": "query"` for SELECT queries (read-only)
   - Use `"intent": "mutation"` for INSERT/UPDATE/DELETE (modifying data)
9. For **mutation** operations, you MUST also provide:
   - `preview_sql`: A SELECT query that shows the data to be affected (before execution)
   - `key_columns`: List of column names that identify affected rows (e.g., ["id", "username"])
   - `warnings`: List of warnings about the operation's impact (e.g., ["This will update 5 rows"])

### Output Format
Return ONLY a JSON object with the following keys:
   - `sql`: The SQL query string. Do NOT include markdown code blocks.
   - `filename`: A short, descriptive filename (e.g., "login_users").
   - `sheet_name`: A short sheet name (e.g., "人员名单").
   - `reasoning`: A brief explanation of your logic.
   - `intent`: Either "query" or "mutation"
   - `preview_sql`: For mutations - a SELECT query preview (optional for queries)
   - `key_columns`: For mutations - list of identifying columns (optional)
   - `warnings`: For mutations - list of impact warnings (optional)

### User Query
{rewritten_query}

### Output
JSON Object:
"""

        try:
            # Use qwen-plus as requested
            response = Generation.call(
                model='qwen-plus',
                messages=[{'role': 'system', 'content': 'You are a helpful SQL assistant. Return only JSON.'},
                          {'role': 'user', 'content': prompt}],
                result_format='message'
            )
            
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                # Clean up code blocks if present
                content = content.replace('```json', '').replace('```', '').strip()
                # Find the first { and last }
                start = content.find('{')
                end = content.rfind('}')
                if start != -1 and end != -1:
                    content = content[start:end+1]

                result = json.loads(content)
                # Apply defaults for extended contract fields
                result.setdefault('intent', 'query')
                result.setdefault('preview_sql', None)
                result.setdefault('key_columns', [])
                result.setdefault('warnings', [])

                # Step 4: Validate SQL tables against allowed list
                sql = result.get('sql', '')
                if sql and self.table_validator:
                    is_valid, error_msg = self.table_validator.validate(sql)
                    if not is_valid:
                        logger.warning(f"Table validation failed: {error_msg}")
                        # Add validation error to warnings
                        result['warnings'].append(f"Table validation: {error_msg}")
                        # Return error result instead of invalid SQL
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

                self.last_result = result  # Store for transaction preview

                # Add to conversation history (use original user_query for history)
                self._add_to_history(user_query, result)

                return result
            else:
                raise Exception(f"API Error: {response.code} - {response.message}")
                
        except Exception as e:
            raise Exception(f"LLM generation failed: {str(e)}")
    
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

    def chat(self, user_input: str) -> str:
        """
        生成通用对话回复

        Args:
            user_input: 用户输入

        Returns:
            生成的回复文本
        """
        messages = [{'role': 'system', 'content': 'You are a helpful parking management assistant. Answer user questions clearly and concisely.'}]
        
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
            response = Generation.call(
                model='qwen-plus',
                messages=[
                    {'role': 'system', 'content': 'You are a helpful assistant. Return only JSON.'},
                    {'role': 'user', 'content': prompt}
                ],
                result_format='message'
            )

            if response.status_code == 200:
                content = response.output.choices[0].message.content
                # Clean up code blocks if present
                content = content.replace('```json', '').replace('```', '').strip()
                # Find the first { and last }
                start = content.find('{')
                end = content.rfind('}')
                if start != -1 and end != -1:
                    content = content[start:end + 1]

                result = json.loads(content)

                # Apply defaults
                result.setdefault('operation_id', None)
                result.setdefault('confidence', 0.0)
                result.setdefault('params', {})
                result.setdefault('fallback_sql', None)
                result.setdefault('reasoning', '')
                result.setdefault('missing_params', [])
                result.setdefault('suggestions', [])

                logger.info(f"意图识别结果: operation={result.get('operation_id')}, "
                           f"confidence={result.get('confidence'):.2f}")

                return result
            else:
                raise Exception(f"API Error: {response.code} - {response.message}")

        except json.JSONDecodeError as e:
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
