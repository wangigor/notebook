import React from 'react';
import { Card, Typography, Descriptions } from '@douyinfe/semi-ui';
import { IconClock, IconCalendar } from '@douyinfe/semi-icons';

const { Text } = Typography;

interface TimeInfoCardProps {
  createdAt?: string;
  startedAt?: string;
  completedAt?: string;
  showTitle?: boolean;
  compact?: boolean;
}

/**
 * 时间信息卡片组件
 * 显示任务的创建、开始和完成时间
 */
export function TimeInfoCard({ 
  createdAt, 
  startedAt, 
  completedAt, 
  showTitle = true,
  compact = false
}: TimeInfoCardProps) {
  // 格式化时间函数
  const formatTime = (timeStr?: string) => {
    if (!timeStr) return '-';
    
    const date = new Date(timeStr);
    if (compact) {
      return new Intl.DateTimeFormat('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }).format(date);
    }
    return date.toLocaleString();
  };
  
  // 计算持续时间
  const calculateDuration = (start?: string, end?: string) => {
    if (!start) return '-';
    
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const durationMs = endTime - startTime;
    
    if (durationMs < 1000) return `${durationMs}毫秒`;
    if (durationMs < 60000) return `${Math.floor(durationMs / 1000)}秒`;
    if (durationMs < 3600000) return `${Math.floor(durationMs / 60000)}分${Math.floor((durationMs % 60000) / 1000)}秒`;
    return `${Math.floor(durationMs / 3600000)}小时${Math.floor((durationMs % 3600000) / 60000)}分`;
  };
  
  return (
    <Card
      style={{ marginBottom: '16px' }}
      headerStyle={{ padding: compact ? '6px 12px' : '8px 16px' }}
      bodyStyle={{ padding: compact ? '6px 12px' : '8px 16px' }}
      header={
        showTitle && 
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <IconClock size={compact ? "small" : "default"} />
          <Text size={compact ? "small" : "normal"}>时间信息</Text>
        </div>
      }
    >
      <Descriptions size="small" row>
        <Descriptions.Item itemKey="创建时间">
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <IconCalendar size="small" />
            <Text size={compact ? "small" : "normal"}>{formatTime(createdAt)}</Text>
          </div>
        </Descriptions.Item>
        
        {startedAt && (
          <Descriptions.Item itemKey="开始时间">
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <IconCalendar size="small" />
              <Text size={compact ? "small" : "normal"}>{formatTime(startedAt)}</Text>
            </div>
          </Descriptions.Item>
        )}
        
        {completedAt && (
          <Descriptions.Item itemKey="完成时间">
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <IconCalendar size="small" />
              <Text size={compact ? "small" : "normal"}>{formatTime(completedAt)}</Text>
            </div>
          </Descriptions.Item>
        )}
        
        {startedAt && (
          <Descriptions.Item itemKey="运行时长">
            <Text size={compact ? "small" : "normal"}>{calculateDuration(startedAt, completedAt)}</Text>
          </Descriptions.Item>
        )}
      </Descriptions>
    </Card>
  );
} 