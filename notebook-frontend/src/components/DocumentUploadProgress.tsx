import React, { useEffect, useState } from 'react';
import { Card, Progress, Typography, Space, Tag, Button } from '@douyinfe/semi-ui';
import { IconFile, IconEyeOpened } from '@douyinfe/semi-icons';
import { TaskStatusBadge } from './shared/TaskStatusBadge';
import { useTaskWebSocket } from '../hooks/useTaskWebSocket';

const { Text, Title } = Typography;

// 任务状态类型
type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

interface DocumentUploadProgressProps {
  taskId: string;
  fileName: string;
  onViewDetails?: () => void;
  onComplete?: (success: boolean) => void;
  onClose?: () => void;
}

/**
 * 文档上传进度组件
 * 用于文档列表中展示当前正在上传/处理的文档进度
 */
export function DocumentUploadProgress({ 
  taskId, 
  fileName, 
  onViewDetails, 
  onComplete,
  onClose
}: DocumentUploadProgressProps) {
  const [showProgress, setShowProgress] = useState(true);
  const { taskUpdate, connected } = useTaskWebSocket(taskId);
  
  // 处理任务完成
  useEffect(() => {
    if (!taskUpdate) return;
    
    if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(taskUpdate.status)) {
      // 触发完成回调
      if (onComplete) {
        onComplete(taskUpdate.status === 'COMPLETED');
      }
      
      // 如果是失败或取消，等待5秒后自动关闭
      if (['FAILED', 'CANCELLED'].includes(taskUpdate.status)) {
        const timer = setTimeout(() => {
          setShowProgress(false);
          if (onClose) onClose();
        }, 5000);
        
        return () => clearTimeout(timer);
      }
    }
  }, [taskUpdate, onComplete, onClose]);
  
  // 如果不需要显示进度条，直接返回null
  if (!showProgress) return null;
  
  // 获取任务信息
  const progress = taskUpdate?.progress || 0;
  const status = taskUpdate?.status as TaskStatus || 'PENDING';
  
  // 获取当前步骤
  const getCurrentStep = () => {
    if (!taskUpdate?.steps) return null;
    
    const runningStep = taskUpdate.steps.find(step => step.status === 'RUNNING');
    if (runningStep) return runningStep;
    
    // 如果没有运行中的步骤，找最后一个完成的步骤
    for (let i = taskUpdate.steps.length - 1; i >= 0; i--) {
      if (taskUpdate.steps[i].status === 'COMPLETED') {
        return taskUpdate.steps[i];
      }
    }
    
    return taskUpdate.steps[0];
  };
  
  const currentStep = getCurrentStep();
  
  // 获取进度条颜色
  const getProgressColor = (status: TaskStatus) => {
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
  
  return (
    <Card 
      style={{ marginBottom: '16px' }}
      bodyStyle={{ padding: '12px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <IconFile />
            <Title heading={5} style={{ margin: 0 }}>
              {fileName}
            </Title>
            <TaskStatusBadge status={status} />
            {connected && <Tag size="small" color="green">实时</Tag>}
          </div>
          
          <Progress 
            percent={progress} 
            stroke={getProgressColor(status)}
            style={{ marginBottom: '8px' }}
          />
          
          <div>
            <Text type="secondary">
              {currentStep ? (
                <>
                  步骤: {currentStep.name} 
                  {currentStep.progress ? ` (${currentStep.progress}%)` : ''}
                </>
              ) : (
                '准备中...'
              )}
              {taskUpdate?.error_message && (
                <Text type="danger"> - {taskUpdate.error_message}</Text>
              )}
            </Text>
          </div>
        </div>
        
        <Space style={{ marginLeft: '16px' }}>
          {onViewDetails && (
            <Button 
              icon={<IconEyeOpened />} 
              onClick={onViewDetails}
              size="small"
            >
              详情
            </Button>
          )}
          {onClose && (
            <Button 
              onClick={onClose}
              size="small"
              type="tertiary"
            >
              关闭
            </Button>
          )}
        </Space>
      </div>
    </Card>
  );
} 