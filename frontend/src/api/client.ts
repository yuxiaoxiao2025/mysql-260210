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
  return response.data.tables || [];
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
