import React from 'react';
import SyntaxHighlighter from 'react-syntax-highlighter';
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import { DEFAULT_THUMBNAIL_SIZE } from '../types/documents';

interface TextThumbnailProps {
  content: string;
  width?: number;
  height?: number;
}

/**
 * 文本文档缩略图组件
 * 使用语法高亮显示文本内容的前几行
 */
const TextThumbnail: React.FC<TextThumbnailProps> = ({
  content,
  width = DEFAULT_THUMBNAIL_SIZE.width,
  height = DEFAULT_THUMBNAIL_SIZE.height
}) => {
  // 提取文本的前10行作为预览
  const lines = content.split('\n');
  const previewLines = lines.slice(0, 10).join('\n');
  
  return (
    <div
      className="text-thumbnail"
      style={{
        width,
        height,
        overflow: 'hidden',
        borderRadius: '4px',
        border: '1px solid #e0e0e0',
        fontSize: '10px',
      }}
    >
      <SyntaxHighlighter
        language="text"
        style={docco}
        customStyle={{
          margin: 0,
          padding: '8px',
          height: '100%',
          overflow: 'hidden',
          fontSize: '10px',
        }}
      >
        {previewLines}
      </SyntaxHighlighter>
    </div>
  );
};

export default TextThumbnail; 