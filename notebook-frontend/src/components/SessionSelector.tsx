import { FC, useState, useEffect } from 'react';
import { Button, Empty, Input, List, Modal, Popconfirm, Spin, Typography, Toast } from '@douyinfe/semi-ui';
import { IconEdit, IconDelete, IconPlus, IconSave } from '@douyinfe/semi-icons';
import { ChatSession } from '../types';
import { chat } from '../api/api';

interface SessionSelectorProps {
  selectedSessionId: string | null;
  onSessionSelect: (session: ChatSession) => void;
  onSessionCreate: () => void;
}

const SessionSelector: FC<SessionSelectorProps> = ({
  selectedSessionId,
  onSessionSelect,
  onSessionCreate,
}) => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editedSessionName, setEditedSessionName] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // 获取会话列表
  const fetchSessions = async () => {
    try {
      setLoading(true);
      const response = await chat.getSessions();
      if (response.success) {
        setSessions(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  // 开始编辑会话名称
  const handleEditStart = (session: ChatSession) => {
    setEditingSessionId(session.id);
    setEditedSessionName(session.name);
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
            s.id === editingSessionId ? { ...s, name: editedSessionName } : s
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
            onClick={() => onSessionSelect(session)}
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
                  <Typography.Text ellipsis>{session.name}</Typography.Text>
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