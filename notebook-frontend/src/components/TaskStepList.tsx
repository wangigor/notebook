import React from 'react';
import { Steps, Typography, Progress, Spin, Card, Tag, Collapse } from '@douyinfe/semi-ui';
import { IconTickCircle, IconClose, IconAlertTriangle, IconHourglass, IconInfoCircle } from '@douyinfe/semi-icons';

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
}

/**
 * 任务步骤列表组件
 * 以垂直步骤条的形式展示任务处理步骤
 */
export function TaskStepList({ steps, currentStepIndex = -1 }: TaskStepListProps) {
  // 状态到图标的映射
  const statusIcons = {
    PENDING: <IconHourglass style={{ color: '#AAA' }} />,
    RUNNING: <Spin size="small" />,
    COMPLETED: <IconTickCircle style={{ color: '#52c41a' }} />,
    FAILED: <IconClose style={{ color: '#ff4d4f' }} />,
    SKIPPED: <IconAlertTriangle style={{ color: '#faad14' }} />
  };
  
  // 格式化时间函数
  const formatTime = (timeStr?: string) => {
    if (!timeStr) return '';
    return new Date(timeStr).toLocaleString();
  };
  
  // 计算持续时间
  const getDuration = (start?: string, end?: string) => {
    if (!start) return '';
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const durationMs = endTime - startTime;
    
    if (durationMs < 1000) return `${durationMs}ms`;
    if (durationMs < 60000) return `${Math.floor(durationMs / 1000)}秒`;
    return `${Math.floor(durationMs / 60000)}分${Math.floor((durationMs % 60000) / 1000)}秒`;
  };
  
  return (
    <div className="task-step-list">
      <Steps direction="vertical" current={currentStepIndex}>
        {steps.map((step, index) => (
          <Step 
            key={index}
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Text>{step.name}</Text>
                {statusIcons[step.status]}
                {step.step_type && (
                  <Tag size="small" color="blue">{step.step_type}</Tag>
                )}
              </div>
            }
            description={
              <div>
                {step.description && <Text type="secondary">{step.description}</Text>}
                
                {/* 进度条 */}
                {(step.status === 'RUNNING' || step.status === 'COMPLETED') && (
                  <Progress 
                    percent={step.progress} 
                    size="small" 
                    style={{ margin: '8px 0' }}
                    showInfo
                  />
                )}
                
                {/* 时间信息 */}
                <div style={{ fontSize: '12px', marginTop: '4px' }}>
                  {step.started_at && (
                    <div>
                      <Text type="tertiary">开始: {formatTime(step.started_at)}</Text>
                    </div>
                  )}
                  {step.completed_at && (
                    <div>
                      <Text type="tertiary">完成: {formatTime(step.completed_at)}</Text>
                    </div>
                  )}
                  {step.started_at && (
                    <div>
                      <Text type="tertiary">
                        耗时: {getDuration(step.started_at, step.completed_at)}
                      </Text>
                    </div>
                  )}
                </div>
                
                {/* 错误信息 */}
                {step.error_message && (
                  <div style={{ marginTop: '8px', padding: '8px', borderRadius: '4px', background: 'var(--semi-color-danger-light-default)' }}>
                    <Text type="danger">{step.error_message}</Text>
                  </div>
                )}
                
                {/* 步骤元数据与输出 */}
                {(step.metadata || step.output) && (
                  <div style={{ marginTop: '8px' }}>
                    <Collapse>
                      {step.metadata && (
                        <Collapse.Panel 
                          header={
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <IconInfoCircle size="small" />
                              <span>步骤元数据</span>
                            </div>
                          } 
                          itemKey="metadata"
                        >
                          <Card style={{ padding: '8px' }}>
                            <pre style={{ margin: 0, fontSize: '12px' }}>
                              {JSON.stringify(step.metadata, null, 2)}
                            </pre>
                          </Card>
                        </Collapse.Panel>
                      )}
                      
                      {step.output && (
                        <Collapse.Panel 
                          header={
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <IconInfoCircle size="small" />
                              <span>步骤输出</span>
                            </div>
                          } 
                          itemKey="output"
                        >
                          <Card style={{ padding: '8px' }}>
                            <pre style={{ margin: 0, fontSize: '12px' }}>
                              {JSON.stringify(step.output, null, 2)}
                            </pre>
                          </Card>
                        </Collapse.Panel>
                      )}
                    </Collapse>
                  </div>
                )}
              </div>
            }
          />
        ))}
      </Steps>
    </div>
  );
} 