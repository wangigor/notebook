import React, { useState } from 'react';
import { Timeline, Typography, Progress, Spin, Card, Tag, Collapse } from '@douyinfe/semi-ui';
import { 
  IconTickCircle, 
  IconClose, 
  IconAlertTriangle, 
  IconHourglass, 
  IconInfoCircle, 
  IconChevronUp, 
  IconChevronDown,
  IconFile,
  IconArticle,
  IconListView,
  IconSetting,
  IconSaveStroked
} from '@douyinfe/semi-icons';
import './TaskStepList.css';

const { Text, Title } = Typography;

// 任务步骤状态类型
type TaskStepStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';

// 任务步骤接口定义
interface TaskStep {
  name: string;
  description?: string;
  status: TaskStepStatus;
  progress: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  metadata?: Record<string, any>;
  output?: Record<string, any>;
  step_type?: string;
}

interface TaskStepListProps {
  steps: TaskStep[];
  currentStepIndex?: number;
  // 新增折叠控制配置
  collapsible?: boolean; // 是否允许折叠整个列表
  defaultExpanded?: boolean; // 列表默认是否展开
  // 新增外部控制展开/折叠的属性
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

/**
 * 任务步骤列表组件
 * 以垂直步骤条的形式展示任务处理步骤
 */
export function TaskStepList({ 
  steps, 
  currentStepIndex = -1, 
  collapsible = false, 
  defaultExpanded = true,
  isExpanded,
  onToggleExpand
}: TaskStepListProps) {
  // 状态到图标的映射
  const statusIcons = {
    PENDING: <IconHourglass style={{ color: '#AAA' }} />,
    RUNNING: <Spin size="small" />,
    COMPLETED: null, // 移除COMPLETED状态的对号图标
    FAILED: <IconClose style={{ color: '#ff4d4f' }} />,
    SKIPPED: <IconAlertTriangle style={{ color: '#faad14' }} />
  };
  
  // 步骤类型到图标的映射，增大图标尺寸
  const stepTypeIcons: Record<string, React.ReactNode> = {
    'document_verification': <IconTickCircle size="default" />,
    'file_upload': <IconFile size="default" />,
    'text_extraction': <IconArticle size="default" />,
    'text_preprocessing': <IconListView size="default" />,
    'vectorization': <IconSetting size="default" />,
    'vector_storage': <IconSaveStroked size="default" />,
    // 兼容旧的步骤类型名称
    '文档验证': <IconTickCircle size="default" />,
    '文件上传': <IconFile size="default" />,
    '文本提取': <IconArticle size="default" />,
    '文本预处理': <IconListView size="default" />,
    '向量化处理': <IconSetting size="default" />,
    '保存向量': <IconSaveStroked size="default" />
  };
  
  // 使用外部状态或内部状态控制列表是否展开
  const [internalExpanded, setInternalExpanded] = useState(true);
  const isListExpanded = isExpanded !== undefined ? isExpanded : internalExpanded;
  
  // 切换列表展开状态，如果有外部控制就调用外部方法，否则使用内部状态
  const toggleListExpanded = () => {
    if (onToggleExpand) {
      onToggleExpand();
    } else {
      setInternalExpanded(!internalExpanded);
    }
  };
  
  // 已展开的步骤ID集合 - 默认为空集合（步骤元数据默认关闭）
  const [expandedStepIds, setExpandedStepIds] = useState<Set<number>>(new Set());
  
  // 切换单个步骤详情展开状态
  const toggleStepDetail = (stepId: number) => {
    setExpandedStepIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(stepId)) {
        newSet.delete(stepId);
      } else {
        newSet.add(stepId);
      }
      return newSet;
    });
  };
  
  // 计算总体进度
  const calculateOverallProgress = (steps: TaskStep[]): number => {
    if (steps.length === 0) return 0;
    
    const completedSteps = steps.filter(step => step.status === 'COMPLETED').length;
    const runningSteps = steps.filter(step => step.status === 'RUNNING');
    
    let progress = (completedSteps / steps.length) * 100;
    
    // 如果有正在运行的步骤，将其进度计入总进度
    if (runningSteps.length > 0) {
      const runningProgress = runningSteps.reduce((sum, step) => sum + step.progress, 0) / runningSteps.length;
      progress += (runningProgress / 100) * (1 / steps.length) * 100;
    }
    
    return Math.min(Math.round(progress), 100);
  };
  
  // 格式化时间函数
  const formatTime = (timeStr?: string) => {
    if (!timeStr) return '未开始';
    
    const date = new Date(timeStr);
    return new Intl.DateTimeFormat('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }).format(date);
  };
  
  // 计算持续时间
  const getDuration = (start?: string, end?: string) => {
    if (!start) return '未开始';
    
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const durationMs = endTime - startTime;
    
    if (durationMs < 1000) return `${durationMs}毫秒`;
    
    if (durationMs < 60000) {
      const seconds = (durationMs / 1000).toFixed(1);
      return `${seconds}秒`;
    }
    
    if (durationMs < 3600000) {
      const minutes = Math.floor(durationMs / 60000);
      const seconds = Math.floor((durationMs % 60000) / 1000);
      return `${minutes}分${seconds}秒`;
    }
    
    const hours = Math.floor(durationMs / 3600000);
    const minutes = Math.floor((durationMs % 3600000) / 60000);
    return `${hours}时${minutes}分`;
  };

  // 添加辅助函数，将步骤状态映射到Timeline.Item的type
  const getTimelineItemType = (status: TaskStepStatus): "default" | "ongoing" | "success" | "warning" | "error" => {
    switch (status) {
      case 'RUNNING':
        return 'ongoing';
      case 'COMPLETED':
        return 'success';
      case 'FAILED':
        return 'error';
      case 'SKIPPED':
        return 'warning';
      default:
        return 'default';
    }
  };

  // 添加辅助函数，根据状态获取对应的dot
  const getStatusDot = (status: TaskStepStatus): React.ReactNode => {
    switch (status) {
      case 'RUNNING':
        return <Spin size="small" />;
      case 'PENDING':
        return <IconHourglass style={{ color: '#AAA' }} />;
      case 'FAILED':
        return <IconClose style={{ color: '#ff4d4f' }} />;
      case 'SKIPPED':
        return <IconAlertTriangle style={{ color: '#faad14' }} />;
      default:
        return null;
    }
  };

  return (
    <div className="task-step-list">
      {/* 步骤列表内容，当isListExpanded为false时隐藏 */}
      {isListExpanded && (
        <Timeline mode="center" className="task-timeline">
          {steps.map((step, index) => {
            // 获取对应步骤类型的图标
            const stepIcon = step.step_type ? stepTypeIcons[step.step_type] : null;
            
            return (
              <Timeline.Item 
                key={index}
                time={step.completed_at ? formatTime(step.completed_at) : ''}
                type={getTimelineItemType(step.status)}
                dot={stepIcon || getStatusDot(step.status)}
              >
                <div className="timeline-item-content">
                  <div className="timeline-item-header">
                    <Text strong>{step.name}</Text>
                    {statusIcons[step.status]}
                  </div>
                  
                  {step.description && (
                    <div className="timeline-item-description">
                      <Text type="secondary" size="small">{step.description}</Text>
                    </div>
                  )}
                  
                  {/* 进度条 */}
                  {(step.status === 'RUNNING' || step.status === 'COMPLETED') && (
                    <div className="timeline-item-progress">
                      <Progress 
                        percent={step.progress} 
                        size="small" 
                        strokeWidth={3}
                        showInfo
                      />
                    </div>
                  )}
                  
                  {/* 时间信息 */}
                  <div className="timeline-item-time-info">
                    {step.started_at && (
                      <div className="timeline-time-item">
                        <Text type="tertiary" size="small">开始: {formatTime(step.started_at)}</Text>
                      </div>
                    )}
                    {step.started_at && (
                      <div className="timeline-time-item">
                        <Text type="tertiary" size="small">
                          耗时: {getDuration(step.started_at, step.completed_at)}
                        </Text>
                      </div>
                    )}
                  </div>
                  
                  {/* 错误信息 */}
                  {step.error_message && (
                    <div className="timeline-item-error">
                      <Text type="danger" size="small">{step.error_message}</Text>
                    </div>
                  )}
                  
                  {/* 步骤详情折叠控制 */}
                  {(step.metadata || step.output) && (
                    <div 
                      className="timeline-item-detail-toggle" 
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleStepDetail(index);
                      }}
                    >
                      <Text type="tertiary" size="small">
                        {expandedStepIds.has(index) ? "隐藏详情" : "查看详情"}
                      </Text>
                      {expandedStepIds.has(index) ? <IconChevronUp size="small" /> : <IconChevronDown size="small" />}
                    </div>
                  )}
                  
                  {/* 步骤元数据与输出，仅在步骤被展开时显示 */}
                  {expandedStepIds.has(index) && (step.metadata || step.output) && (
                    <div className="timeline-item-detail-content">
                      {step.metadata && (
                        <div className="timeline-metadata">
                          <Text strong size="small">步骤元数据</Text>
                          <Card className="step-detail-card">
                            <pre className="step-detail-json">
                              {JSON.stringify(step.metadata, null, 2)}
                            </pre>
                          </Card>
                        </div>
                      )}
                      
                      {step.output && (
                        <div className="timeline-output">
                          <Text strong size="small">步骤输出</Text>
                          <Card className="step-detail-card">
                            <pre className="step-detail-json">
                              {JSON.stringify(step.output, null, 2)}
                            </pre>
                          </Card>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </Timeline.Item>
            );
          })}
        </Timeline>
      )}
    </div>
  );
} 