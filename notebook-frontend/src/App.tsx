import { useState, useEffect, useRef } from 'react';
import { Layout, Toast, Button, Avatar, Dropdown, Tabs, Badge } from '@douyinfe/semi-ui';
import { IconPlus, IconUpload, IconSetting, IconUser, IconExit, IconFile, IconComment } from '@douyinfe/semi-icons';
import { v4 as uuidv4 } from 'uuid';
import './App.css';

import SessionSelector from './components/SessionSelector';
import SemiChat from './components/SemiChat';
import DocumentUploader from './components/DocumentUploader';
import DocumentManager from './components/DocumentManager';
import SettingsDialog from './components/SettingsDialog';
import { chat, agent, documents } from './api/api';
import { ChatSession, Message } from './types';
import { useAuth } from './contexts/AuthContext';

const { Header, Sider, Content } = Layout;
const { TabPane } = Tabs;

// 定义DocumentManager组件的引用类型
interface DocumentManagerRef {
  showUploader?: () => void;
}

// 定义DocumentManager组件的属性
interface DocumentManagerProps {
  onUploadSuccess?: () => void;
}

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
  const [activeTab, setActiveTab] = useState<string>('chat');
  const [documentCount, setDocumentCount] = useState(0);
  
  const documentManagerRef = useRef<DocumentManagerRef>(null);

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
  
  // 处理标签切换
  const handleTabChange = (tabKey: string) => {
    setActiveTab(tabKey);
    if (tabKey === 'documents') {
      updateDocumentCount();
    }
  };
  
  // 处理上传文档
  const handleUploadDocument = () => {
    if (activeTab === 'chat') {
      // 在聊天界面，使用模态框上传
      setShowUploader(true);
    } else {
      // 在文档界面，切换到上传标签
      if (documentManagerRef.current && documentManagerRef.current.showUploader) {
        documentManagerRef.current.showUploader();
      }
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
          {activeTab === 'chat' && (
            <Button
              icon={<IconPlus />}
              theme="light"
              onClick={handleCreateSession}
              style={{ marginRight: '8px' }}
            >
              新会话
            </Button>
          )}
          <Button
            icon={<IconUpload />}
            theme="light"
            onClick={handleUploadDocument}
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
        {showSidebar && activeTab === 'chat' && (
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
          <Tabs
            type="line"
            activeKey={activeTab}
            onChange={handleTabChange}
            className="main-tabs"
          >
            <TabPane 
              tab={
                <span>
                  <IconComment style={{ marginRight: 8 }} />
                  聊天
                </span>
              } 
              itemKey="chat"
            >
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
            </TabPane>
            <TabPane 
              tab={
                <span>
                  <IconFile style={{ marginRight: 8 }} />
                  文档
                  {documentCount > 0 && (
                    <Badge count={documentCount} overflowCount={99} style={{ marginLeft: 8 }} />
                  )}
                </span>
              } 
              itemKey="documents"
            >
              <div className="document-manager-container">
                <DocumentManager 
                  onUploadSuccess={updateDocumentCount}
                />
              </div>
            </TabPane>
          </Tabs>
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
    </Layout>
  );
}

export default App;
