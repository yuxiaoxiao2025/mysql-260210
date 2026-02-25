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
import { TableInfo } from '../types';

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
          {tables.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', padding: 20 }}>
              暂无表数据
            </div>
          ) : (
            tables.map(table => (
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
            ))
          )}
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
