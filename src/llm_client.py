import os
import json
import logging
import dashscope
from dashscope import Generation
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.last_result = None  # Store last result for transaction preview
        self.conversation_history = []  # Store conversation history (max 5 rounds)
        self.max_history_rounds = 5  # Maximum number of conversation rounds to keep
        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY not found in environment variables.")
            print("⚠️  Warning: DASHSCOPE_API_KEY not found in environment variables.")
        else:
            dashscope.api_key = self.api_key

    def generate_sql(self, user_query, schema_context, error_context=None):
        """
        Translate NL to SQL.
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
        
        prompt = f"""You are a MySQL expert. Your task is to translate the user's natural language query into an executable SQL statement.

### Schema Information
{schema_context}
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
{user_query}

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
                self.last_result = result  # Store for transaction preview
                
                # Add to conversation history
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
   - Park names (场库): Must match one of the available values
   - Operator names (操作员): Must match one of the available values
   - Dates: Parse relative dates like "30天内" to appropriate values
3. If a parameter value is mentioned but not in the available values list, still extract it but add a warning.
4. If the query doesn't match any operation template, generate a fallback SQL query.
5. List any required parameters that are missing.

### Output Format
Return ONLY a JSON object with these keys:
- `operation_id`: The matched operation ID (e.g., "plate_distribute"), or null if no match
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
