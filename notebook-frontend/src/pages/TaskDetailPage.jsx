// pages/TaskDetailPage.jsx
// @deprecated - 此组件已弃用，请使用TaskDetailsPage组件
// 原因：此组件依赖antd库，而项目标准使用Semi Design
import React, { useState, useEffect } from 'react';
import { Card, Progress } from 'antd';
import TaskStepsList from '../components/TaskStepsList';
import { useParams } from 'react-router-dom';
import { fetchTaskDetails } from '../api/tasks';

const TaskDetailPage = () => {
  const { taskId } = useParams();
  const [task, setTask] = useState(null);
  const [taskDetails, setTaskDetails] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 获取任务详情
    const loadTaskDetails = async () => {
      try {
        setLoading(true);
        const data = await fetchTaskDetails(taskId);
        setTask(data);
        setTaskDetails(data.task_details || []);
      } catch (error) {
        console.error('Failed to load task details:', error);
      } finally {
        setLoading(false);
      }
    };

    loadTaskDetails();

    // 建立WebSocket连接
    const ws = new WebSocket(`ws://${window.location.host}/ws/tasks/${taskId}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.event === 'task_update') {
        // 更新任务状态
        setTask(data.data);
        
        // 更新任务详情
        if (data.data.task_details) {
          setTaskDetails(data.data.task_details);
        }
      }
    };
    
    return () => {
      ws.close();
    };
  }, [taskId]);

  if (loading || !task) {
    return <div>加载中...</div>;
  }

  return (
    <div className="task-detail-page">
      <Card title={`处理文档: ${task.document?.name || '未知文档'}`}>
        <div className="task-status">
          <div className="status-indicator">
            {task.status === 'COMPLETED' && <span className="status-completed">已完成</span>}
            {task.status === 'RUNNING' && <span className="status-running">处理中</span>}
            {task.status === 'FAILED' && <span className="status-failed">失败</span>}
            {task.status === 'PENDING' && <span className="status-pending">等待中</span>}
          </div>
          
          <Progress 
            percent={task.progress} 
            status={
              task.status === 'FAILED' ? 'exception' : 
              task.status === 'COMPLETED' ? 'success' : 'active'
            }
          />
          
          {/* 集成TaskStepsList组件 */}
          <TaskStepsList taskDetails={taskDetails} />
          
          {task.error_message && (
            <div className="error-message">
              <h4>错误信息</h4>
              <pre>{task.error_message}</pre>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};

export default TaskDetailPage; 