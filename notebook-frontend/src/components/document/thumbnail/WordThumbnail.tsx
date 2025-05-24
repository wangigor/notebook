import React from 'react';
import { IconFile } from '@douyinfe/semi-icons';
import { Typography } from '@douyinfe/semi-ui';
import { DocumentType, DEFAULT_THUMBNAIL_SIZE } from '../types/documents';

interface WordThumbnailProps {
  url: string;
  documentId: number;
  filename: string;
  width?: number;
  height?: number;
}

/**
 * Word文档缩略图组件
 * 由于技术限制，使用图标和文件名作为缩略图展示
 */
const WordThumbnail: React.FC<WordThumbnailProps> = ({
  filename,
  width = DEFAULT_THUMBNAIL_SIZE.width,
  height = DEFAULT_THUMBNAIL_SIZE.height
}) => {
  // 确定文档类型(doc或docx)
  const isDocx = filename.toLowerCase().endsWith('.docx');
  const documentType = isDocx ? DocumentType.WORD_X : DocumentType.WORD;
  
  // 根据文档类型返回颜色
  const getIconColor = (): string => {
    return '#3498db'; // Word蓝色
  };
  
  // 获取文档类型名称
  const getTypeName = (): string => {
    return isDocx ? 'DOCX' : 'DOC';
  };
  
  return (
    <div
      className="word-thumbnail"
      style={{
        width,
        height,
        backgroundColor: '#f5f5f5',
        border: '1px solid #e0e0e0',
        borderRadius: '4px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '16px',
        boxSizing: 'border-box',
      }}
    >
      <IconFile size="extra-large" style={{ color: getIconColor(), fontSize: '40px' }} />
      <Typography.Text
        ellipsis={{ showTooltip: true }}
        style={{
          marginTop: '8px',
          fontSize: '12px',
          color: '#666',
          textAlign: 'center',
          maxWidth: '100%'
        }}
      >
        {filename}
      </Typography.Text>
      <div
        style={{
          marginTop: '4px',
          fontSize: '10px',
          color: '#999',
          textAlign: 'center',
        }}
      >
        {getTypeName()}
      </div>
    </div>
  );
};

export default WordThumbnail; 