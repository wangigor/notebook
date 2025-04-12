import { useState } from 'react';
import { Form, Button, Card, Typography, Tabs, TabPane, Input } from '@douyinfe/semi-ui';
import { IconLock, IconUser, IconMail } from '@douyinfe/semi-icons';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;

export default function Login() {
  const [activeTab, setActiveTab] = useState('login');
  const [loading, setLoading] = useState(false);
  const [formApi, setFormApi] = useState<any>(null);
  
  const { login, register } = useAuth();
  const navigate = useNavigate();

  // 处理登录
  const handleLogin = async (values: any) => {
    setLoading(true);
    try {
      const success = await login(values.username, values.password);
      if (success) {
        navigate('/');
      }
    } finally {
      setLoading(false);
    }
  };

  // 处理注册
  const handleRegister = async (values: any) => {
    // 手动验证密码
    if (values.password !== values.confirmPassword) {
      formApi.setError('confirmPassword', '两次输入的密码不一致');
      setLoading(false);
      return;
    }
    
    setLoading(true);
    try {
      const success = await register(values.username, values.email, values.password);
      if (success) {
        // 注册成功后切换到登录标签
        setActiveTab('login');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page flex items-center justify-center min-h-screen bg-gray-100 p-4">
      <Card className="w-full max-w-md bg-white rounded-lg shadow-lg p-6">
        <div className="text-center mb-6">
          <Title heading={3}>Notebook AI</Title>
          <Text type="secondary">您的个人知识库助手</Text>
        </div>

        <Tabs activeKey={activeTab} onChange={setActiveTab} style={{ width: '100%' }} size="large">
          <TabPane tab="登录" itemKey="login" />
          <TabPane tab="注册" itemKey="register" />
        </Tabs>

        <div className="mt-4">
          {activeTab === 'login' ? (
            <Form onSubmit={handleLogin} style={{ width: '100%' }}>
              <Form.Input
                field="username"
                label="用户名"
                placeholder="请输入用户名"
                prefix={<IconUser />}
                rules={[{ required: true, message: '请输入用户名' }]}
                size="large"
              />
              <Form.Input
                field="password"
                label="密码"
                placeholder="请输入密码"
                prefix={<IconLock />}
                mode="password"
                rules={[{ required: true, message: '请输入密码' }]}
                size="large"
              />
              <Button 
                type="primary" 
                htmlType="submit" 
                theme="solid" 
                loading={loading} 
                block 
                size="large"
                className="mt-6"
              >
                登录
              </Button>
            </Form>
          ) : (
            <Form 
              onSubmit={handleRegister} 
              style={{ width: '100%' }}
              getFormApi={setFormApi}
            >
              <Form.Input
                field="username"
                label="用户名"
                placeholder="请输入用户名"
                prefix={<IconUser />}
                rules={[{ required: true, message: '请输入用户名' }]}
                size="large"
              />
              <Form.Input
                field="email"
                label="邮箱"
                placeholder="请输入邮箱"
                prefix={<IconMail />}
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { type: 'email', message: '请输入有效的邮箱地址' }
                ]}
                size="large"
              />
              <Form.Input
                field="password"
                label="密码"
                placeholder="请输入密码"
                prefix={<IconLock />}
                mode="password"
                rules={[
                  { required: true, message: '请输入密码' },
                  { min: 6, message: '密码长度不能少于6位' }
                ]}
                size="large"
              />
              <Form.Input
                field="confirmPassword"
                label="确认密码"
                placeholder="请再次输入密码"
                prefix={<IconLock />}
                mode="password"
                rules={[
                  { required: true, message: '请确认密码' }
                ]}
                size="large"
              />
              <Button 
                type="primary" 
                htmlType="submit" 
                theme="solid" 
                loading={loading} 
                block 
                size="large"
                className="mt-6"
              >
                注册
              </Button>
            </Form>
          )}

          <div className="mt-4 text-center">
            {activeTab === 'login' ? (
              <Text type="tertiary">
                还没有账号？{' '}
                <a onClick={() => setActiveTab('register')} style={{ color: '#2080f0', cursor: 'pointer' }}>
                  立即注册
                </a>
              </Text>
            ) : (
              <Text type="tertiary">
                已有账号？{' '}
                <a onClick={() => setActiveTab('login')} style={{ color: '#2080f0', cursor: 'pointer' }}>
                  去登录
                </a>
              </Text>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
} 