import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getToken } from '../api/api';
import { ensureTaskSteps } from '../utils/taskUtils';
import { Task, TaskDetail } from '../types';

// 任务更新消息类型定义
export interface TaskUpdateMessage extends Task {
  task_details?: TaskDetail[];
}

/**
 * 任务WebSocket Hook，用于实时监听任务状态更新
 * @param taskId 任务ID
 * @returns 连接状态和最新任务更新
 */
export function useTaskWebSocket(taskId: string) {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [taskUpdate, setTaskUpdate] = useState<TaskUpdateMessage | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const auth = useAuth();
  
  // 清除重连定时器
  const clearReconnectTimeout = () => {
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  };
  
  // 连接WebSocket
  const connectWebSocket = useCallback(() => {
    if (!taskId) {
      console.log('无法连接WebSocket：缺少taskId');
      return;
    }
    
    const token = getToken();
    if (!token) {
      console.log('无法连接WebSocket：未找到认证令牌');
      return;
    }
    
    try {
      // 修改WebSocket URL，移除任务ID路径参数
      const wsUrl = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/ws`;
      console.log(`尝试连接WebSocket: ${wsUrl}`);
      
      const ws = new WebSocket(wsUrl, [`Bearer.${token}`]);
      
      ws.onopen = () => {
        console.log(`WebSocket连接已建立，正在发送任务ID: ${taskId}`);
        
        // 连接建立后发送任务ID
        ws.send(JSON.stringify({
          task_id: taskId
        }));
        
        setConnected(true);
        setConnectionError(null);
        reconnectAttempts.current = 0;
        clearReconnectTimeout();
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log(`收到WebSocket消息:`, data);
          if (data.event === 'task_update') {
            // 确保任务包含steps数据
            setTaskUpdate(ensureTaskSteps(data.data));
          }
        } catch (error) {
          console.error('解析WebSocket消息失败:', error);
        }
      };
      
      ws.onclose = (event) => {
        console.log(`WebSocket连接已关闭, 代码: ${event.code}, 原因: ${event.reason}`);
        setConnected(false);
        
        // 只有在非正常关闭时才自动重连
        if (event.code !== 1000 && event.code !== 1001) {
          scheduleReconnect();
        }
      };
      
      ws.onerror = (error) => {
        console.error(`WebSocket错误:`, error);
        setConnected(false);
        setConnectionError('连接服务器失败，请检查网络');
      };
      
      setSocket(ws);
    } catch (error) {
      console.error('创建WebSocket连接失败:', error);
      setConnectionError(`创建连接失败: ${error instanceof Error ? error.message : String(error)}`);
      scheduleReconnect();
    }
  }, [taskId]);
  
  // 指数退避重连
  const scheduleReconnect = () => {
    clearReconnectTimeout();
    
    const maxAttempts = 5;
    if (reconnectAttempts.current < maxAttempts) {
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
      console.log(`安排WebSocket重连，尝试 ${reconnectAttempts.current + 1}/${maxAttempts}，延迟: ${delay}ms`);
      
      reconnectTimeoutRef.current = window.setTimeout(() => {
        reconnectAttempts.current += 1;
        connectWebSocket();
      }, delay);
    } else {
      console.log('已达到最大重连次数');
      setConnectionError('连接服务器失败，已达到最大重试次数');
    }
  };
  
  // 初始连接
  useEffect(() => {
    connectWebSocket();
    
    // 清理函数
    return () => {
      clearReconnectTimeout();
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close(1000, '组件卸载');
      }
    };
  }, [connectWebSocket]);
  
  // 手动重连方法
  const reconnect = useCallback(() => {
    console.log('手动重连WebSocket');
    
    if (socket) {
      socket.close(1000, '手动重连');
    }
    
    clearReconnectTimeout();
    reconnectAttempts.current = 0;
    setConnectionError(null);
    connectWebSocket();
  }, [socket, connectWebSocket]);
  
  return { connected, taskUpdate, reconnect, connectionError };
} 