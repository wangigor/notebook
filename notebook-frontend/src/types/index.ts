export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

export interface ChatSession {
  id: string;
  session_id?: string;
  name: string;
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
  id: string;
  name: string;
  content: string;
  createdAt: string;
  metadata?: Record<string, unknown>;
} 