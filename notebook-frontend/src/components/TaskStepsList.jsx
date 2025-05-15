// components/TaskStepsList.jsx
// @deprecated - 此组件已弃用，请使用TaskStepList组件
// 原因：此组件依赖@ant-design/icons库，而项目标准使用Semi Design
import React, { useState } from 'react';
import { 
  CheckCircleOutlined, 
  SyncOutlined, 
  CloseCircleOutlined, 
  ClockCircleOutlined,
  DownOutlined,
  UpOutlined
} from '@ant-design/icons';
import './TaskStepsList.css';

const TaskStepsList = ({ taskDetails = [] }) => {
  const [stepsExpanded, setStepsExpanded] = useState(true);
  const [expandedStepId, setExpandedStepId] = useState(null);

  const toggleStepDetail = (stepId) => {
    if (expandedStepId === stepId) {
      setExpandedStepId(null);
    } else {
      setExpandedStepId(stepId);
    }
  };

  // 获取步骤状态图标
  const getStepStatusIcon = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircleOutlined />;
      case 'RUNNING':
        return <SyncOutlined spin />;
      case 'FAILED':
        return <CloseCircleOutlined />;
      default:
        return <ClockCircleOutlined />;
    }
  };

  // 格式化日期时间
  const formatDateTime = (dateTimeStr) => {
    if (!dateTimeStr) return '未开始';
    return new Date(dateTimeStr).toLocaleString();
  };

  // 计算步骤耗时
  const getStepDuration = (step) => {
    if (!step.started_at) return '未开始';
    if (!step.completed_at) return '进行中';
    
    const start = new Date(step.started_at);
    const end = new Date(step.completed_at);
    const durationMs = end - start;
    
    if (durationMs < 1000) {
      return `${durationMs}毫秒`;
    } else if (durationMs < 60000) {
      return `${(durationMs / 1000).toFixed(2)}秒`;
    } else {
      const minutes = Math.floor(durationMs / 60000);
      const seconds = ((durationMs % 60000) / 1000).toFixed(0);
      return `${minutes}分${seconds}秒`;
    }
  };

  // 如果没有任务详情，不显示组件
  if (!taskDetails || taskDetails.length === 0) {
    return null;
  }

  // 按步骤顺序排序
  const sortedDetails = [...taskDetails].sort((a, b) => a.step_order - b.step_order);

  return (
    <div className="task-steps-container">
      <div className="task-steps-header" onClick={() => setStepsExpanded(!stepsExpanded)}>
        <span>处理步骤</span>
        <span>{stepsExpanded ? <UpOutlined /> : <DownOutlined />}</span>
      </div>
      
      {stepsExpanded && (
        <div className="task-steps-list">
          {sortedDetails.map((step) => (
            <div 
              key={step.id} 
              className={`task-step-item status-${step.status.toLowerCase()}`}
            >
              <div 
                className="step-item-header"
                onClick={() => toggleStepDetail(step.id)}
              >
                <div className="step-status-icon">
                  {getStepStatusIcon(step.status)}
                </div>
                <div className="step-name">{step.step_name}</div>
                <div className="step-progress">
                  <div className="progress-bar">
                    <div 
                      className="progress-fill" 
                      style={{width: `${step.progress}%`}}
                    />
                  </div>
                  <span>{step.progress}%</span>
                </div>
                <div className="step-time">
                  {getStepDuration(step)}
                </div>
                <div className="step-expand-icon">
                  {expandedStepId === step.id ? <UpOutlined /> : <DownOutlined />}
                </div>
              </div>
              
              {expandedStepId === step.id && (
                <div className="step-item-detail">
                  <div className="step-metadata">
                    <h4>步骤信息</h4>
                    <div className="metadata-grid">
                      <div className="metadata-item">
                        <span className="label">开始时间:</span>
                        <span>{formatDateTime(step.started_at)}</span>
                      </div>
                      <div className="metadata-item">
                        <span className="label">完成时间:</span>
                        <span>{formatDateTime(step.completed_at)}</span>
                      </div>
                      {step.details && Object.entries(step.details).map(([key, value]) => (
                        <div className="metadata-item" key={key}>
                          <span className="label">{key}:</span>
                          <span>
                            {typeof value === 'object' 
                              ? JSON.stringify(value, null, 2) 
                              : value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  {step.error_message && (
                    <div className="step-error">
                      <h4>错误信息</h4>
                      <pre>{step.error_message}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TaskStepsList; 