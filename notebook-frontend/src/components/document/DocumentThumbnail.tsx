import React from 'react';
import { DocumentType, DEFAULT_THUMBNAIL_SIZE } from './types/documents';
import DefaultThumbnail from './thumbnail/DefaultThumbnail';
import PdfThumbnail from './thumbnail/PdfThumbnail';
import WordThumbnail from './thumbnail/WordThumbnail';
import MarkdownThumbnail from './thumbnail/MarkdownThumbnail';
import TextThumbnail from './thumbnail/TextThumbnail';

interface DocumentThumbnailProps {
  documentUrl?: string;
  documentType: DocumentType;
  documentId: number;
  filename: string;
  content?: string;
  width?: number;
  height?: number;
}

/**
 * 文档缩略图工厂组件
 * 根据文档类型选择并渲染合适的缩略图组件
 */
const DocumentThumbnail: React.FC<DocumentThumbnailProps> = ({
  documentUrl,
  documentType,
  documentId,
  filename,
  content,
  width = DEFAULT_THUMBNAIL_SIZE.width,
  height = DEFAULT_THUMBNAIL_SIZE.height
}) => {
  // 根据文档类型渲染对应的缩略图组件
  const renderThumbnail = () => {
    switch(documentType) {
      case DocumentType.PDF:
        // 返回PDF缩略图组件
        return (
          <PdfThumbnail 
            url={documentUrl || `/api/documents/${documentId}/download`} 
            documentId={documentId}
            width={width} 
            height={height} 
          />
        );
        
      case DocumentType.WORD:
      case DocumentType.WORD_X:
        // 返回Word缩略图组件
        return (
          <WordThumbnail 
            url={documentUrl || `/api/documents/${documentId}/download`} 
            documentId={documentId}
            filename={filename}
            width={width} 
            height={height} 
          />
        );
        
      case DocumentType.MARKDOWN:
        // 返回Markdown缩略图组件
        if (content) {
          return (
            <MarkdownThumbnail 
              content={content} 
              width={width} 
              height={height} 
            />
          );
        }
        // 没有内容时，使用默认缩略图
        return (
          <DefaultThumbnail 
            documentType={DocumentType.MARKDOWN}
            filename={filename}
            width={width} 
            height={height} 
          />
        );
        
      case DocumentType.TEXT:
        // 返回文本缩略图组件
        if (content) {
          return (
            <TextThumbnail 
              content={content} 
              width={width} 
              height={height} 
            />
          );
        }
        // 没有内容时，使用默认缩略图
        return (
          <DefaultThumbnail 
            documentType={DocumentType.TEXT}
            filename={filename}
            width={width} 
            height={height} 
          />
        );
        
      default:
        return (
          <DefaultThumbnail 
            documentType={documentType}
            filename={filename}
            width={width} 
            height={height} 
          />
        );
    }
  };

  return (
    <div className="document-thumbnail-container">
      {renderThumbnail()}
    </div>
  );
};

export default DocumentThumbnail; 