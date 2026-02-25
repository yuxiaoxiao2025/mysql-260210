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
