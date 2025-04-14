import axios from 'axios';
import type { ApiResponse, ChatSession, Message, QueryResponse, User, DocumentList, Document, DocumentFilter, DocumentPreview } from '../types';
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
    
    if (response.data.hasOwnProperty('success')) {
      return response.data;
    }
    
    return {
      success: true,
      data: response.data,
      message: 'success'
    };
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
    
    return {
      success: false,
      message: error.response?.data?.detail || error.message || '请求失败',
      data: null
    };
  }
);

// API函数
export const auth = {
  login: async (username: string, password: string): Promise<ApiResponse<User>> => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await api.post('/auth/token', formData);
    
    if (response.success && response.data.access_token) {
      saveToken(response.data.access_token);
    }
    
    return response;
  },
  
  register: async (username: string, email: string, password: string, fullName?: string): Promise<ApiResponse<User>> => {
    return api.post('/auth/register', { username, email, password, full_name: fullName });
  },
  
  getProfile: async (): Promise<ApiResponse<User>> => {
    return api.get('/auth/me');
  },
  
  logout: async (): Promise<ApiResponse<any>> => {
    clearToken();
    return { success: true, message: '已退出登录', data: null };
  }
};

// 系统设置API
export const settings = {
  getConfig: async (): Promise<ApiResponse<any>> => {
    return api.get('/agents/config');
  },
  
  updateConfig: async (config: any): Promise<ApiResponse<any>> => {
    return api.post('/agents/config', config);
  }
};

export const agent = {
  query: async (query: string, sessionId?: string, useRetrieval: boolean = true): Promise<ApiResponse<QueryResponse>> => {
    return api.post('/agents/query', { query, session_id: sessionId, use_retrieval: useRetrieval });
  },
  
  uploadDocument: async (file: File): Promise<ApiResponse<any>> => {
    const formData = new FormData();
    formData.append('file', file);
    
    return api.post('/agents/upload-file', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
  },
  
  getConfig: async (): Promise<ApiResponse<any>> => {
    return api.get('/agents/config');
  },
  
  updateConfig: async (config: any): Promise<ApiResponse<any>> => {
    return api.post('/agents/config', config);
  }
};

export const chat = {
  getSessions: async (): Promise<ApiResponse<ChatSession[]>> => {
    return api.get('/chat/sessions');
  },
  
  getSession: async (sessionId: string): Promise<ApiResponse<ChatSession>> => {
    return api.get(`/chat/sessions/${sessionId}`);
  },
  
  createSession: async (title: string): Promise<ApiResponse<ChatSession>> => {
    return api.post('/chat/sessions', { title });
  },
  
  updateSession: async (sessionId: string, title: string): Promise<ApiResponse<ChatSession>> => {
    return api.put(`/chat/sessions/${sessionId}`, { title });
  },
  
  deleteSession: async (sessionId: string): Promise<ApiResponse<any>> => {
    return api.delete(`/chat/sessions/${sessionId}`);
  },
  
  getMessages: async (sessionId: string): Promise<ApiResponse<Message[]>> => {
    return api.get(`/chat/sessions/${sessionId}/messages`);
  },
  
  clearContext: async (sessionId: string): Promise<ApiResponse<any>> => {
    return api.post(`/chat/sessions/${sessionId}/clear`);
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
    
    return api.get(endpoint);
  },
  
  // 获取单个文档
  getDocument: async (documentId: string): Promise<ApiResponse<Document>> => {
    return api.get(`/documents/${documentId}`);
  },
  
  // 获取文档内容
  getDocumentContent: async (documentId: string): Promise<ApiResponse<any>> => {
    return api.get(`/documents/${documentId}/content`);
  },
  
  // 上传文档
  uploadDocument: async (file: File, metadata?: any): Promise<ApiResponse<Document>> => {
    const formData = new FormData();
    formData.append('file', file);
    
    if (metadata) {
      formData.append('metadata', typeof metadata === 'string' ? metadata : JSON.stringify(metadata));
    }
    
    return api.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
  },
  
  // 从网页加载文档
  loadFromWeb: async (url: string, metadata?: any): Promise<ApiResponse<Document>> => {
    return api.post('/documents/from-web', {
      url,
      metadata
    });
  },
  
  // 创建自定义文档
  createCustomDocument: async (name: string, content: string, fileType: string = 'txt', metadata?: any): Promise<ApiResponse<Document>> => {
    return api.post('/documents/custom', {
      name,
      content,
      file_type: fileType,
      metadata
    });
  },
  
  // 更新文档
  updateDocument: async (documentId: string, data: any): Promise<ApiResponse<Document>> => {
    return api.put(`/documents/${documentId}`, data);
  },
  
  // 删除文档
  deleteDocument: async (documentId: string, permanent: boolean = false): Promise<ApiResponse<any>> => {
    return api.delete(`/documents/${documentId}?permanent=${permanent}`);
  },
  
  // 下载文档
  downloadDocument: async (documentId: string): Promise<void> => {
    window.open(`/api/documents/${documentId}/download`, '_blank');
  }
};

export default api; 