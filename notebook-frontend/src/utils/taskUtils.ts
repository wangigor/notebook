import { Task, TaskDetail, TaskStep, TaskStepStatus } from '../types';

/**
 * 将任务详情数据映射为任务步骤
 */
export function mapTaskDetailsToSteps(taskDetails: TaskDetail[]): TaskStep[] {
  return taskDetails.map(detail => ({
    name: detail.step_name,
    description: '',
    status: detail.status as TaskStepStatus,
    progress: detail.progress,
    started_at: detail.started_at,
    completed_at: detail.completed_at,
    error_message: detail.error_message,
    metadata: detail.details || {}
  }));
}

/**
 * 确保任务对象拥有步骤数据
 * 如果有task_details但没有steps，将task_details映射为steps
 */
export function ensureTaskSteps(task: Task): Task {
  if (task.task_details && Array.isArray(task.task_details) && (!task.steps || task.steps.length === 0)) {
    return {
      ...task,
      steps: mapTaskDetailsToSteps(task.task_details)
    };
  }
  return task;
} 