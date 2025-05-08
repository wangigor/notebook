import React from 'react';
import { Tooltip } from '@douyinfe/semi-ui';
import { IconTickCircle, IconAlertTriangle, IconHourglass, IconPlay, IconClose } from '@douyinfe/semi-icons';

// 任务状态类型
export type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

interface TaskStatusBadgeProps {
  status: TaskStatus;
  showText?: boolean;
  tooltipPosition?: 'top' | 'left' | 'right' | 'bottom';
}

/**
 * 任务状态徽章组件
 * 根据任务状态显示不同颜色和图标的徽章
 */
export function TaskStatusBadge({ status, showText = true, tooltipPosition = 'top' }: TaskStatusBadgeProps) {
  // 状态映射配置
  const statusConfig = {
    PENDING: {
      icon: <IconHourglass size="small" />,
      color: '#ccc',
      bgColor: '#f5f5f5',
      text: '等待中'
    },
    RUNNING: {
      icon: <IconPlay size="small" />,
      color: '#0077ff',
      bgColor: '#e6f7ff',
      text: '运行中'
    },
    COMPLETED: {
      icon: <IconTickCircle size="small" />,
      color: '#52c41a',
      bgColor: '#f6ffed',
      text: '已完成'
    },
    FAILED: {
      icon: <IconClose size="small" />,
      color: '#ff4d4f',
      bgColor: '#fff2f0',
      text: '失败'
    },
    CANCELLED: {
      icon: <IconAlertTriangle size="small" />,
      color: '#faad14',
      bgColor: '#fffbe6',
      text: '已取消'
    }
  };
  
  const config = statusConfig[status] || statusConfig.PENDING;
  
  return (
    <Tooltip content={config.text} position={tooltipPosition}>
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '2px 8px',
          borderRadius: '12px',
          backgroundColor: config.bgColor,
          color: config.color,
          fontSize: '12px',
          fontWeight: 'normal',
          lineHeight: '20px',
        }}
      >
        {config.icon}
        {showText && <span>{config.text}</span>}
      </div>
    </Tooltip>
  );
} 