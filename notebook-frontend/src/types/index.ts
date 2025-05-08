export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

export interface ChatSession {
  id: string;
  session_id?: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages?: Message[];
}

export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string | null;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ApiResponse<T> {
  data: T;
  message: string;
  success: boolean;
}

export interface ErrorResponse {
  message: string;
  success: false;
}

export interface QueryResponse {
  answer: string;
  sources?: string[];
}

export interface Document {
  id: number;
  name: string;
  file_type: string;
  filename?: string;
  metadata?: Record<string, any>;
  vector_id?: string;
  created_at: string;
  updated_at: string;
  content?: string;
  extracted_text?: string;
  status?: string;
}

export interface DocumentPreview {
  id: number;
  name: string;
  file_type?: string;
  created_at: string;
  updated_at: string;
  status?: string;
  preview_content?: string;
  tags?: string[];
  user_id: number;
  metadata?: Record<string, any>;
}

export interface DocumentList {
  items: DocumentPreview[];
  total: number;
  page: number;
  page_size: number;
}

export interface DocumentFilter {
  search?: string;
  file_type?: string;
  skip?: number;
  limit?: number;
}

export type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
export type TaskStepStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';

export interface TaskStep {
  name: string;
  description?: string;
  status: TaskStepStatus;
  progress: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  metadata?: Record<string, any>;
  output?: Record<string, any>;
  step_type?: string;
}

export interface Task {
  id: string;
  name: string;
  task_type: string;
  status: TaskStatus;
  progress: number;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  updated_at?: string;
  steps: TaskStep[];
  created_by: number;
  document_id?: number;
}

export interface DocumentWithTask extends Document {
  latest_task?: Task;
} 