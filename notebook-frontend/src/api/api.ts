import axios from 'axios';
import type { ApiResponse, ChatSession, Message, QueryResponse, User, DocumentList, Document, DocumentFilter, DocumentPreview, DocumentWithTask, Task } from '../types';
import { v4 as uuidv4 } from 'uuid';

// 创建axios实例
const api = axios.create({
  baseURL: '/api',  // 使用相对路径，由代理服务器处理
  timeout: 50000,
  withCredentials: true
});

// 认证相关函数
export const setCookie = (name: string, value: string, days: number = 7) => {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = name + '=' + encodeURIComponent(value) + '; expires=' + expires + '; path=/; SameSite=Lax';
};

export const getCookie = (name: string): string | null => {
  const nameEQ = name + '=';
  const ca = document.cookie.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === ' ') c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) === 0) return decodeURIComponent(c.substring(nameEQ.length, c.length));
  }
  return null;
};

export const deleteCookie = (name: string) => {
  document.cookie = name + '=; Max-Age=-99999999; path=/';
};

export const getToken = (): string | null => {
  const token = getCookie('token') || localStorage.getItem('token');
  
  // 如果没有在cookie中找到，尝试从localStorage查找
  if (!token) {
    console.warn('未找到认证令牌，访问受限API可能会失败');
    return null;
  }
  
  return token;
};

export const saveToken = (token: string) => {
  // 同时保存到cookie和localStorage以确保在不同环境中都能正确访问
  setCookie('token', token);
  localStorage.setItem('token', token);
  
  // 设置axios的默认header
  api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  console.log('令牌已保存，Authorization header已设置');
};

export const clearToken = () => {
  deleteCookie('token');
  localStorage.removeItem('token');
  delete api.defaults.headers.common['Authorization'];
  console.log('令牌已清除');
};

// 设置请求拦截器，添加认证header
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
    console.log(`请求拦截器: 设置Auth头部 ${config.url}`);
  } else {
    console.warn(`请求拦截器: 缺少令牌 ${config.url}`);
  }
  return config;
}, (error) => {
  console.error('请求拦截器错误:', error);
  return Promise.reject(error);
});

// 响应拦截器，处理错误
api.interceptors.response.use(
  (response) => {
    console.log(`API响应成功: ${response.config.url}`);
    
    // 将响应数据包装成ApiResponse格式
    let apiResponse: ApiResponse<any>;
    
    if (response.data && response.data.hasOwnProperty('success')) {
      apiResponse = response.data as ApiResponse<any>;
    } else {
      apiResponse = {
        success: true,
        data: response.data,
        message: 'success'
      };
    }
    
    // 返回修改后的响应对象，保持与Axios响应格式兼容
    return {
      ...response,
      data: apiResponse
    } as any;
  },
  (error) => {
    console.error('API错误:', error.response?.data || error.message);
    console.error(`失败URL: ${error.config?.url}, 状态码: ${error.response?.status}`);
    
    if (error.response?.status === 401) {
      // 认证失败，清除token
      clearToken();
      console.error('认证失败，令牌已清除');
      // 重定向到登录页面
      window.location.href = '/login';
    }
    
    const apiResponse: ApiResponse<any> = {
      success: false,
      message: error.response?.data?.detail || error.message || '请求失败',
      data: null
    };
    
    // 构造一个错误响应
    const errorResponse = {
      ...error.response,
      data: apiResponse
    };
    
    return Promise.resolve(errorResponse as any);
  }
);

// API函数
export const auth = {
  login: async (username: string, password: string): Promise<ApiResponse<User>> => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await api.post('/auth/token', formData);
    
    if (response.data && response.data.success && response.data.data.access_token) {
      saveToken(response.data.data.access_token);
    }
    
    return response.data;
  },
  
  register: async (username: string, email: string, password: string, fullName?: string): Promise<ApiResponse<User>> => {
    return (await api.post('/auth/register', { username, email, password, full_name: fullName })).data;
  },
  
  getProfile: async (): Promise<ApiResponse<User>> => {
    return (await api.get('/auth/me')).data;
  },
  
  logout: async (): Promise<ApiResponse<any>> => {
    clearToken();
    return { success: true, message: '已退出登录', data: null };
  }
};

// 系统设置API
export const settings = {
  getConfig: async (): Promise<ApiResponse<any>> => {
    return (await api.get('/agents/config')).data;
  },
  
  updateConfig: async (config: any): Promise<ApiResponse<any>> => {
    return (await api.post('/agents/config', config)).data;
  }
};

export const agent = {
  query: async (query: string, sessionId?: string, useRetrieval: boolean = true): Promise<ApiResponse<QueryResponse>> => {
    return (await api.post('/agents/query', { query, session_id: sessionId, use_retrieval: useRetrieval })).data;
  },
  
  uploadDocument: async (file: File): Promise<ApiResponse<any>> => {
    const formData = new FormData();
    formData.append('file', file);
    
    return (await api.post('/agents/upload-file', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })).data;
  },
  
  getConfig: async (): Promise<ApiResponse<any>> => {
    return (await api.get('/agents/config')).data;
  },
  
  updateConfig: async (config: any): Promise<ApiResponse<any>> => {
    return (await api.post('/agents/config', config)).data;
  }
};

export const chat = {
  getSessions: async (): Promise<ApiResponse<ChatSession[]>> => {
    return (await api.get('/chat/sessions')).data;
  },
  
  getSession: async (sessionId: string): Promise<ApiResponse<ChatSession>> => {
    return (await api.get(`/chat/sessions/${sessionId}`)).data;
  },
  
  createSession: async (title: string): Promise<ApiResponse<ChatSession>> => {
    return (await api.post('/chat/sessions', { title })).data;
  },
  
  updateSession: async (sessionId: string, title: string): Promise<ApiResponse<ChatSession>> => {
    return (await api.put(`/chat/sessions/${sessionId}`, { title })).data;
  },
  
  deleteSession: async (sessionId: string): Promise<ApiResponse<any>> => {
    return (await api.delete(`/chat/sessions/${sessionId}`)).data;
  },
  
  getMessages: async (sessionId: string): Promise<ApiResponse<Message[]>> => {
    return (await api.get(`/chat/sessions/${sessionId}/messages`)).data;
  },
  
  clearContext: async (sessionId: string): Promise<ApiResponse<any>> => {
    return (await api.post(`/chat/sessions/${sessionId}/clear`)).data;
  }
};

// 文档API
export const documents = {
  // 获取文档列表
  getDocuments: async (filter?: DocumentFilter): Promise<ApiResponse<DocumentList>> => {
    let endpoint = '/documents/';
    
    if (filter) {
      const params = new URLSearchParams();
      if (filter.skip !== undefined) params.append('skip', filter.skip.toString());
      if (filter.limit !== undefined) params.append('limit', filter.limit.toString());
      if (filter.search) params.append('search', filter.search);
      
      if (params.toString()) {
        endpoint += `?${params.toString()}`;
      }
    }
    
    return (await api.get(endpoint)).data;
  },
  
  // 获取单个文档
  getDocument: async (documentId: number): Promise<ApiResponse<Document>> => {
    return (await api.get(`/documents/${documentId}`)).data;
  },
  
  // 获取文档内容
  getDocumentContent: async (documentId: number): Promise<ApiResponse<any>> => {
    return (await api.get(`/documents/${documentId}/content`)).data;
  },
  
  // 上传文档
  uploadDocument: async (formData: FormData): Promise<ApiResponse<Document>> => {
    return (await api.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })).data;
  },
  
  // 从网页加载文档
  loadFromWeb: async (url: string, metadata?: any): Promise<ApiResponse<Document>> => {
    return (await api.post('/documents/from-web', {
      url,
      metadata
    })).data;
  },
  
  // 创建自定义文档
  createCustomDocument: async (name: string, content: string, fileType: string = 'txt', metadata?: any): Promise<ApiResponse<Document>> => {
    return (await api.post('/documents/custom', {
      name,
      content,
      file_type: fileType,
      metadata
    })).data;
  },
  
  // 更新文档
  updateDocument: async (documentId: number, data: any): Promise<ApiResponse<Document>> => {
    return (await api.put(`/documents/${documentId}`, data)).data;
  },
  
  // 删除文档
  deleteDocument: async (documentId: number, permanent: boolean = false): Promise<ApiResponse<any>> => {
    return (await api.delete(`/documents/${documentId}?permanent=${permanent}`)).data;
  },
  
  // 下载文档
  downloadDocument: async (documentId: number): Promise<void> => {
    window.open(`/api/documents/${documentId}/download`, '_blank');
  },
  
  // 获取文档列表，包含任务状态
  getDocumentsWithTasks: async (params = {}): Promise<ApiResponse<DocumentWithTask[]>> => {
    return (await api.get('/documents/with-tasks', { params })).data;
  }
};

// 任务API
export const tasks = {
  // 获取用户任务列表
  getUserTasks: async (params = {}): Promise<ApiResponse<Task[]>> => {
    return (await api.get('/tasks/user/list', { params })).data;
  },
  
  // 获取单个任务详情
  getTask: async (taskId: string): Promise<ApiResponse<Task>> => {
    return (await api.get(`/tasks/${taskId}`)).data;
  },
  
  // 获取任务步骤详情
  getTaskDetails: async (taskId: string): Promise<ApiResponse<any>> => {
    return (await api.get(`/tasks/${taskId}/details`)).data;
  },
  
  // 取消任务
  cancelTask: async (taskId: string): Promise<ApiResponse<Task>> => {
    return (await api.post(`/tasks/${taskId}/cancel`)).data;
  },
  
  // 获取文档相关任务
  getDocumentTasks: async (documentId: number): Promise<ApiResponse<Task[]>> => {
    return (await api.get(`/documents/${documentId}/tasks`)).data;
  },
  
  // 为文档创建处理任务
  createDocumentTask: async (documentId: number): Promise<ApiResponse<Task>> => {
    const formData = new FormData();
    formData.append('document_id', documentId.toString());
    
    return (await api.post('/documents/process', formData)).data;
  }
};

export default api; 