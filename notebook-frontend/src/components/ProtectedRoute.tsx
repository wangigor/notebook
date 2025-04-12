import { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Spin } from '@douyinfe/semi-ui';

interface ProtectedRouteProps {
  children: ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  // 如果正在加载认证状态，显示加载指示器
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Spin size="large" />
        <span className="ml-3">验证身份中...</span>
      </div>
    );
  }

  // 如果用户未认证，重定向到登录页面
  if (!isAuthenticated) {
    // 保存当前路径，以便登录后可以返回
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 用户已认证，渲染子组件
  return <>{children}</>;
} 