import { Task, TaskDetail, TaskStep, TaskStepStatus } from '../types';

/**
 * 将任务详情数据映射为任务步骤
 */
export function mapTaskDetailsToSteps(taskDetails: TaskDetail[]): TaskStep[] {
  return taskDetails.map(detail => {
    // 从步骤名称推断步骤类型
    let stepType = '';
    const stepNameLower = detail.step_name.toLowerCase();
    
    if (stepNameLower.includes('验证') || stepNameLower.includes('verification')) {
      stepType = 'document_verification';
    } else if (stepNameLower.includes('上传') || stepNameLower.includes('upload')) {
      stepType = 'file_upload';
    } else if (stepNameLower.includes('提取') || stepNameLower.includes('extraction')) {
      stepType = 'text_extraction';
    } else if (stepNameLower.includes('预处理') || stepNameLower.includes('preprocessing')) {
      stepType = 'text_preprocessing';
    } else if (stepNameLower.includes('向量化') || stepNameLower.includes('vectorization')) {
      stepType = 'vectorization';
    } else if (stepNameLower.includes('保存') || stepNameLower.includes('存储') || stepNameLower.includes('storage')) {
      stepType = 'vector_storage';
    }
    
    // 检查details中是否已包含step_type
    if (detail.details && detail.details.step_type) {
      stepType = detail.details.step_type;
    }
    
    return {
      name: detail.step_name,
      description: '',
      status: detail.status as TaskStepStatus,
      progress: detail.progress,
      started_at: detail.started_at,
      completed_at: detail.completed_at,
      error_message: detail.error_message,
      metadata: detail.details || {},
      step_type: stepType // 添加步骤类型
    };
  });
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