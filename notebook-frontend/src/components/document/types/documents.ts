/**
 * 文档类型枚举
 * 定义系统支持的所有文档类型
 */
export enum DocumentType {
  PDF = 'pdf',
  WORD = 'doc',
  WORD_X = 'docx',
  MARKDOWN = 'md',
  TEXT = 'txt',
  UNKNOWN = 'unknown'
}

/**
 * 文档处理状态枚举
 * 用于表示文档处理的当前状态
 */
export enum DocumentProcessingStatus {
  PENDING = 'PENDING',     // 等待处理
  PROCESSING = 'PROCESSING', // 处理中
  COMPLETED = 'COMPLETED',   // 处理完成
  FAILED = 'FAILED'        // 处理失败
}

/**
 * 缩略图大小配置接口
 */
export interface ThumbnailSize {
  width: number;
  height: number;
}

/**
 * 默认缩略图尺寸常量
 */
export const DEFAULT_THUMBNAIL_SIZE: ThumbnailSize = {
  width: 120,
  height: 160
};

/**
 * 根据文件扩展名获取文档类型
 * @param filename 文件名
 * @returns DocumentType 文档类型
 */
export function getDocumentType(filename: string): DocumentType {
  if (!filename) return DocumentType.UNKNOWN;
  
  const extension = filename.split('.').pop()?.toLowerCase() || '';
  
  switch (extension) {
    case 'pdf':
      return DocumentType.PDF;
    case 'doc':
      return DocumentType.WORD;
    case 'docx':
      return DocumentType.WORD_X;
    case 'md':
      return DocumentType.MARKDOWN;
    case 'txt':
      return DocumentType.TEXT;
    default:
      return DocumentType.UNKNOWN;
  }
}

/**
 * 文档缩略图组件Props接口
 */
export interface DocumentThumbnailProps {
  documentUrl?: string;
  documentType: DocumentType;
  documentId: number;
  filename: string;
  width?: number;
  height?: number;
}

/**
 * 文档预览组件Props接口
 */
export interface DocumentPreviewProps {
  documentType: DocumentType;
  filename: string;
  documentId: number;
} 