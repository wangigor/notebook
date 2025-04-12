import { useState, useEffect } from 'react';
import { Layout, Nav, Toast, Button, Spin, Avatar, Dropdown } from '@douyinfe/semi-ui';
import { IconPlus, IconUpload, IconSetting, IconUser, IconExit } from '@douyinfe/semi-icons';
import { v4 as uuidv4 } from 'uuid';
import './App.css';

import SessionSelector from './components/SessionSelector';
import SemiChat from './components/SemiChat';
import DocumentUploader from './components/DocumentUploader';
import SettingsDialog from './components/SettingsDialog';
import { chat, agent } from './api/api';
import { ChatSession, Message } from './types';
import { useAuth } from './contexts/AuthContext';

const { Header, Sider, Content } = Layout;

function App() {
  const { isAuthenticated, user, logout } = useAuth();
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);

  // 初始化：获取会话列表
  useEffect(() => {
    if (isAuthenticated) {
      fetchSessions();
    }
  }, [isAuthenticated]);

  // 获取会话列表
  const fetchSessions = async () => {
    try {
      setLoading(true);
      const response = await chat.getSessions();
      if (response.success) {
        setSessions(response.data);
        // 如果有会话，默认选择第一个
        if (response.data.length > 0 && !currentSession) {
          handleSessionSelect(response.data[0]);
        }
      } else {
        Toast.error('获取会话列表失败：' + response.message);
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
      Toast.error('获取会话列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 创建新会话
  const handleCreateSession = async (): Promise<ChatSession> => {
    try {
      setLoading(true);
      setError(null);
      const name = `新对话 ${new Date().toLocaleString()}`;
      const response = await chat.createSession(name);
      
      if (response.success) {
        const newSession = response.data;
        setSessions(prev => [newSession, ...prev]);
        setCurrentSession(newSession);
        setMessages([]);
        return newSession;
      } else {
        throw new Error(response.message || '创建会话失败');
      }
    } catch (error: any) {
      console.error('Failed to create session:', error);
      Toast.error('创建会话失败：' + (error.message || '未知错误'));
      throw error;
    } finally {
      setLoading(false);
    }
  };

  // 选择会话
  const handleSessionSelect = async (session: ChatSession) => {
    setCurrentSession(session);
    // 确保使用正确的会话ID
    const sessionId = session.id || session.session_id;
    if (sessionId) {
      try {
        // 确保ID格式正确
        const formattedSessionId = sessionId.startsWith('session_') ? sessionId : `session_${sessionId}`;
        await loadSessionMessages(formattedSessionId);
      } catch (error: any) {
        console.error('加载消息失败:', error);
        Toast.error('加载消息失败，请重试');
        
        // 如果会话不存在，创建一个新会话
        if (error.message && (error.message.includes('会话不存在') || error.message.includes('404'))) {
          Toast.info('正在创建新会话...');
          await handleCreateSession();
        } else {
          setError('会话加载失败，请尝试选择其他会话或创建新会话');
        }
      }
    } else {
      Toast.error('会话ID无效');
      setError('会话ID无效，无法加载消息');
    }
  };

  // 加载会话消息
  const loadSessionMessages = async (sessionId: string) => {
    try {
      setLoading(true);
      // 确保会话ID格式正确
      const formattedSessionId = sessionId.startsWith('session_') ? sessionId : `session_${sessionId}`;
      // 使用会话ID查询消息
      const response = await chat.getMessages(formattedSessionId);
      if (response.success) {
        setMessages(response.data);
      } else {
        Toast.error('加载消息失败：' + response.message);
      }
    } catch (error: any) {
      console.error('Failed to load messages:', error);
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      Toast.error('加载消息失败：' + errorMessage);
      setError('无法加载消息，请重试');
    } finally {
      setLoading(false);
    }
  };

  // 处理登出
  const handleLogout = async () => {
    try {
      await logout();
      // 清空状态
      setCurrentSession(null);
      setSessions([]);
      setMessages([]);
    } catch (error) {
      console.error('登出失败:', error);
    }
  };

  if (!isAuthenticated) {
    return null; // 未认证时不渲染内容，由AuthProvider处理重定向
  }

  return (
    <Layout className="app-container">
      <Header className="header">
        <div className="header-left">
          <div className="logo">Notebook AI</div>
        </div>
        <div className="header-right">
          <Button
            icon={<IconPlus />}
            theme="light"
            onClick={handleCreateSession}
            style={{ marginRight: '8px' }}
          >
            新会话
          </Button>
          <Button
            icon={<IconUpload />}
            theme="light"
            onClick={() => setShowUploader(true)}
            style={{ marginRight: '8px' }}
          >
            上传文档
          </Button>
          <Button
            icon={<IconSetting />}
            theme="light"
            onClick={() => setShowSettings(true)}
            style={{ marginRight: '8px' }}
          >
            设置
          </Button>
          <Dropdown
            position="bottomRight"
            render={
              <Dropdown.Menu>
                <Dropdown.Item icon={<IconUser />}>
                  {user?.username || 'User'}
                </Dropdown.Item>
                <Dropdown.Divider />
                <Dropdown.Item icon={<IconExit />} onClick={handleLogout}>
                  登出
                </Dropdown.Item>
              </Dropdown.Menu>
            }
          >
            <Avatar color="light-blue">{user?.username?.[0] || 'U'}</Avatar>
          </Dropdown>
        </div>
      </Header>
      <Layout>
        {showSidebar && (
          <Sider className="sidebar">
            <div className="sidebar-inner">
              <div className="sidebar-header">
                <h3>会话列表</h3>
                <Button
                  icon={<IconPlus />}
                  theme="light"
                  size="small"
                  onClick={handleCreateSession}
                />
              </div>
              <SessionSelector
                selectedSessionId={currentSession?.id || null}
                onSessionSelect={handleSessionSelect}
                onSessionCreate={handleCreateSession}
              />
            </div>
          </Sider>
        )}
        <Content className="content">
          {error ? (
            <div className="error-container">
              <p>{error}</p>
              <Button onClick={handleCreateSession}>创建新会话</Button>
            </div>
          ) : (
            <SemiChat 
              currentSession={currentSession} 
              onCreateSession={handleCreateSession} 
            />
          )}
        </Content>
      </Layout>

      {/* 设置对话框 */}
      <SettingsDialog
        visible={showSettings}
        onClose={() => setShowSettings(false)}
      />
      
      {/* 文档上传对话框 */}
      <DocumentUploader
        visible={showUploader}
        onClose={() => setShowUploader(false)}
      />
    </Layout>
  );
}

export default App;
