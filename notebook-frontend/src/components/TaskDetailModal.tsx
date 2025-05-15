import React from 'react';
import { Modal } from '@douyinfe/semi-ui';
import { TaskMonitor } from './TaskMonitor';

interface TaskDetailModalProps {
  taskId: string;
  visible: boolean;
  onCancel: () => void;
  title?: string;
}

/**
 * 任务详情对话框组件
 * 在弹窗中展示任务监控组件
 */
export function TaskDetailModal({ taskId, visible, onCancel, title = '任务详情' }: TaskDetailModalProps) {
  return (
    <Modal
      title={title}
      visible={visible}
      onCancel={onCancel}
      footer={null}
      width={800}
      style={{ maxHeight: '90vh' }}
      bodyStyle={{ overflowY: 'auto', padding: '8px 16px 16px' }}
    >
      <TaskMonitor 
        taskId={taskId} 
        showHeader={false} 
        compact={true} 
      />
    </Modal>
  );
} 