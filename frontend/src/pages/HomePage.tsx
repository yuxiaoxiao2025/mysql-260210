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
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 4, overflow: 'auto' }}>
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
