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
  document_id: string;
  name: string;
  file_type: string;
  metadata?: Record<string, any>;
  vector_id?: string;
  created_at: string;
  updated_at: string;
  content?: string;
  extracted_text?: string;
}

export interface DocumentPreview {
  id: number;
  document_id: string;
  name: string;
  file_type: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export interface DocumentList {
  documents: DocumentPreview[];
  total: number;
}

export interface DocumentFilter {
  search?: string;
  file_type?: string;
  skip?: number;
  limit?: number;
} 