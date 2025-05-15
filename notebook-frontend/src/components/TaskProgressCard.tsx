import React, { useState, useEffect } from 'react';
import { Card, Progress, Typography, Space, Button, Empty, Spin, Divider, Toast } from '@douyinfe/semi-ui';
import { IconRefresh, IconFile, IconClose, IconChevronDown, IconChevronUp, IconPlus } from '@douyinfe/semi-icons';
import { useTaskWebSocket } from '../hooks/useTaskWebSocket';
import { TaskStepList } from './TaskStepList';
import { TaskStatusBadge } from './shared/TaskStatusBadge';
import { Task, TaskStatus } from '../types';
import { tasks } from '../api/api';

const { Text, Title } = Typography;

interface TaskProgressCardProps {
  documentId: number;
  taskId?: string;
}

/**
 * 文档任务进度卡片组件
 * 用于在文档管理器的展开行中显示文档的处理任务进度
 */
export const TaskProgressCard: React.FC<TaskProgressCardProps> = ({ documentId, taskId: initialTaskId }) => {
  const [task, setTask] = useState<Task | null>(null);
  const [taskId, setTaskId] = useState<string | undefined>(initialTaskId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSteps, setShowSteps] = useState(true);
  const [creatingTask, setCreatingTask] = useState(false);
  const { connected, taskUpdate, reconnect, connectionError } = useTaskWebSocket(taskId || '');

  // 根据文档ID获取最新任务
  useEffect(() => {
    if (!documentId) return;
    
    const fetchDocumentTask = async () => {
      try {
        setLoading(true);
        // 如果已有taskId，则直接获取任务详情
        if (taskId) {
          console.log(`获取任务详情: taskId=${taskId}`);
          const response = await tasks.getTask(taskId);
          if (response.success && response.data) {
            console.log('任务详情获取成功:', response.data);
            setTask(response.data);
          } else {
            console.error('获取任务详情失败:', response.message);
            setError('获取任务数据失败');
          }
        } else {
          // 否则获取文档关联的任务列表
          console.log(`获取文档关联任务: documentId=${documentId}`);
          const response = await tasks.getDocumentTasks(documentId);
          console.log('文档任务响应:', response);
          
          if (response.success && response.data && response.data.length > 0) {
            // 获取最新的任务
            const latestTask = response.data[0];
            console.log('找到最新任务:', latestTask);
            setTask(latestTask);
            setTaskId(latestTask.id);
          } else if (response.success && (!response.data || response.data.length === 0)) {
            console.log('文档无关联任务');
            setError('该文档暂无处理任务');
          } else {
            console.error('获取文档任务失败:', response.message);
            setError('获取任务数据失败');
          }
        }
      } catch (err) {
        console.error('获取任务数据发生异常:', err);
        setError(`获取任务数据失败: ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setLoading(false);
      }
    };
    
    fetchDocumentTask();
  }, [documentId, taskId]);
  
  // 处理WebSocket任务更新
  useEffect(() => {
    if (taskUpdate) {
      console.log('收到任务实时更新:', taskUpdate);
      setTask(taskUpdate as Task);
    }
  }, [taskUpdate]);

  // 手动刷新任务数据
  const handleRefresh = async () => {
    if (!taskId) return;
    
    try {
      setLoading(true);
      console.log(`手动刷新任务: taskId=${taskId}`);
      const response = await tasks.getTask(taskId);
      if (response.success && response.data) {
        console.log('刷新任务成功:', response.data);
        setTask(response.data);
      } else {
        console.error('刷新任务失败:', response.message);
        Toast.error('刷新任务数据失败');
      }
    } catch (err) {
      console.error('刷新任务数据失败:', err);
      Toast.error(`刷新失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };
  
  // 创建文档处理任务
  const handleCreateTask = async () => {
    try {
      setCreatingTask(true);
      console.log(`为文档创建处理任务: documentId=${documentId}`);
      
      // 使用API方法创建任务
      const response = await tasks.createDocumentTask(documentId);
      if (response.success && response.data) {
        console.log('创建任务成功:', response.data);
        Toast.success('已创建文档处理任务');
        setTask(response.data);
        setTaskId(response.data.id);
        setError(null);
      } else {
        console.error('创建任务失败:', response.message);
        Toast.error(`创建任务失败: ${response.message || '服务器错误'}`);
      }
    } catch (err) {
      console.error('创建任务过程中发生异常:', err);
      Toast.error(`创建任务失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setCreatingTask(false);
    }
  };
  
  // 用于刷新文档任务列表的辅助函数
  const fetchDocumentTasks = async () => {
    try {
      console.log(`刷新文档任务列表: documentId=${documentId}`);
      const response = await tasks.getDocumentTasks(documentId);
      if (response.success && response.data && response.data.length > 0) {
        const latestTask = response.data[0];
        console.log('刷新后找到最新任务:', latestTask);
        setTask(latestTask);
        setTaskId(latestTask.id);
        setError(null);
      }
    } catch (err) {
      console.error('刷新文档任务列表失败:', err);
    }
  };

  // 根据任务状态获取进度条颜色
  const getProgressColor = (status?: TaskStatus) => {
    switch (status) {
      case 'COMPLETED':
        return 'var(--semi-color-success)';
      case 'FAILED':
        return 'var(--semi-color-danger)';
      case 'CANCELLED':
        return 'var(--semi-color-warning)';
      default:
        return undefined; // 使用默认颜色
    }
  };

  // 切换步骤列表显示
  const toggleSteps = () => {
    setShowSteps(!showSteps);
  };

  // 加载中状态
  if (loading && !task) {
    return (
      <div style={{ padding: '20px 0', textAlign: 'center' }}>
        <Spin size="middle" />
        <div style={{ marginTop: '8px' }}>
          <Text>加载任务数据...</Text>
        </div>
      </div>
    );
  }

  // 错误状态
  if (error && !task) {
    return (
      <div style={{ padding: '20px 0', textAlign: 'center' }}>
        <Empty 
          image={<IconClose style={{ color: 'var(--semi-color-danger)' }} size="large" />}
          title="无法获取任务信息"
          description={error}
        />
        <Space style={{ marginTop: '12px' }}>
          {taskId && (
            <Button 
              onClick={handleRefresh}
              size="small"
            >
              重试
            </Button>
          )}
          <Button 
            type="primary"
            icon={<IconPlus />}
            onClick={handleCreateTask}
            loading={creatingTask}
            size="small"
          >
            创建处理任务
          </Button>
        </Space>
      </div>
    );
  }

  // 无任务状态
  if (!task) {
    return (
      <div style={{ padding: '20px 0', textAlign: 'center' }}>
        <Empty 
          image={<IconFile size="large" />}
          title="无处理任务"
          description="该文档目前没有关联的处理任务"
        />
        <Button 
          style={{ marginTop: '12px' }} 
          type="primary"
          icon={<IconPlus />}
          onClick={handleCreateTask}
          loading={creatingTask}
          size="small"
        >
          创建处理任务
        </Button>
      </div>
    );
  }

  return (
    <Card 
      style={{ 
        marginBottom: '16px', 
        borderTop: 'none', 
        borderLeft: 'none', 
        borderRight: 'none',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)'
      }}
      bodyStyle={{ padding: '16px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <Title heading={6} style={{ margin: 0 }}>
            {task.name || `文档处理 (${task.task_type})`}
          </Title>
          <TaskStatusBadge status={task.status} />
          {connected ? (
            <Text type="success" size="small">实时更新</Text>
          ) : connectionError ? (
            <Text type="danger" size="small">连接断开</Text>
          ) : null}
        </div>
        <Space>
          <Button 
            icon={showSteps ? <IconChevronUp /> : <IconChevronDown />} 
            onClick={toggleSteps}
            size="small"
            type="tertiary"
          >
            {showSteps ? '隐藏详情' : '显示详情'}
          </Button>
          <Button 
            icon={<IconRefresh />} 
            onClick={handleRefresh}
            size="small"
            loading={loading}
          >
            刷新
          </Button>
        </Space>
      </div>
      
      <div>
        <Progress 
          percent={task.progress || 0} 
          stroke={getProgressColor(task.status)}
          style={{ marginBottom: '8px' }}
        />
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap' }}>
          
          <Text type="tertiary" size="small">
            任务ID: {task.id}
          </Text>
        </div>
        
        {showSteps && task.steps && task.steps.length > 0 && (
          <>
            <Divider margin="8px" />
            <TaskStepList 
              steps={task.steps} 
              collapsible={true}
              defaultExpanded={true}
            />
          </>
        )}
        
        {!connected && taskId && (
          <div style={{ marginTop: '8px', textAlign: 'right' }}>
            <Button 
              type="tertiary"
              onClick={reconnect}
              size="small"
              icon={<IconRefresh />}
            >
              {connectionError ? '重新连接' : '连接实时更新'}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}; 