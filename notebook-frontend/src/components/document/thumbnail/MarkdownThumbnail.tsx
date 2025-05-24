import React from 'react';
import { Typography } from '@douyinfe/semi-ui';
import { ThumbnailSize, DEFAULT_THUMBNAIL_SIZE } from '../types/documents';

interface MarkdownThumbnailProps {
  content: string;
  width?: number;
  height?: number;
}

/**
 * Markdown文档缩略图组件
 * 将Markdown内容的前一部分显示为缩略图预览
 */
const MarkdownThumbnail: React.FC<MarkdownThumbnailProps> = ({
  content,
  width = DEFAULT_THUMBNAIL_SIZE.width,
  height = DEFAULT_THUMBNAIL_SIZE.height
}) => {
  // 提取Markdown的前300个字符作为预览
  const previewContent = content.substring(0, 300);
  
  return (
    <div
      className="markdown-thumbnail"
      style={{
        width,
        height,
        padding: '8px',
        overflow: 'hidden',
        borderRadius: '4px',
        backgroundColor: '#f9f9f9',
        border: '1px solid #e0e0e0',
        fontSize: '12px',
      }}
    >
      <Typography.Text size="small" ellipsis={{ rows: 10 }}>
        {previewContent}
      </Typography.Text>
    </div>
  );
};

export default MarkdownThumbnail; 