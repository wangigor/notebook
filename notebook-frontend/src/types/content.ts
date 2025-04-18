export type BlockType = 'thinking' | 'analyzing' | 'document' | 'answer' | 'response' | 'raw';

export interface ContentBlock {
  id: string;
  type: BlockType;
  content: string;
  title?: string;
  renderOptions?: {
    typing?: boolean;
    speed?: number;
    collapsed?: boolean;
  };
}

// 为文档引用添加专门的类型
export interface DocumentReference {
  name: string;
  content: string;
  url?: string;
}

// 生成块ID的辅助函数
export function generateBlockId(): string {
  return `block-${Math.random().toString(36).substring(2, 9)}`;
}

// 增强消息内容类型
export interface EnhancedMessageContent {
  raw: string;
  thinking?: string[];
  analyzing?: string[];
  answer?: string;
} 