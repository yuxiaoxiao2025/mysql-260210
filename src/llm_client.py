import os
import json
import dashscope
from dashscope import Generation

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.last_result = None  # Store last result for transaction preview
        self.conversation_history = []  # Store conversation history (max 5 rounds)
        self.max_history_rounds = 5  # Maximum number of conversation rounds to keep
        if not self.api_key:
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
