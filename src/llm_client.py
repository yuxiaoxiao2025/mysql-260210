import os
import json
import dashscope
from dashscope import Generation

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
             print("⚠️  Warning: DASHSCOPE_API_KEY not found in environment variables.")
        else:
            dashscope.api_key = self.api_key

    def generate_sql(self, user_query, schema_context):
        """
        Translate NL to SQL.
        Returns a dict: {
            "sql": "SELECT ...",
            "filename": "suggested_filename",
            "sheet_name": "suggested_sheet_name",
            "reasoning": "Explanation..."
        }
        """
        prompt = f"""You are a MySQL expert. Your task is to translate the user's natural language query into an executable SQL statement.

### Schema Information
{schema_context}

### Instructions
1. Generate a valid MySQL SQL query based on the schema and user request.
2. If tables are in different databases (e.g., cloudinterface vs parkcloud), ensure you use the database prefix (e.g., `parkcloud.table_name`) if necessary.
3. Use JOINs if the data is distributed across tables.
4. **IMPORTANT**: The user wants "customized" and "readable" exports. Rename the output columns to friendly Chinese names using `AS` (e.g., `SELECT name AS '姓名'`). Use the descriptions provided in the schema context or infer reasonable names.
5. Suggest a filename (without extension) and a sheet name for the Excel export.
6. Return ONLY a JSON object with the following keys:
   - `sql`: The SQL query string. Do NOT include markdown code blocks.
   - `filename`: A short, descriptive filename (e.g., "login_users").
   - `sheet_name`: A short sheet name (e.g., "人员名单").
   - `reasoning`: A brief explanation of your logic.

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
                
                return json.loads(content)
            else:
                raise Exception(f"API Error: {response.code} - {response.message}")
                
        except Exception as e:
            raise Exception(f"LLM generation failed: {str(e)}")
