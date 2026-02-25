// API 请求/响应类型

export interface QueryRequest {
  natural_language: string;
  selected_tables?: string[];
}

export interface QueryResponse {
  sql: string;
  filename: string;
  sheet_name: string;
  reasoning: string;
  needs_interaction: boolean;
  selected_tables: string[];
  suggestions: TableSuggestion[];
}

export interface TableSuggestion {
  table: string;
  recommended?: boolean;
  score?: number;
}

export interface TableInfo {
  table_name: string;
  columns: ColumnInfo[];
  description?: string;
  foreign_keys?: ForeignKey[];
}

export interface ColumnInfo {
  name: string;
  type: string;
  comment?: string;
  nullable?: boolean;
}

export interface ForeignKey {
  column: string;
  references: string;
}

export interface MutationPreviewRequest {
  sql: string;
  preview_sql: string;
  key_columns: string[];
  operation_type: 'insert' | 'update' | 'delete';
}

export interface MutationPreviewResponse {
  operation_type: string;
  summary: {
    inserted?: number;
    updated?: number;
    deleted?: number;
  };
  before_data?: Record<string, any>[];
  after_data?: Record<string, any>[];
  warnings: string[];
  estimated_time: number;
  changes?: DiffChange[];
}

export interface DiffChange {
  keys: Record<string, any>;
  changed_fields: string[];
  before: Record<string, any>;
  after: Record<string, any>;
}
