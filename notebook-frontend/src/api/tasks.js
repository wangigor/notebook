// api/tasks.js
import axios from 'axios';

/**
 * 获取任务详情，包括任务步骤信息
 * @param {string} taskId 任务ID
 * @returns {Promise<Object>} 任务详情数据
 */
export const fetchTaskDetails = async (taskId) => {
  const response = await axios.get(`/api/tasks/${taskId}`);
  return response.data;
};

/**
 * 获取任务列表
 * @param {Object} params 查询参数
 * @returns {Promise<Array>} 任务列表
 */
export const fetchTasks = async (params = {}) => {
  const response = await axios.get('/api/tasks', { params });
  return response.data;
};

/**
 * 创建新任务
 * @param {Object} taskData 任务数据
 * @returns {Promise<Object>} 创建的任务
 */
export const createTask = async (taskData) => {
  const response = await axios.post('/api/tasks', taskData);
  return response.data;
};

/**
 * 取消任务
 * @param {string} taskId 任务ID
 * @returns {Promise<Object>} 取消结果
 */
export const cancelTask = async (taskId) => {
  const response = await axios.post(`/api/tasks/${taskId}/cancel`);
  return response.data;
}; 