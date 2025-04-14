import { FC, useState, useEffect } from 'react';
import { Button, Empty, Input, List, Modal, Popconfirm, Spin, Typography, Toast } from '@douyinfe/semi-ui';
import { IconEdit, IconDelete, IconPlus, IconSave } from '@douyinfe/semi-icons';
import { ChatSession } from '../types';
import { chat } from '../api/api';

interface SessionSelectorProps {
  selectedSessionId: string | null;
  onSessionSelect: (session: ChatSession) => void;
  onSessionCreate: () => void;
  sessions?: ChatSession[]; // 添加可选的sessions参数
}

const SessionSelector: FC<SessionSelectorProps> = ({
  selectedSessionId,
  onSessionSelect,
  onSessionCreate,
  sessions: propSessions, // 接收从父组件传入的sessions
}) => {
  const [sessions, setSessions] = useState<ChatSession[]>(propSessions || []);
  const [loading, setLoading] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editedSessionName, setEditedSessionName] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // 当props中的sessions变化时更新本地状态
  useEffect(() => {
    if (propSessions) {
      setSessions(propSessions);
    }
  }, [propSessions]);

  // 只在propSessions未提供时获取会话列表
  useEffect(() => {
    if (!propSessions) {
      fetchSessions();
    }
  }, [propSessions]);

  // 获取会话列表 (只在未从props接收到sessions时使用)
  const fetchSessions = async () => {
    try {
      setLoading(true);
      console.log('SessionSelector: 正在获取会话列表');
      
      const response = await chat.getSessions();
      console.log('SessionSelector: 会话列表响应:', response);
      
      if (response.success) {
        if (Array.isArray(response.data)) {
          console.log('SessionSelector: 成功获取会话列表，数量:', response.data.length);
          
          // 对会话按更新时间排序，最新的在前面
          const sortedSessions = [...response.data].sort((a, b) => {
            const timeA = new Date(a.updatedAt || a.createdAt || 0).getTime();
            const timeB = new Date(b.updatedAt || b.createdAt || 0).getTime();
            return timeB - timeA;
          });
          
          setSessions(sortedSessions);
        } else {
          console.error('SessionSelector: 会话列表格式不正确');
          Toast.warning('会话列表格式不正确');
          setSessions([]);
        }
      } else {
        console.error('SessionSelector: 获取会话列表失败:', response.message);
        Toast.error(`获取会话列表失败: ${response.message}`);
        setSessions([]);
      }
    } catch (error) {
      console.error('SessionSelector: 获取会话列表异常:', error);
      Toast.error('获取会话列表失败，请刷新页面重试');
      setSessions([]);
    } finally {
      setLoading(false);
    }
  };

  // 开始编辑会话名称
  const handleEditStart = (session: ChatSession) => {
    setEditingSessionId(session.id);
    setEditedSessionName(session.title || '');
  };

  // 保存编辑的会话名称
  const handleEditSave = async () => {
    if (!editingSessionId || !editedSessionName.trim()) return;

    try {
      const response = await chat.updateSession(editingSessionId, editedSessionName);
      if (response.success) {
        // 更新本地状态
        setSessions(
          sessions.map((s) =>
            s.id === editingSessionId ? { ...s, title: editedSessionName } : s
          )
        );
        setEditingSessionId(null);
      }
    } catch (error) {
      console.error('Failed to update session:', error);
    }
  };

  // 删除会话
  const handleDelete = async (sessionId: string) => {
    try {
      const response = await chat.deleteSession(sessionId);
      if (response.success) {
        setSessions(sessions.filter((s) => s.id !== sessionId));
        if (selectedSessionId === sessionId) {
          // 如果删除的是当前选中的会话，选择第一个会话或创建新会话
          if (sessions.length > 1) {
            const nextSession = sessions.find((s) => s.id !== sessionId);
            if (nextSession) {
              onSessionSelect(nextSession);
            }
          } else {
            onSessionCreate();
          }
        }
      } else {
        // 显示错误信息
        console.error('删除会话失败:', response.message);
        
        // 导入Toast
        Toast.error(`删除会话失败: ${response.message}`);
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
      
      // 导入Toast
      Toast.error('删除会话失败，请重试');
    }
  };

  if (loading && sessions.length === 0) {
    return (
      <div className="flex justify-center items-center p-4">
        <Spin size="middle" />
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="p-4">
        <Empty
          title="没有会话"
          description="创建一个新会话开始对话"
          style={{ padding: '24px 0' }}
        />
        <Button
          icon={<IconPlus />}
          theme="solid"
          type="primary"
          onClick={onSessionCreate}
          block
        >
          新建会话
        </Button>
      </div>
    );
  }

  return (
    <div className="sessions-container" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="session-header flex justify-between items-center p-3">
        <Typography.Title heading={6} style={{ margin: 0 }}>
          会话列表
        </Typography.Title>
        <Button
          icon={<IconPlus />}
          type="primary"
          theme="solid"
          size="small"
          onClick={onSessionCreate}
        />
      </div>

      <List
        className="session-list"
        style={{ flex: 1, overflowY: 'auto' }}
        dataSource={sessions}
        renderItem={(session) => (
          <List.Item
            className={`session-item ${selectedSessionId === session.id ? 'active' : ''}`}
            onClick={() => {
              console.log('选择会话:', session);
              onSessionSelect(session);
            }}
            header={
              <div className="flex items-center gap-2">
                {editingSessionId === session.id ? (
                  <Input
                    value={editedSessionName}
                    onChange={setEditedSessionName}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleEditSave();
                      }
                    }}
                    autoFocus
                    size="small"
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <Typography.Text ellipsis>{session.title || '无标题'}</Typography.Text>
                )}
              </div>
            }
            main={
              <div className="session-actions flex gap-2">
                {editingSessionId === session.id ? (
                  <Button
                    icon={<IconSave />}
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEditSave();
                    }}
                  />
                ) : (
                  <Button
                    icon={<IconEdit />}
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEditStart(session);
                    }}
                  />
                )}
                <Popconfirm
                  title="确定要删除这个会话吗？"
                  content="所有相关消息都将被删除"
                  onConfirm={(e) => {
                    e?.stopPropagation();
                    handleDelete(session.id);
                  }}
                  okText="删除"
                  cancelText="取消"
                >
                  <Button
                    icon={<IconDelete />}
                    size="small"
                    type="danger"
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              </div>
            }
          />
        )}
      />
    </div>
  );
};

export default SessionSelector; 