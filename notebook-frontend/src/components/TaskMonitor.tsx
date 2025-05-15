import React, { useState, useEffect } from 'react';
import { Card, Progress, Typography, Space, Button, Empty, Spin, Divider, Notification } from '@douyinfe/semi-ui';
import { 
  IconRefresh, 
  IconClose, 
  IconFile,
  IconTickCircle,
  IconArticle,
  IconListView,
  IconSetting,
  IconSaveStroked,
  IconChevronUp,
  IconChevronDown
} from '@douyinfe/semi-icons';
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
  compact?: boolean;
}

/**
 * 任务监控组件
 * 显示任务详情、进度和步骤状态，支持WebSocket实时更新
 */
export function TaskMonitor({ 
  taskId, 
  onClose, 
  showHeader = true, 
  autoRefresh = true,
  compact = true
}: TaskMonitorProps) {
  const [task, setTask] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { connected, taskUpdate, reconnect } = useTaskWebSocket(taskId);
  // 新增状态用于控制步骤列表的展开/折叠
  const [isStepsExpanded, setIsStepsExpanded] = useState(true);
  
  // 切换步骤列表展开状态
  const toggleStepsExpanded = () => {
    setIsStepsExpanded(!isStepsExpanded);
  };
  
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
        style={{ marginBottom: '12px' }}
        headerStyle={{ padding: compact ? '12px' : '16px' }}
        bodyStyle={{ padding: 0 }}
        header={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ marginBottom: compact ? '4px' : '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Title heading={compact ? 6 : 5} style={{ margin: 0 }}>
                  {task.name || `任务 ${task.id}`}
                </Title>
                <TaskStatusBadge status={task.status as TaskStatus} showText={!compact} />
              </div>
              {task.document && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <IconFile size="small" />
                  <Text type="secondary" size={compact ? "small" : "normal"}>{task.document.name}</Text>
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
        <div 
          style={{ padding: compact ? '0 12px 12px' : '0 16px 16px', cursor: 'pointer' }} 
          onClick={toggleStepsExpanded}
        >
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <Progress 
              percent={task.progress || 0} 
              stroke={getProgressColor(task.status)}
              style={{ 
                marginBottom: '8px', 
                maxWidth: '50%', 
                minWidth: '200px',
                display: 'inline-block' 
              }}
              size={compact ? "small" : "default"}
            />
            <div style={{ marginLeft: '8px' }}>
              {isStepsExpanded ? <IconChevronUp /> : <IconChevronDown />}
            </div>
          </div>
          <Text type="secondary" size={compact ? "small" : "normal"} style={{ marginLeft: '12px' }}>
            {task.description || '处理中...'}
            {task.error_message && <Text type="danger" size={compact ? "small" : "normal"}> - {task.error_message}</Text>}
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
      <div style={{ marginBottom: compact ? '12px' : '16px' }}>
        <Text type={connected ? 'success' : 'tertiary'} size={compact ? "small" : "normal"}>
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
  
  // 渲染步骤的标准图标
  const renderStepTypeIcons = () => {
    const iconStyle = { verticalAlign: 'middle' };
    return (
      <div className="step-type-icons" style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        flexWrap: 'wrap',
        margin: compact ? '12px 0' : '16px 0',
        padding: '8px 12px',
        backgroundColor: 'var(--semi-color-fill-0)',
        borderRadius: '6px',
        fontSize: compact ? '12px' : '14px'
      }}>
        <div className="step-icon-item" style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px', marginRight: '8px' }}>
          <IconTickCircle size="default" style={iconStyle} /> <Text>文档验证</Text>
        </div>
        <div className="step-icon-item" style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px', marginRight: '8px' }}>
          <IconFile size="default" style={iconStyle} /> <Text>文件上传</Text>
        </div>
        <div className="step-icon-item" style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px', marginRight: '8px' }}>
          <IconArticle size="default" style={iconStyle} /> <Text>文本提取</Text>
        </div>
        <div className="step-icon-item" style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px', marginRight: '8px' }}>
          <IconListView size="default" style={iconStyle} /> <Text>文本预处理</Text>
        </div>
        <div className="step-icon-item" style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px', marginRight: '8px' }}>
          <IconSetting size="default" style={iconStyle} /> <Text>向量化处理</Text>
        </div>
        <div className="step-icon-item" style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px', marginRight: '8px' }}>
          <IconSaveStroked size="default" style={iconStyle} /> <Text>保存向量</Text>
        </div>
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
      
      {/* 步骤类型图标说明 */}
      {renderStepTypeIcons()}
      
      <TimeInfoCard 
        createdAt={task.created_at}
        startedAt={task.started_at}
        completedAt={task.completed_at}
        compact={compact}
      />
      
      <Card 
        title={<Text size={compact ? "small" : "normal"} strong>任务步骤</Text>}
        style={{ marginBottom: '16px' }}
        headerStyle={{ padding: compact ? '10px 16px' : '12px 16px' }}
        bodyStyle={{ padding: compact ? '8px 16px 16px' : '12px 16px 16px' }}
      >
        {task.steps && task.steps.length > 0 ? (
          <TaskStepList 
            steps={task.steps} 
            currentStepIndex={getCurrentStepIndex()} 
            collapsible={false}
            isExpanded={isStepsExpanded}
            onToggleExpand={toggleStepsExpanded}
          />
        ) : (
          <Empty description="暂无任务步骤信息" />
        )}
      </Card>
    </div>
  );
}