# MySQL Web Enhancement - 前端实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 MySQL 数据导出工具创建 React + TypeScript 前端界面，实现完整的查询、预览、导出操作流程。

**Architecture:** 使用 React 18 + Vite + TypeScript 构建 SPA，Ant Design 作为 UI 组件库，Axios 处理 API 请求。应用分为四大功能模块：智能查询（自然语言输入+表选择）、Schema 浏览器、变更预览（Before/After 对比）、结果导出。

**Tech Stack:** React 18, TypeScript, Vite, Ant Design 5.x, Axios, React Router

---

## 项目结构

```
frontend/
├── index.html              # HTML 入口
├── package.json            # 依赖配置
├── tsconfig.json           # TypeScript 配置
├── vite.config.ts          # Vite 配置
├── src/
│   ├── main.tsx            # 应用入口
│   ├── App.tsx             # 根组件
│   ├── api/
│   │   └── client.ts       # Axios 封装 + API 调用
│   ├── components/         # 可复用组件
│   │   ├── Layout.tsx      # 页面布局
│   │   ├── QueryInput.tsx  # 查询输入组件
│   │   ├── TableSelector.tsx # 表选择器
│   │   ├── DiffViewer.tsx  # 变更对比组件
│   │   └── SchemaViewer.tsx # Schema 展示组件
│   ├── pages/              # 页面组件
│   │   ├── HomePage.tsx    # 首页（查询）
│   │   ├── SchemaPage.tsx  # Schema 管理页
│   │   └── PreviewPage.tsx # 变更预览页
│   ├── types/
│   │   └── index.ts        # TypeScript 类型定义
│   └── styles/
│       └── global.css      # 全局样式
└── public/                 # 静态资源
```

---

## 阶段一：项目初始化与基础配置

### Task 1: 初始化 Vite + React + TypeScript 项目

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`

**Step 1: 创建 package.json**

```json
{
  "name": "mysql-web-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "antd": "^5.12.0",
    "axios": "^1.6.0",
    "@ant-design/icons": "^5.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.37",
    "@types/react-dom": "^18.2.15",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.2.2",
    "vite": "^5.0.0"
  }
}
```

**Step 2: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

**Step 3: 创建 vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
```

**Step 4: 创建 index.html**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MySQL 数据导出工具</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**Step 5: 安装依赖**

```bash
cd frontend && npm install
```

**验收标准:**
- [ ] `frontend/node_modules` 目录存在
- [ ] 无安装错误

---

## 阶段二：类型定义与 API 封装

### Task 2: 创建 TypeScript 类型定义

**Files:**
- Create: `frontend/src/types/index.ts`

**实现:**

```typescript
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
}

export interface DiffChange {
  keys: Record<string, any>;
  changed_fields: string[];
  before: Record<string, any>;
  after: Record<string, any>;
}
```

**验收标准:**
- [ ] 文件创建成功
- [ ] 类型定义完整

---

### Task 3: 创建 API 客户端

**Files:**
- Create: `frontend/src/api/client.ts`

**实现:**

```typescript
import axios from 'axios';
import {
  QueryRequest,
  QueryResponse,
  TableInfo,
  MutationPreviewRequest,
  MutationPreviewResponse,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// 健康检查
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

// 查询分析
export const analyzeQuery = async (data: QueryRequest): Promise<QueryResponse> => {
  const response = await api.post('/query/analyze', data);
  return response.data;
};

// 获取所有表
export const getTables = async (): Promise<string[]> => {
  const response = await api.get('/schema/tables');
  return response.data.tables;
};

// 获取表详情
export const getTableInfo = async (tableName: string): Promise<TableInfo> => {
  const response = await api.get(`/schema/table/${tableName}`);
  return response.data;
};

// 变更预览
export const previewMutation = async (
  data: MutationPreviewRequest
): Promise<MutationPreviewResponse> => {
  const response = await api.post('/mutation/preview', data);
  return response.data;
};

export default api;
```

**验收标准:**
- [ ] API 函数完整
- [ ] 类型正确

---

## 阶段三：基础布局与路由

### Task 4: 创建布局组件

**Files:**
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/styles/global.css`

**实现 Layout.tsx:**

```typescript
import React from 'react';
import { Layout as AntLayout, Menu, Typography } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  DatabaseOutlined,
  SearchOutlined,
  EyeOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = AntLayout;
const { Title } = Typography;

const Layout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/',
      icon: <SearchOutlined />,
      label: '智能查询',
    },
    {
      key: '/schema',
      icon: <DatabaseOutlined />,
      label: 'Schema 管理',
    },
    {
      key: '/preview',
      icon: <EyeOutlined />,
      label: '变更预览',
    },
  ];

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#fff', borderBottom: '1px solid #f0f0f0' }}>
        <Title level={3} style={{ margin: '16px 0' }}>
          MySQL 数据导出工具
        </Title>
      </Header>
      <AntLayout>
        <Sider width={200} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>
        <Content style={{ padding: '24px', background: '#f5f5f5' }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
};

export default Layout;
```

**实现 global.css:**

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}
```

**验收标准:**
- [ ] 布局组件渲染正常
- [ ] 导航菜单可点击

---

### Task 5: 创建应用入口与路由

**Files:**
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`

**实现 main.tsx:**

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import './styles/global.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <App />
    </ConfigProvider>
  </React.StrictMode>
);
```

**实现 App.tsx:**

```typescript
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import SchemaPage from './pages/SchemaPage';
import PreviewPage from './pages/PreviewPage';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="schema" element={<SchemaPage />} />
          <Route path="preview" element={<PreviewPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
```

**验收标准:**
- [ ] 路由切换正常
- [ ] 中文语言包生效

---

## 阶段四：页面实现

### Task 6: 实现智能查询页面（首页）

**Files:**
- Create: `frontend/src/pages/HomePage.tsx`

**功能需求:**
1. 自然语言输入框
2. 提交后显示表选择器（如果需要交互）
3. 显示生成的 SQL
4. 执行导出按钮

**实现:**

```typescript
import React, { useState } from 'react';
import {
  Card,
  Input,
  Button,
  Typography,
  Spin,
  Alert,
  Tag,
  Space,
  List,
  Checkbox,
} from 'antd';
import { SearchOutlined, DownloadOutlined } from '@ant-design/icons';
import { analyzeQuery } from '../api/client';
import { QueryResponse, TableSuggestion } from '../types';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const HomePage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);

  const handleAnalyze = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await analyzeQuery({
        natural_language: query,
        selected_tables: selectedTables.length > 0 ? selectedTables : undefined,
      });
      setResult(response);
      if (!response.needs_interaction) {
        setSelectedTables(response.selected_tables);
      }
    } catch (err) {
      setError('分析失败，请稍后重试');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleTableSelect = (table: string, checked: boolean) => {
    if (checked) {
      setSelectedTables([...selectedTables, table]);
    } else {
      setSelectedTables(selectedTables.filter(t => t !== table));
    }
  };

  return (
    <div>
      <Title level={2}>智能查询</Title>
      <Paragraph type="secondary">
        使用自然语言描述您想要查询的数据，AI 会自动生成 SQL 并导出 Excel。
      </Paragraph>

      <Card style={{ marginBottom: 24 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <TextArea
            placeholder="例如：查一下昨天所有固定车的入场记录"
            value={query}
            onChange={e => setQuery(e.target.value)}
            rows={3}
            size="large"
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleAnalyze}
            loading={loading}
            size="large"
            block
          >
            分析查询
          </Button>
        </Space>
      </Card>

      {error && (
        <Alert message={error} type="error" style={{ marginBottom: 24 }} />
      )}

      {result?.needs_interaction && (
        <Card title="请选择数据表" style={{ marginBottom: 24 }}>
          <Paragraph>{result.reason}</Paragraph>
          <List
            dataSource={result.suggestions}
            renderItem={(item: TableSuggestion) => (
              <List.Item>
                <Checkbox
                  checked={selectedTables.includes(item.table)}
                  onChange={e => handleTableSelect(item.table, e.target.checked)}
                >
                  <Space>
                    <Text strong>{item.table}</Text>
                    {item.recommended && <Tag color="green">推荐</Tag>}
                    {item.score && <Tag>匹配度: {(item.score * 100).toFixed(0)}%</Tag>}
                  </Space>
                </Checkbox>
              </List.Item>
            )}
          />
          <Button
            type="primary"
            onClick={handleAnalyze}
            style={{ marginTop: 16 }}
            disabled={selectedTables.length === 0}
          >
            确认选择
          </Button>
        </Card>
      )}

      {result && !result.needs_interaction && (
        <Card title="查询结果" style={{ marginBottom: 24 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert message={result.reason} type="info" showIcon />
            
            <div>
              <Text strong>生成 SQL：</Text>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 4 }}>
                {result.sql}
              </pre>
            </div>

            <div>
              <Text strong>推理过程：</Text>
              <Paragraph>{result.reasoning}</Paragraph>
            </div>

            <div>
              <Text strong>导出文件：</Text>
              <Text>{result.filename}.xlsx ({result.sheet_name})</Text>
            </div>

            <Button
              type="primary"
              icon={<DownloadOutlined />}
              size="large"
            >
              执行并导出
            </Button>
          </Space>
        </Card>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <p>AI 正在分析您的查询...</p>
        </div>
      )}
    </div>
  );
};

export default HomePage;
```

**验收标准:**
- [ ] 页面可以输入查询
- [ ] 点击"分析查询"调用 API
- [ ] 如果需要交互显示表选择器
- [ ] 显示生成的 SQL 和推理过程

---

### Task 7: 实现 Schema 管理页面

**Files:**
- Create: `frontend/src/pages/SchemaPage.tsx`

**功能需求:**
1. 显示所有表列表
2. 点击表名查看详情（字段、类型、注释、外键）

**实现:**

```typescript
import React, { useEffect, useState } from 'react';
import {
  Card,
  Table,
  Typography,
  Spin,
  Alert,
  Tag,
  Descriptions,
  Space,
} from 'antd';
import { getTables, getTableInfo } from '../api/client';
import { TableInfo, ColumnInfo } from '../types';

const { Title } = Typography;

const SchemaPage: React.FC = () => {
  const [tables, setTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableInfo, setTableInfo] = useState<TableInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTables();
  }, []);

  const loadTables = async () => {
    try {
      const data = await getTables();
      setTables(data);
    } catch (err) {
      setError('加载表列表失败');
      console.error(err);
    }
  };

  const handleTableClick = async (tableName: string) => {
    setLoading(true);
    setError(null);
    setSelectedTable(tableName);
    
    try {
      const info = await getTableInfo(tableName);
      setTableInfo(info);
    } catch (err) {
      setError('加载表详情失败');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '字段名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: '注释',
      dataIndex: 'comment',
      key: 'comment',
    },
    {
      title: '可空',
      dataIndex: 'nullable',
      key: 'nullable',
      render: (nullable: boolean) => (nullable ? '是' : '否'),
    },
  ];

  return (
    <div>
      <Title level={2}>Schema 管理</Title>

      {error && <Alert message={error} type="error" style={{ marginBottom: 16 }} />}

      <Space align="start" style={{ width: '100%' }}>
        <Card title="数据表" style={{ width: 300, minHeight: 500 }}>
          {tables.map(table => (
            <div
              key={table}
              onClick={() => handleTableClick(table)}
              style={{
                padding: '12px 16px',
                cursor: 'pointer',
                background: selectedTable === table ? '#e6f7ff' : 'transparent',
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              {table}
            </div>
          ))}
        </Card>

        <Card title={selectedTable || '表详情'} style={{ flex: 1, minHeight: 500 }}>
          {loading ? (
            <Spin />
          ) : tableInfo ? (
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              {tableInfo.description && (
                <Descriptions size="small">
                  <Descriptions.Item label="描述">
                    {tableInfo.description}
                  </Descriptions.Item>
                </Descriptions>
              )}

              <Table
                columns={columns}
                dataSource={tableInfo.columns}
                rowKey="name"
                size="small"
                pagination={false}
              />

              {tableInfo.foreign_keys && tableInfo.foreign_keys.length > 0 && (
                <div>
                  <Title level={5}>外键关系</Title>
                  {tableInfo.foreign_keys.map((fk, idx) => (
                    <Tag key={idx} color="blue">
                      {fk.column} → {fk.references}
                    </Tag>
                  ))}
                </div>
              )}
            </Space>
          ) : (
            <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>
              请点击左侧表名查看详情
            </div>
          )}
        </Card>
      </Space>
    </div>
  );
};

export default SchemaPage;
```

**验收标准:**
- [ ] 显示表列表
- [ ] 点击表名加载详情
- [ ] 显示字段、类型、注释、外键

---

### Task 8: 实现变更预览页面

**Files:**
- Create: `frontend/src/pages/PreviewPage.tsx`

**功能需求:**
1. 输入 SQL 和预览 SQL
2. 显示 Before/After 对比
3. 显示警告信息

**实现:**

```typescript
import React, { useState } from 'react';
import {
  Card,
  Input,
  Button,
  Typography,
  Spin,
  Alert,
  Table,
  Tag,
  Space,
  Descriptions,
  Radio,
} from 'antd';
import { EyeOutlined } from '@ant-design/icons';
import { previewMutation } from '../api/client';
import { MutationPreviewResponse, DiffChange } from '../types';

const { Title, Text } = Typography;
const { TextArea } = Input;

const PreviewPage: React.FC = () => {
  const [sql, setSql] = useState('');
  const [previewSql, setPreviewSql] = useState('');
  const [keyColumns, setKeyColumns] = useState('id');
  const [operationType, setOperationType] = useState<'update' | 'delete' | 'insert'>('update');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MutationPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePreview = async () => {
    if (!sql.trim() || !previewSql.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await previewMutation({
        sql,
        preview_sql: previewSql,
        key_columns: keyColumns.split(',').map(s => s.trim()),
        operation_type: operationType,
      });
      setResult(response);
    } catch (err) {
      setError('预览失败，请检查 SQL 语法');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const renderDiffTable = () => {
    if (!result?.changes || result.changes.length === 0) return null;

    const columns = [
      {
        title: '主键',
        key: 'keys',
        render: (change: DiffChange) => (
          <span>{JSON.stringify(change.keys)}</span>
        ),
      },
      {
        title: '变更字段',
        key: 'changed_fields',
        render: (change: DiffChange) => (
          <Space>
            {change.changed_fields.map(field => (
              <Tag key={field} color="orange">{field}</Tag>
            ))}
          </Space>
        ),
      },
      {
        title: '变更前',
        key: 'before',
        render: (change: DiffChange) => (
          <pre style={{ margin: 0, fontSize: 12 }}>
            {JSON.stringify(change.before, null, 2)}
          </pre>
        ),
      },
      {
        title: '变更后',
        key: 'after',
        render: (change: DiffChange) => (
          <pre style={{ margin: 0, fontSize: 12 }}>
            {JSON.stringify(change.after, null, 2)}
          </pre>
        ),
      },
    ];

    return (
      <Table
        columns={columns}
        dataSource={result.changes}
        rowKey={(record, index) => index?.toString() || ''}
        size="small"
        pagination={{ pageSize: 5 }}
      />
    );
  };

  return (
    <div>
      <Title level={2}>变更预览</Title>

      <Card style={{ marginBottom: 24 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>操作类型：</Text>
            <Radio.Group
              value={operationType}
              onChange={e => setOperationType(e.target.value)}
            >
              <Radio value="update">更新</Radio>
              <Radio value="delete">删除</Radio>
              <Radio value="insert">插入</Radio>
            </Radio.Group>
          </div>

          <div>
            <Text strong>主键列（逗号分隔）：</Text>
            <Input
              value={keyColumns}
              onChange={e => setKeyColumns(e.target.value)}
              placeholder="例如：id 或 id,name"
            />
          </div>

          <div>
            <Text strong>执行 SQL：</Text>
            <TextArea
              value={sql}
              onChange={e => setSql(e.target.value)}
              rows={4}
              placeholder="输入要执行的 SQL 语句"
            />
          </div>

          <div>
            <Text strong>预览 SQL（用于获取变更前数据）：</Text>
            <TextArea
              value={previewSql}
              onChange={e => setPreviewSql(e.target.value)}
              rows={4}
              placeholder="输入用于预览的 SELECT 语句"
            />
          </div>

          <Button
            type="primary"
            icon={<EyeOutlined />}
            onClick={handlePreview}
            loading={loading}
            size="large"
            block
          >
            预览变更
          </Button>
        </Space>
      </Card>

      {error && <Alert message={error} type="error" style={{ marginBottom: 16 }} />}

      {result && (
        <Card title="变更预览结果">
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Descriptions size="small" bordered>
              <Descriptions.Item label="操作类型">
                <Tag color={operationType === 'delete' ? 'red' : operationType === 'update' ? 'orange' : 'green'}>
                  {operationType === 'update' ? '更新' : operationType === 'delete' ? '删除' : '插入'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="影响行数">
                {result.summary.updated || result.summary.deleted || result.summary.inserted || 0}
              </Descriptions.Item>
              <Descriptions.Item label="预计耗时">
                {result.estimated_time.toFixed(2)}s
              </Descriptions.Item>
            </Descriptions>

            {result.warnings.length > 0 && (
              <Alert
                message="警告"
                description={
                  <ul>
                    {result.warnings.map((warning, idx) => (
                      <li key={idx}>{warning}</li>
                    ))}
                  </ul>
                }
                type="warning"
                showIcon
              />
            )}

            {renderDiffTable()}

            <Button type="primary" danger={operationType === 'delete'}>
              确认执行
            </Button>
          </Space>
        </Card>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <p>正在生成预览...</p>
        </div>
      )}
    </div>
  );
};

export default PreviewPage;
```

**验收标准:**
- [ ] 可以输入 SQL 和预览 SQL
- [ ] 选择操作类型
- [ ] 显示 Before/After 对比表格
- [ ] 显示警告信息

---

## 阶段五：构建与部署

### Task 9: 构建前端项目

**Files:**
- Modify: `frontend/package.json` - 添加 build 脚本（已包含）

**Step 1: 构建**

```bash
cd frontend && npm run build
```

**Step 2: 验证构建输出**

检查 `frontend/dist/` 目录是否存在且包含：
- index.html
- assets/ (JS/CSS 文件)

**验收标准:**
- [ ] 构建成功无错误
- [ ] dist 目录包含所有资源

---

### Task 10: 配置后端静态文件服务

**Files:**
- Modify: `web_app.py` - 添加静态文件挂载

**实现:**

在 web_app.py 中添加：

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# 挂载前端静态文件
frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    
    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))
    
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = os.path.join(frontend_path, path)
        if os.path.exists(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_path, "index.html"))
```

**验收标准:**
- [ ] 访问 http://127.0.0.1:8000/ 显示前端页面
- [ ] API 接口仍正常工作

---

## 执行计划

### 并行执行策略

**Wave 1: 基础配置（串行）**
- Task 1 → Task 2 → Task 3

**Wave 2: 布局与路由（串行）**
- Task 4 → Task 5

**Wave 3: 页面实现（并行）**
- Task 6, Task 7, Task 8 可同时进行

**Wave 4: 构建与部署（串行）**
- Task 9 → Task 10

### 验收总标准

- [ ] 所有页面可正常访问
- [ ] 智能查询页面：输入 → 分析 → 选择表 → 显示 SQL
- [ ] Schema 页面：查看表列表 → 查看字段详情
- [ ] 预览页面：输入 SQL → 显示 Before/After 对比
- [ ] 前后端连通性正常
- [ ] 无控制台错误

---

## 执行方式选择

**Plan complete and saved to `.sisyphus/plans/frontend-implementation.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
