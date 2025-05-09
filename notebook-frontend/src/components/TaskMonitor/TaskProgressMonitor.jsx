import React, { useEffect, useState } from 'react';
import { Card, Progress, Steps, Tag, Typography, Alert } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { getTaskDetails } from '@/api/tasks';
import useWebSocket from '@/hooks/useWebSocket';

const { Step } = Steps;
const { Text, Title } = Typography;

const TaskProgressMonitor = ({ taskId }) => {
  const [taskDetails, setTaskDetails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [overallProgress, setOverallProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [lastUpdateTime, setLastUpdateTime] = useState(0); // 跟踪最后更新时间

  // 使用WebSocket监听任务更新
  const { lastMessage, isConnected, error: wsError } = useWebSocket(
    `${process.env.REACT_APP_WS_URL}/ws/tasks/${taskId}`
  );

  // 初始加载任务详情
  useEffect(() => {
    const fetchTaskDetails = async () => {
      try {
        setLoading(true);
        const response = await getTaskDetails(taskId);
        setTaskDetails(response.data.task_details || []);
        
        // 计算总体进度和当前步骤
        calculateProgress(response.data.task_details);
        setLastUpdateTime(Date.now());
        
        setLoading(false);
      } catch (err) {
        setError('加载任务详情失败');
        setLoading(false);
        console.error('获取任务详情错误:', err);
      }
    };

    if (taskId) {
      fetchTaskDetails();
    }
  }, [taskId]);

  // 监听WebSocket消息
  useEffect(() => {
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage.data);
        if (data.task_id === taskId) {
          // 更新任务详情
          setTaskDetails(data.task_details || []);
          
          // 计算总体进度和当前步骤
          calculateProgress(data.task_details);
          setLastUpdateTime(Date.now());
        }
      } catch (err) {
        console.error('解析WebSocket消息错误:', err);
      }
    }
  }, [lastMessage, taskId]);

  // 添加轮询机制作为WebSocket的备选
  useEffect(() => {
    let pollingTimer = null;
    const POLLING_INTERVAL = 5000; // 5秒
    const STALE_THRESHOLD = 10000; // 10秒
    
    // 如果WebSocket连接失败或长时间没有更新，开始轮询
    const startPolling = () => {
      if (pollingTimer) return; // 已经在轮询中
      
      pollingTimer = setInterval(async () => {
        // 检查是否应该轮询：WebSocket有问题或数据过期
        const shouldPoll = 
          !isConnected || 
          wsError || 
          (Date.now() - lastUpdateTime > STALE_THRESHOLD);
          
        if (shouldPoll) {
          console.log('WebSocket不可用或数据过期，通过轮询获取最新状态');
          try {
            const response = await getTaskDetails(taskId);
            if (response && response.data) {
              setTaskDetails(response.data.task_details || []);
              calculateProgress(response.data.task_details);
              setLastUpdateTime(Date.now());
            }
          } catch (err) {
            console.error('轮询获取任务详情错误:', err);
          }
        }
      }, POLLING_INTERVAL);
    };
    
    startPolling();
    
    return () => {
      if (pollingTimer) {
        clearInterval(pollingTimer);
      }
    };
  }, [isConnected, wsError, lastUpdateTime, taskId]);

  // 计算总体进度和当前步骤
  const calculateProgress = (details) => {
    if (!details || details.length === 0) return;
    
    // 计算总体进度
    const totalProgress = details.reduce((sum, item) => sum + (item.progress || 0), 0) / details.length;
    setOverallProgress(Math.round(totalProgress));
    
    // 确定当前步骤
    const runningStepIndex = details.findIndex(item => item.status === 'RUNNING');
    if (runningStepIndex >= 0) {
      setCurrentStep(runningStepIndex);
    } else {
      // 如果没有正在运行的步骤，则查找最后一个已完成的步骤
      const lastCompletedIndex = details
        .map((item, index) => ({ status: item.status, index }))
        .filter(item => item.status === 'COMPLETED')
        .map(item => item.index)
        .pop();
        
      if (lastCompletedIndex !== undefined) {
        setCurrentStep(lastCompletedIndex + 1);
      }
    }
  };

  // 获取步骤状态图标
  const getStepIcon = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'FAILED':
        return <CloseCircleOutlined style={{ color: '#f5222d' }} />;
      case 'RUNNING':
        return <LoadingOutlined />;
      default:
        return null;
    }
  };

  // 获取步骤状态标签
  const getStatusTag = (status) => {
    switch (status) {
      case 'PENDING':
        return <Tag color="default">等待中</Tag>;
      case 'RUNNING':
        return <Tag color="processing">处理中</Tag>;
      case 'COMPLETED':
        return <Tag color="success">已完成</Tag>;
      case 'FAILED':
        return <Tag color="error">失败</Tag>;
      default:
        return <Tag>{status}</Tag>;
    }
  };

  if (loading) return <div>加载任务进度...</div>;
  if (error) return <Alert type="error" message={error} />;

  return (
    <Card title="文档处理进度" bordered={false}>
      <div style={{ marginBottom: 20 }}>
        <Title level={5}>总体进度</Title>
        <Progress percent={overallProgress} status={overallProgress === 100 ? 'success' : 'active'} />
      </div>
      
      <Steps current={currentStep} direction="vertical">
        {taskDetails.map((step, index) => (
          <Step
            key={index}
            title={step.step_name}
            description={
              <div>
                {getStatusTag(step.status)}
                {step.status === 'RUNNING' && (
                  <Progress percent={step.progress} size="small" style={{ marginTop: 8 }} />
                )}
                {step.error_message && (
                  <Text type="danger" style={{ display: 'block', marginTop: 8 }}>
                    错误: {step.error_message}
                  </Text>
                )}
              </div>
            }
            icon={getStepIcon(step.status)}
          />
        ))}
      </Steps>
    </Card>
  );
};

export default TaskProgressMonitor; 