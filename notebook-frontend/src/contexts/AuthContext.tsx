import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { auth, getToken, clearToken } from '../api/api';
import { User } from '../types';
import { Toast } from '@douyinfe/semi-ui';

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // 检查本地存储或cookie中是否有token，用于初始化认证状态
  useEffect(() => {
    let isMounted = true;
    
    const checkAuth = async () => {
      try {
        const token = getToken();
        console.log('检查认证状态: token存在=', !!token);
        
        if (token) {
          console.log('尝试验证token...');
          try {
            const response = await auth.getCurrentUser();
            
            // 确保组件仍然挂载
            if (!isMounted) return;
            
            if (response.success && response.data) {
              console.log('验证用户成功:', response.data);
              setUser(response.data);
              setIsAuthenticated(true);
            } else {
              console.warn('验证用户失败，API返回失败信息');
              // 如果token无效，清除它
              clearToken();
              setIsAuthenticated(false);
              setUser(null);
            }
          } catch (error) {
            // 确保组件仍然挂载
            if (!isMounted) return;
            
            console.error('验证用户失败:', error);
            // 明确清除token
            clearToken();
            setIsAuthenticated(false);
            setUser(null);
          }
        } else {
          console.log('未找到token，用户未登录');
          setIsAuthenticated(false);
          setUser(null);
        }
      } catch (e) {
        console.error('认证检查过程中发生错误:', e);
      } finally {
        // 确保组件仍然挂载
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    checkAuth();
    
    // 清理函数
    return () => {
      isMounted = false;
    };
  }, []);

  // 登录函数
  const login = async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    try {
      const response = await auth.login(username, password);
      if (response.success) {
        // token已经在auth.login函数中保存到cookie和localStorage
        setUser(response.data.user);
        setIsAuthenticated(true);
        Toast.success('登录成功');
        return true;
      } else {
        Toast.error(`登录失败: ${response.message}`);
        return false;
      }
    } catch (error: any) {
      const errorMessage = error?.message || '登录失败，请重试';
      Toast.error(errorMessage);
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  // 注册函数
  const register = async (username: string, email: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    try {
      const response = await auth.register(username, email, password);
      
      console.log('注册响应:', response); // 添加日志
      
      if (response.success) {
        Toast.success('注册成功，请登录');
        return true;
      } else {
        const errorMsg = response.message || '注册失败，请重试';
        Toast.error(errorMsg);
        return false;
      }
    } catch (error: any) {
      console.error('注册错误:', error); // 添加错误日志
      
      // 处理特定的错误信息
      let errorMessage = '注册失败，请重试';
      if (error.response && error.response.data) {
        errorMessage = error.response.data.detail || error.response.data.message || errorMessage;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      Toast.error(errorMessage);
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  // 登出函数
  const logout = async (): Promise<void> => {
    setIsLoading(true);
    try {
      await auth.logout();
      setUser(null);
      setIsAuthenticated(false);
      Toast.info('您已成功登出');
    } catch (error) {
      console.error('登出失败:', error);
      Toast.error('登出失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        user,
        isLoading,
        login,
        logout,
        register,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
} 