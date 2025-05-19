import { useState, useEffect, useRef, ReactNode } from 'react';
import { Layout, Toast, Button, Avatar, Dropdown, Badge } from '@douyinfe/semi-ui';
import { IconPlus, IconUpload, IconSetting, IconUser, IconExit, IconFile, IconMenu } from '@douyinfe/semi-icons';
import { v4 as uuidv4 } from 'uuid';
import './App.css';
import { useNavigate } from 'react-router-dom';

import SessionSelector from './components/SessionSelector';
import SemiChat from './components/SemiChat';
import DocumentUploader from './components/DocumentUploader';
import DocumentDrawer from './components/DocumentDrawer';
import SettingsDialog from './components/SettingsDialog';
import { chat, agent, documents } from './api/api';
import { ChatSession, Message } from './types';
import { useAuth } from './contexts/AuthContext';

const { Header, Sider, Content } = Layout;

// 定义DocumentDrawer组件的引用类型
interface DocumentDrawerRef {
  showUploader?: () => void;
}

function App() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [documentCount, setDocumentCount] = useState(0);
  
  // 抽屉状态
  const [showDocumentDrawer, setShowDocumentDrawer] = useState(false);
  const [documentDrawerWidth, setDocumentDrawerWidth] = useState(() => {
    // 默认使用窗口宽度的60%
    const defaultWidth = Math.round(window.innerWidth * 0.6);
    // 从本地存储加载保存的值，如果存在的话
    const savedWidth = localStorage.getItem('documentDrawerWidth');
    return savedWidth ? parseInt(savedWidth) : defaultWidth;
  });
  
  const documentDrawerRef = useRef<DocumentDrawerRef>(null);

  // 从本地存储加载抽屉状态
  useEffect(() => {
    const savedVisible = localStorage.getItem('documentDrawerVisible');
    if (savedVisible === 'true') {
      setShowDocumentDrawer(true);
    }
  }, []);

  // 保存抽屉状态到本地存储
  useEffect(() => {
    localStorage.setItem('documentDrawerVisible', String(showDocumentDrawer));
  }, [showDocumentDrawer]);
  
  // 保存抽屉宽度到本地存储
  useEffect(() => {
    localStorage.setItem('documentDrawerWidth', String(documentDrawerWidth));
  }, [documentDrawerWidth]);
  
  // 监听窗口大小变化，动态调整抽屉宽度
  useEffect(() => {
    const handleResize = () => {
      // 如果未显示且宽度值已保存，则不更新
      if (!showDocumentDrawer && localStorage.getItem('documentDrawerWidth')) {
        return;
      }
      // 更新宽度为窗口宽度的60%
      const newWidth = Math.round(window.innerWidth * 0.6);
      setDocumentDrawerWidth(newWidth);
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [showDocumentDrawer]);

  // 初始化：获取会话列表，只在App组件中获取一次
  useEffect(() => {
    if (isAuthenticated) {
      fetchSessions();
      updateDocumentCount();
    }
  }, [isAuthenticated]);

  // 获取会话列表
  const fetchSessions = async () => {
    try {
      setLoading(true);
      const response = await chat.getSessions();
      if (response.success) {
        // 对会话按更新时间排序，最新的在前面
        const sortedSessions = [...response.data].sort((a, b) => {
          const timeA = new Date(a.updatedAt || a.createdAt || 0).getTime();
          const timeB = new Date(b.updatedAt || b.createdAt || 0).getTime();
          return timeB - timeA;
        });
        
        setSessions(sortedSessions);
        // 如果有会话，默认选择第一个
        if (sortedSessions.length > 0 && !currentSession) {
          handleSessionSelect(sortedSessions[0]);
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
    // 不再在这里加载消息，由SemiChat组件负责
    const sessionId = session.id || session.session_id;
    if (!sessionId) {
      Toast.error('会话ID无效');
      setError('会话ID无效，无法加载消息');
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
  
  // 更新文档计数
  const updateDocumentCount = async () => {
    try {
      const response = await documents.getDocuments({ limit: 1 });
      if (response.success) {
        setDocumentCount(response.data.total);
      }
    } catch (error) {
      console.error('获取文档计数失败', error);
    }
  };
  
  // 切换文档抽屉显示状态
  const toggleDocumentDrawer = () => {
    setShowDocumentDrawer(!showDocumentDrawer);
  };
  
  // 处理抽屉宽度变化
  const handleDrawerWidthChange = (width: number) => {
    setDocumentDrawerWidth(width);
  };
  
  // 处理上传文档
  const handleUploadDocument = () => {
    navigate('/upload');
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
            icon={<IconFile />}
            theme="light"
            onClick={toggleDocumentDrawer}
            style={{ marginRight: '8px' }}
            className="document-toggle-btn"
          >
            文档
            {documentCount > 0 && (
              <Badge 
                count={documentCount} 
                overflowCount={99} 
                className="badge-indicator"
                dot={false}
              />
            )}
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
              <SessionSelector
                selectedSessionId={currentSession?.id || null}
                onSessionSelect={handleSessionSelect}
                onSessionCreate={handleCreateSession}
                sessions={sessions}
              />
            </div>
          </Sider>
        )}
        <Content className="content">
          <div className="content-inner">
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
          </div>
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
        onSuccess={updateDocumentCount}
      />

      {/* 文档抽屉 */}
      <DocumentDrawer
        visible={showDocumentDrawer}
        width={documentDrawerWidth}
        onClose={() => setShowDocumentDrawer(false)}
        onWidthChange={handleDrawerWidthChange}
        onUploadSuccess={updateDocumentCount}
      />
    </Layout>
  );
}

export default App;
