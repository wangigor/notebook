import React, { useState, useEffect } from 'react';
import { Card, Progress, Typography, Space, Button, Empty, Spin, Divider, Notification } from '@douyinfe/semi-ui';
import { IconRefresh, IconClose, IconFile } from '@douyinfe/semi-icons';
import { useTaskWebSocket } from '../hooks/useTaskWebSocket';
import { TaskStepList } from './TaskStepList';
import { TaskStatusBadge } from './shared/TaskStatusBadge';
import { TimeInfoCard } from './shared/TimeInfoCard';
import { tasks } from '../api/api';
import { ensureTaskSteps } from '../utils/taskUtils';

const { Text, Title } = Typography;

// 任务状态枚举
type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

interface TaskMonitorProps {
  taskId: string;
  onClose?: () => void;
  showHeader?: boolean;
  autoRefresh?: boolean;
}

/**
 * 任务监控组件
 * 显示任务详情、进度和步骤状态，支持WebSocket实时更新
 */
export function TaskMonitor({ taskId, onClose, showHeader = true, autoRefresh = true }: TaskMonitorProps) {
  const [task, setTask] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { connected, taskUpdate, reconnect } = useTaskWebSocket(taskId);
  
  // 处理WebSocket任务更新
  useEffect(() => {
    if (taskUpdate) {
      setTask(taskUpdate);
    }
  }, [taskUpdate]);
  
  // 初始数据加载
  useEffect(() => {
    async function fetchTaskData() {
      try {
        setLoading(true);
        const response = await tasks.getTask(taskId);
        if (response.data) {
          setTask(response.data);
        }
      } catch (err) {
        setError(`获取任务数据失败: ${err instanceof Error ? err.message : String(err)}`);
        console.error('获取任务数据失败:', err);
      } finally {
        setLoading(false);
      }
    }
    
    fetchTaskData();

    // 设置自动刷新
    if (!autoRefresh) return;
    
    const intervalId = setInterval(async () => {
      // 已完成或失败的任务不需要继续刷新
      if (task?.status === 'COMPLETED' || task?.status === 'FAILED' || task?.status === 'CANCELLED') {
        return;
      }
      
      try {
        const response = await tasks.getTask(taskId);
        if (response.data) {
          setTask(response.data);
        }
      } catch (err) {
        console.error('刷新任务数据失败:', err);
      }
    }, 5000); // 每5秒刷新一次
    
    return () => clearInterval(intervalId);
  }, [taskId, autoRefresh, task?.status]);
  
  // 手动刷新
  const handleRefresh = async () => {
    try {
      setLoading(true);
      const response = await tasks.getTask(taskId);
      if (response.data) {
        setTask(response.data);
      }
    } catch (err) {
      Notification.error({
        title: '刷新失败',
        content: `获取任务数据失败: ${err instanceof Error ? err.message : String(err)}`,
        duration: 3
      });
    } finally {
      setLoading(false);
    }
  };
  
  // 获取当前步骤索引
  const getCurrentStepIndex = () => {
    if (!task?.steps) return -1;
    
    // 查找正在运行的步骤
    const runningIndex = task.steps.findIndex((step: any) => step.status === 'RUNNING');
    if (runningIndex !== -1) return runningIndex;
    
    // 如果没有正在运行的步骤，找到最后一个已完成的步骤
    for (let i = task.steps.length - 1; i >= 0; i--) {
      if (task.steps[i].status === 'COMPLETED') {
        return i;
      }
    }
    
    return -1;
  };
  
  // 渲染任务头部信息
  const renderTaskHeader = () => {
    if (!task) return null;
    
    return (
      <Card 
        style={{ marginBottom: '16px' }}
        headerStyle={{ padding: '16px' }}
        bodyStyle={{ padding: 0 }}
        header={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Title heading={5} style={{ margin: 0 }}>
                  {task.name || `任务 ${task.id}`}
                </Title>
                <TaskStatusBadge status={task.status as TaskStatus} />
              </div>
              {task.document && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <IconFile size="small" />
                  <Text type="secondary">{task.document.name}</Text>
                </div>
              )}
            </div>
            <Space>
              <Button 
                icon={<IconRefresh />} 
                onClick={handleRefresh}
                size="small"
                loading={loading}
              >
                刷新
              </Button>
              {onClose && (
                <Button 
                  icon={<IconClose />} 
                  onClick={onClose}
                  size="small"
                  type="tertiary"
                >
                  关闭
                </Button>
              )}
            </Space>
          </div>
        }
      >
        <div style={{ padding: '0 16px 16px' }}>
          <Progress 
            percent={task.progress || 0} 
            stroke={getProgressColor(task.status)}
            style={{ marginBottom: '8px' }}
          />
          <Text type="secondary">
            {task.description || '处理中...'}
            {task.error_message && <Text type="danger"> - {task.error_message}</Text>}
          </Text>
        </div>
      </Card>
    );
  };
  
  // 根据任务状态获取进度条颜色
  const getProgressColor = (status?: string) => {
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
  
  // 渲染WebSocket连接状态
  const renderConnectionStatus = () => {
    return (
      <div style={{ marginBottom: '16px' }}>
        <Text type={connected ? 'success' : 'tertiary'}>
          {connected ? '✓ 实时更新已连接' : '● 使用定时刷新'}
        </Text>
        {!connected && (
          <Button 
            type="tertiary"
            onClick={reconnect}
            size="small"
          >
            重连
          </Button>
        )}
      </div>
    );
  };
  
  // 主要渲染逻辑
  if (loading && !task) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center' }}>
        <Spin size="large" />
        <div style={{ marginTop: '16px' }}>
          <Text>加载任务数据...</Text>
        </div>
      </div>
    );
  }
  
  if (error && !task) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center' }}>
        <Empty 
          image={<IconClose style={{ color: 'var(--semi-color-danger)' }} size="extra-large" />}
          title="加载失败"
          description={error}
        />
        <Button 
          style={{ marginTop: '16px' }} 
          onClick={handleRefresh}
        >
          重试
        </Button>
      </div>
    );
  }
  
  if (!task) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center' }}>
        <Empty 
          title="未找到任务"
          description="无法找到指定的任务信息"
        />
      </div>
    );
  }
  
  return (
    <div className="task-monitor">
      {showHeader && renderTaskHeader()}
      
      {renderConnectionStatus()}
      
      <TimeInfoCard 
        createdAt={task.created_at}
        startedAt={task.started_at}
        completedAt={task.completed_at}
      />
      
      <Card 
        title="任务步骤"
        style={{ marginBottom: '16px' }}
      >
        {task.steps && task.steps.length > 0 ? (
          <TaskStepList 
            steps={task.steps} 
            currentStepIndex={getCurrentStepIndex()} 
            collapsible={false} 
          />
        ) : (
          <Empty description="暂无任务步骤信息" />
        )}
      </Card>
    </div>
  );
} 