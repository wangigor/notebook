import React from 'react';
import { useParams } from 'react-router-dom';
import { TaskMonitor } from '../components/TaskMonitor';
import { Card } from '@douyinfe/semi-ui';

/**
 * 任务详情页面
 * 显示单个任务的详细信息，包括处理进度和步骤
 */
const TaskDetailsPage: React.FC = () => {
  // 从URL路由参数中获取taskId
  const { taskId } = useParams<{ taskId: string }>();

  if (!taskId) {
    return <div>任务ID不能为空</div>;
  }

  return (
    <div style={{ padding: '20px', maxWidth: '1000px', margin: '0 auto' }}>
      <Card>
        <TaskMonitor 
          taskId={taskId} 
          showHeader={true} 
          autoRefresh={true}
        />
      </Card>
    </div>
  );
};

export default TaskDetailsPage; 