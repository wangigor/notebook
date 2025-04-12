import axios from 'axios';
import type { ApiResponse, ChatSession, Message, QueryResponse, User } from '../types';
import { v4 as uuidv4 } from 'uuid';

// 创建axios实例
const api = axios.create({
  baseURL: 'http://localhost:3000/api',
  headers: {
    'Content-Type': 'application/json',
  },
  // 添加超时设置
  timeout: 10000,
});

// 工具函数：设置cookie
export const setCookie = (name: string, value: string, days: number = 7) => {
  const date = new Date();
  date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
  const expires = "; expires=" + date.toUTCString();
  // 添加更严格的cookie属性，确保跨会话保留
  document.cookie = name + "=" + encodeURIComponent(value) + expires + 
    "; path=/; SameSite=Lax; secure=" + (window.location.protocol === 'https:') + 
    "; max-age=" + (days * 24 * 60 * 60);
  
  console.log(`Cookie ${name} 设置成功，值长度: ${value.length}, 过期时间: ${days}天`);
};

// 工具函数：获取cookie
export const getCookie = (name: string): string | null => {
  const nameEQ = name + "=";
  const ca = document.cookie.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === ' ') c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) === 0) return decodeURIComponent(c.substring(nameEQ.length, c.length));
  }
  return null;
};

// 工具函数：删除cookie
export const deleteCookie = (name: string) => {
  document.cookie = name + '=; Max-Age=-99999999; path=/';
};

// 获取token，优先从cookie获取，其次从localStorage获取
export const getToken = (): string | null => {
  const cookieToken = getCookie('auth_token');
  const localToken = localStorage.getItem('token');
  
  console.log('获取token: cookie=', !!cookieToken, ', localStorage=', !!localToken);
  
  return cookieToken || localToken;
};

// 保存token到cookie和localStorage
export const saveToken = (token: string) => {
  if (!token) {
    console.warn('尝试保存空token');
    return;
  }
  
  console.log(`保存token: ${token.substring(0, 10)}...，长度: ${token.length}`);
  setCookie('auth_token', token, 30); // 延长cookie保存时间到30天
  localStorage.setItem('token', token);
};

// 清除token
export const clearToken = () => {
  deleteCookie('auth_token');
  localStorage.removeItem('token');
};

// 开发环境中的模拟数据，用于快速测试前端
const MOCK_DATA = {
  enabled: false, // 设置为true开启模拟，false关闭模拟
  sessions: [
    {
      id: '1',
      name: '知识库问答',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
  ],
  messages: [
    {
      id: '1',
      role: 'system' as const,
      content: '我是Notebook AI助手，可以回答您的问题。',
      timestamp: new Date().toISOString(),
    },
  ] as Message[],
};

// 拦截器，处理认证和错误
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 处理特定错误
    if (error.response) {
      console.error('API错误:', error.response.status, error.response.data);
      
      // 处理401认证错误
      if (error.response.status === 401) {
        console.log('收到401未授权响应，清除token并重定向');
        clearToken();
        // 重定向到登录页
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
      
      // 返回友好的错误信息
      return Promise.reject({
        status: error.response.status,
        message: error.response.data?.message || error.response.data?.detail || '请求失败',
        data: error.response.data
      });
    }
    
    // 处理网络错误
    if (error.request) {
      console.error('网络错误:', error.message);
      return Promise.reject({
        status: 0,
        message: '网络连接失败，请检查您的网络连接'
      });
    }
    
    // 其他错误
    return Promise.reject({
      message: error.message || '请求处理过程中发生错误'
    });
  }
);

// 认证相关
export const auth = {
  login: async (username: string, password: string): Promise<ApiResponse<{ token: string; user: User }>> => {
    if (MOCK_DATA.enabled) {
      // 模拟登录
      saveToken('mock-token');
      return {
        success: true,
        message: '登录成功',
        data: {
          token: 'mock-token',
          user: {
            id: '1',
            username: 'test',
            email: 'test@example.com',
          },
        },
      };
    }

    // 使用form-urlencoded格式发送登录请求
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await api.post('/auth/token', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    
    // 处理登录响应
    const token = response.data.access_token;
    
    // 获取用户信息
    const userResponse = await api.get('/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    
    saveToken(token);
    
    return {
      success: true,
      message: '登录成功',
      data: {
        token,
        user: userResponse.data,
      },
    };
  },
  logout: async (): Promise<void> => {
    if (MOCK_DATA.enabled) {
      clearToken();
      return;
    }
    
    await api.post('/auth/logout');
    clearToken();
  },
  register: async (username: string, email: string, password: string): Promise<ApiResponse<User>> => {
    if (MOCK_DATA.enabled) {
      return {
        success: true,
        message: '注册成功',
        data: {
          id: '1',
          username,
          email,
        },
      };
    }
    
    const response = await api.post('/auth/register', { username, email, password });
    
    // 处理后端返回的数据，后端返回的是UserResponse类型
    // 前端只需要id、username和email字段
    if (response.data) {
      return {
        success: true,
        message: '注册成功',
        data: {
          id: String(response.data.id), // 转换为字符串，兼容前端User类型
          username: response.data.username,
          email: response.data.email,
        }
      };
    }
    
    return response.data;
  },
  getCurrentUser: async (): Promise<ApiResponse<User>> => {
    if (MOCK_DATA.enabled) {
      return {
        success: true,
        message: '获取用户信息成功',
        data: {
          id: '1',
          username: 'test',
          email: 'test@example.com',
        },
      };
    }
    
    try {
      console.log('尝试获取当前用户信息，token:', getToken()?.substring(0, 10) + '...');
      const response = await api.get('/auth/me');
      console.log('获取用户信息成功:', response.data);
      
      // 确保数据格式正确
      if (response.data) {
        return {
          success: true,
          message: '获取用户信息成功',
          data: {
            id: String(response.data.id || response.data.user?.id || ''),
            username: response.data.username || response.data.user?.username || '',
            email: response.data.email || response.data.user?.email || '',
            full_name: response.data.full_name || response.data.user?.full_name || null,
            is_active: response.data.is_active || response.data.user?.is_active || true,
            created_at: response.data.created_at || response.data.user?.created_at || '',
            updated_at: response.data.updated_at || response.data.user?.updated_at || '',
          }
        };
      }
      
      return {
        success: true,
        message: '获取用户信息成功',
        data: response.data
      };
    } catch (error: any) {
      console.error('获取用户信息失败:', error);
      throw error;
    }
  },
};

// 会话相关
export const chat = {
  getSessions: async (): Promise<ApiResponse<ChatSession[]>> => {
    if (MOCK_DATA.enabled) {
      return {
        success: true,
        message: '获取会话列表成功',
        data: MOCK_DATA.sessions,
      };
    }
    
    const response = await api.get('/chat/sessions');
    
    // 适配后端返回的数据格式
    const sessionsData = Array.isArray(response.data) ? response.data : [];
    return {
      success: true,
      message: '获取会话列表成功',
      data: sessionsData.map(session => ({
        id: session.session_id || session.id,
        name: session.title || `会话 ${session.id}`,
        createdAt: session.created_at || new Date().toISOString(),
        updatedAt: session.updated_at || new Date().toISOString(),
      }))
    };
  },
  createSession: async (name: string): Promise<ApiResponse<ChatSession>> => {
    if (MOCK_DATA.enabled) {
      const newSession = {
        id: Date.now().toString(),
        name,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      MOCK_DATA.sessions.push(newSession);
      return {
        success: true,
        message: '创建会话成功',
        data: newSession,
      };
    }
    
    // 按照后端API要求调整请求格式
    const response = await api.post('/chat/sessions', { title: name });
    
    // 适配后端返回的数据格式
    const sessionData = response.data;
    return {
      success: true,
      message: '创建会话成功',
      data: {
        id: sessionData.session_id || sessionData.id,
        name: sessionData.title || name,
        createdAt: sessionData.created_at || new Date().toISOString(),
        updatedAt: sessionData.updated_at || new Date().toISOString(),
      }
    };
  },
  getSession: async (id: string): Promise<ApiResponse<ChatSession>> => {
    if (MOCK_DATA.enabled) {
      const session = MOCK_DATA.sessions.find(s => s.id === id);
      if (!session) {
        throw new Error('会话不存在');
      }
      return {
        success: true,
        message: '获取会话成功',
        data: session,
      };
    }
    
    const response = await api.get(`/chat/sessions/${id}`);
    return response.data;
  },
  deleteSession: async (id: string): Promise<ApiResponse<void>> => {
    if (MOCK_DATA.enabled) {
      MOCK_DATA.sessions = MOCK_DATA.sessions.filter(s => s.id !== id);
      return {
        success: true,
        message: '删除会话成功',
        data: undefined,
      };
    }
    
    // 确保使用正确的会话ID格式
    const sessionId = id.startsWith('session_') ? id : `session_${id}`;
    try {
      const response = await api.delete(`/chat/sessions/${sessionId}`);
      return {
        success: true,
        message: '删除会话成功',
        data: undefined
      };
    } catch (error: any) {
      console.error('删除会话失败:', error);
      return {
        success: false,
        message: error.message || '删除会话失败',
        data: undefined
      };
    }
  },
  updateSession: async (id: string, name: string): Promise<ApiResponse<ChatSession>> => {
    if (MOCK_DATA.enabled) {
      const sessionIndex = MOCK_DATA.sessions.findIndex(s => s.id === id);
      if (sessionIndex === -1) {
        throw new Error('会话不存在');
      }
      MOCK_DATA.sessions[sessionIndex] = {
        ...MOCK_DATA.sessions[sessionIndex],
        name,
        updatedAt: new Date().toISOString(),
      };
      return {
        success: true,
        message: '更新会话成功',
        data: MOCK_DATA.sessions[sessionIndex],
      };
    }
    
    // 确保使用正确的会话ID格式
    const sessionId = id.startsWith('session_') ? id : `session_${id}`;
    try {
      const response = await api.put(`/chat/sessions/${sessionId}`, { title: name });
      
      // 适配后端返回的数据格式
      const sessionData = response.data;
      return {
        success: true,
        message: '更新会话成功',
        data: {
          id: sessionData.session_id || sessionData.id,
          name: sessionData.title || name,
          createdAt: sessionData.created_at || new Date().toISOString(),
          updatedAt: sessionData.updated_at || new Date().toISOString(),
        }
      };
    } catch (error: any) {
      console.error('更新会话失败:', error);
      return {
        success: false,
        message: error.message || '更新会话失败',
        data: {
          id,
          name,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        }
      };
    }
  },
  getMessages: async (sessionId: string): Promise<ApiResponse<Message[]>> => {
    if (MOCK_DATA.enabled) {
      return {
        success: true,
        message: '获取消息列表成功',
        data: MOCK_DATA.messages,
      };
    }
    
    const response = await api.get(`/chat/sessions/${sessionId}/messages`);
    
    // 适配后端返回的数据格式
    const messagesData = Array.isArray(response.data) ? response.data : [];
    return {
      success: true,
      message: '获取消息列表成功',
      data: messagesData.map(msg => ({
        id: msg.id?.toString() || uuidv4(),
        role: msg.role || 'assistant',
        content: msg.content || '',
        timestamp: msg.created_at || new Date().toISOString(),
      }))
    };
  },
  sendMessage: async (sessionId: string, content: string): Promise<ApiResponse<Message>> => {
    if (MOCK_DATA.enabled) {
      const newMessage = {
        id: uuidv4(),
        role: 'user' as const,
        content,
        timestamp: new Date().toISOString(),
      };
      MOCK_DATA.messages.push(newMessage);
      return {
        success: true,
        message: '发送消息成功',
        data: newMessage,
      };
    }
    
    // 确保使用正确的会话ID格式
    const formattedSessionId = sessionId.startsWith('session_') ? sessionId : `session_${sessionId}`;
    try {
      // 添加所有必要的字段
      const response = await api.post(`/chat/sessions/${formattedSessionId}/messages`, { 
        role: 'user',
        content: content,
        type: 'text'
      });
      
      const messageData = response.data;
      return {
        success: true,
        message: '发送消息成功',
        data: {
          id: messageData.id?.toString() || uuidv4(),
          role: messageData.role || 'user',
          content: messageData.content || content,
          timestamp: messageData.created_at || new Date().toISOString(),
        }
      };
    } catch (error: any) {
      console.error('发送消息失败:', error);
      return {
        success: false,
        message: error.message || '发送消息失败',
        data: {
          id: uuidv4(),
          role: 'user',
          content: content,
          timestamp: new Date().toISOString(),
        }
      };
    }
  },
  
  // 保存AI助手的回复消息
  saveAssistantMessage: async (sessionId: string, content: string): Promise<ApiResponse<Message>> => {
    if (MOCK_DATA.enabled) {
      const newMessage = {
        id: uuidv4(),
        role: 'assistant' as const,
        content,
        timestamp: new Date().toISOString(),
      };
      MOCK_DATA.messages.push(newMessage);
      return {
        success: true,
        message: 'AI回复保存成功',
        data: newMessage,
      };
    }
    
    // 确保会话ID格式正确
    const formattedSessionId = sessionId.startsWith('session_') ? sessionId : `session_${sessionId}`;
    try {
      // 添加所有必要的字段
      const response = await api.post(`/chat/sessions/${formattedSessionId}/messages`, { 
        role: 'assistant',
        content: content,
        type: 'text'
      });
      
      const messageData = response.data;
      return {
        success: true,
        message: 'AI回复保存成功',
        data: {
          id: messageData.id?.toString() || uuidv4(),
          role: messageData.role || 'assistant',
          content: messageData.content || content,
          timestamp: messageData.created_at || new Date().toISOString(),
        }
      };
    } catch (error: any) {
      console.error('保存AI回复失败:', error);
      return {
        success: false,
        message: error.message || '保存AI回复失败',
        data: {
          id: uuidv4(),
          role: 'assistant',
          content: content,
          timestamp: new Date().toISOString(),
        }
      };
    }
  },
};

// 代理相关
export const agent = {
  query: async (prompt: string, sessionId?: string, onMessage?: (chunk: string) => void): Promise<ApiResponse<QueryResponse>> => {
    if (MOCK_DATA.enabled) {
      // 模拟响应延迟
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // 如果提供了onMessage回调，模拟流式响应
      if (onMessage) {
        const mockAnswer = `这是对"${prompt}"的模拟回答。真实环境中，这里会返回由AI生成的回答。`;
        const chunks = mockAnswer.split(' ');
        
        // 模拟流式返回
        for (const chunk of chunks) {
          await new Promise(resolve => setTimeout(resolve, 200));
          onMessage(chunk + ' ');
        }
      }
      
      // 创建AI回复消息
      const aiMessage = {
        id: uuidv4(),
        role: 'assistant' as const,
        content: `这是对"${prompt}"的模拟回答。真实环境中，这里会返回由AI生成的回答。`,
        timestamp: new Date().toISOString(),
      };
      
      MOCK_DATA.messages.push(aiMessage);
      
      return {
        success: true,
        message: '查询成功',
        data: {
          answer: aiMessage.content,
          sources: ['模拟文档1', '模拟文档2'],
        },
      };
    }
    
    // 确保会话ID格式正确
    const formattedSessionId = sessionId && !sessionId.startsWith('session_') 
      ? `session_${sessionId}` 
      : sessionId;
      
    try {
      // 是否为流式响应
      const isStream = !!onMessage;
      
      if (isStream) {
        console.log('启动流式请求，参数:', {
          query: prompt,
          session_id: formattedSessionId,
          use_retrieval: true,
          stream: true
        });
        
        // 发起流式请求
        const response = await fetch(`${api.defaults.baseURL}/agents/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`,
            'Accept': 'text/event-stream',
          },
          body: JSON.stringify({
            query: prompt,
            session_id: formattedSessionId,
            use_retrieval: true,
            stream: true
          })
        });
        
        console.log('流式响应状态:', response.status, response.statusText);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        if (!response.body) {
          throw new Error('Response body is null');
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        
        // 读取流
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value, { stream: true });
          console.log('收到原始数据块:', chunk);
          
          // 处理SSE格式数据
          const lines = chunk
            .split('\n')
            .filter(line => line.trim() !== '' && line.startsWith('data: '));
            
          for (const line of lines) {
            try {
              const eventData = line.substring(6); // 去掉 "data: " 前缀
              const parsedData = JSON.parse(eventData);
              console.log('解析后的数据:', parsedData);
              
              if (parsedData.type === 'chunk') {
                // 处理内容块
                if (onMessage && typeof parsedData.content === 'string') {
                  // 内容已在服务器端解码，无需再次解码
                  onMessage(parsedData.content);
                  fullResponse += parsedData.content;
                }
              } else if (parsedData.type === 'complete') {
                // 处理完成消息
                console.log('流式响应完成');
              } else if (parsedData.type === 'error') {
                // 处理错误消息
                throw new Error(parsedData.message || '流式响应出错');
              }
            } catch (err) {
              console.error('解析SSE数据出错:', err, 'raw line:', line);
            }
          }
        }
        
        console.log('流式响应接收完成, 完整响应:', fullResponse);
        
        return {
          success: true,
          message: '查询成功',
          data: {
            answer: fullResponse || '无回答',
            sources: [] // 流式响应中可能没有来源信息
          }
        };
      } else {
        // 非流式响应
        const response = await api.post('/agents/query', { 
          query: prompt,
          session_id: formattedSessionId,
          use_retrieval: true,
          stream: false
        });
        
        return {
          success: true,
          message: '查询成功',
          data: {
            answer: response.data.answer || response.data.response || '无回答',
            sources: response.data.sources || []
          }
        };
      }
    } catch (error: any) {
      console.error('查询失败:', error);
      return {
        success: false,
        message: error.message || '查询失败',
        data: {
          answer: '抱歉，处理您的请求时发生错误。',
          sources: []
        }
      };
    }
  },
  uploadDocument: async (file: File): Promise<ApiResponse<{ id: string }>> => {
    if (MOCK_DATA.enabled) {
      // 模拟上传延迟
      await new Promise(resolve => setTimeout(resolve, 1500));
      return {
        success: true,
        message: '文档上传成功',
        data: {
          id: uuidv4(),
        },
      };
    }
    
    // 从文件内容中提取文本
    const text = await file.text();
    
    // 按照后端API要求调整请求格式
    const response = await api.post('/agents/upload', { 
      texts: [text],
      metadatas: [{ filename: file.name, source: 'upload' }]
    });
    
    return {
      success: true,
      message: '文档上传成功',
      data: {
        id: response.data.document_ids[0] || uuidv4(),
      }
    };
  },
};

// 新增设置相关API
export const settings = {
  getConfig: async (): Promise<ApiResponse<any>> => {
    if (MOCK_DATA.enabled) {
      return {
        success: true,
        message: '获取配置成功',
        data: {
          memory_config: {
            max_token_limit: 2000,
            return_messages: true,
            return_source_documents: true,
            k: 5
          }
        },
      };
    }
    
    const response = await api.get('/agents/config');
    return response.data;
  },
  
  updateConfig: async (config: any): Promise<ApiResponse<any>> => {
    if (MOCK_DATA.enabled) {
      return {
        success: true,
        message: '更新配置成功',
        data: config,
      };
    }
    
    const response = await api.post('/agents/config', config);
    return response.data;
  },
};

export default api; 