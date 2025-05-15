import React, { useState } from 'react';
import { Steps, Typography, Progress, Spin, Card, Tag, Collapse } from '@douyinfe/semi-ui';
import { IconTickCircle, IconClose, IconAlertTriangle, IconHourglass, IconInfoCircle, IconChevronUp, IconChevronDown } from '@douyinfe/semi-icons';
import './TaskStepList.css';

const { Step } = Steps;
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
}

/**
 * 任务步骤列表组件
 * 以垂直步骤条的形式展示任务处理步骤
 */
export function TaskStepList({ 
  steps, 
  currentStepIndex = -1, 
  collapsible = false, 
  defaultExpanded = true 
}: TaskStepListProps) {
  // 状态到图标的映射
  const statusIcons = {
    PENDING: <IconHourglass style={{ color: '#AAA' }} />,
    RUNNING: <Spin size="small" />,
    COMPLETED: <IconTickCircle style={{ color: '#52c41a' }} />,
    FAILED: <IconClose style={{ color: '#ff4d4f' }} />,
    SKIPPED: <IconAlertTriangle style={{ color: '#faad14' }} />
  };
  
  // 列表整体是否展开
  const [listExpanded, setListExpanded] = useState(defaultExpanded);
  
  // 已展开的步骤ID集合
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
  
  // 格式化时间函数
  const formatTime = (timeStr?: string) => {
    if (!timeStr) return '未开始';
    
    const date = new Date(timeStr);
    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
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

  return (
    <div className="task-step-list">
      {/* 如果可折叠，显示折叠头部 */}
      {collapsible && (
        <div 
          className="step-list-header"
          onClick={() => setListExpanded(!listExpanded)}
        >
          <div className="header-title">
            <Text strong>处理步骤</Text>
          </div>
          <div className="header-icon">
            {listExpanded ? <IconChevronUp /> : <IconChevronDown />}
          </div>
        </div>
      )}
      
      {/* 步骤列表内容，当listExpanded为false时隐藏 */}
      {(!collapsible || listExpanded) && (
        <Steps direction="vertical" current={currentStepIndex}>
          {steps.map((step, index) => (
            <Step 
              key={index}
              title={
                <div className="step-title">
                  <Text>{step.name}</Text>
                  {statusIcons[step.status]}
                  {step.step_type && (
                    <Tag size="small" color="blue">{step.step_type}</Tag>
                  )}
                </div>
              }
              description={
                <div>
                  {step.description && (
                    <div className="step-description">
                      <Text type="secondary">{step.description}</Text>
                    </div>
                  )}
                  
                  {/* 进度条 */}
                  {(step.status === 'RUNNING' || step.status === 'COMPLETED') && (
                    <div className="step-progress">
                      <Progress 
                        percent={step.progress} 
                        size="small" 
                        showInfo
                      />
                    </div>
                  )}
                  
                  {/* 时间信息 */}
                  <div className="step-time-info">
                    {step.started_at && (
                      <div className="step-time-item">
                        <Text type="tertiary">开始: {formatTime(step.started_at)}</Text>
                      </div>
                    )}
                    {step.completed_at && (
                      <div className="step-time-item">
                        <Text type="tertiary">完成: {formatTime(step.completed_at)}</Text>
                      </div>
                    )}
                    {step.started_at && (
                      <div className="step-time-item">
                        <Text type="tertiary">
                          耗时: {getDuration(step.started_at, step.completed_at)}
                        </Text>
                      </div>
                    )}
                  </div>
                  
                  {/* 错误信息 */}
                  {step.error_message && (
                    <div className="step-error">
                      <Text type="danger">{step.error_message}</Text>
                    </div>
                  )}
                  
                  {/* 步骤详情折叠控制 */}
                  {(step.metadata || step.output) && (
                    <div 
                      className="step-detail-toggle" 
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
                    <div className="step-detail-content">
                      {step.metadata && (
                        <div className="step-metadata">
                          <Text strong size="small">步骤元数据</Text>
                          <Card className="step-detail-card">
                            <pre>
                              {JSON.stringify(step.metadata, null, 2)}
                            </pre>
                          </Card>
                        </div>
                      )}
                      
                      {step.output && (
                        <div className="step-output">
                          <Text strong size="small">步骤输出</Text>
                          <Card className="step-detail-card">
                            <pre>
                              {JSON.stringify(step.output, null, 2)}
                            </pre>
                          </Card>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              }
            />
          ))}
        </Steps>
      )}
    </div>
  );
} 