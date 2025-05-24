import React from 'react';
import { IconFile } from '@douyinfe/semi-icons';
import { Typography } from '@douyinfe/semi-ui';
import { DocumentType, DEFAULT_THUMBNAIL_SIZE } from '../types/documents';

interface DefaultThumbnailProps {
  documentType: DocumentType;
  filename?: string;
  width?: number;
  height?: number;
}

/**
 * 默认文档缩略图组件
 * 当无法生成特定格式的缩略图时，显示此默认图标
 */
const DefaultThumbnail: React.FC<DefaultThumbnailProps> = ({ 
  documentType, 
  filename,
  width = DEFAULT_THUMBNAIL_SIZE.width, 
  height = DEFAULT_THUMBNAIL_SIZE.height 
}) => {
  // 根据文档类型返回不同颜色的图标
  const getIconColor = (): string => {
    switch (documentType) {
      case DocumentType.PDF:
        return '#e74c3c'; // 红色
      case DocumentType.WORD:
      case DocumentType.WORD_X:
        return '#3498db'; // 蓝色
      case DocumentType.MARKDOWN:
        return '#9b59b6'; // 紫色
      case DocumentType.TEXT:
        return '#95a5a6'; // 灰色
      default:
        return '#bdc3c7'; // 浅灰色
    }
  };

  // 获取文档类型名称
  const getTypeName = (): string => {
    switch (documentType) {
      case DocumentType.PDF:
        return 'PDF';
      case DocumentType.WORD:
        return 'DOC';
      case DocumentType.WORD_X:
        return 'DOCX';
      case DocumentType.MARKDOWN:
        return 'MD';
      case DocumentType.TEXT:
        return 'TXT';
      default:
        return '未知';
    }
  };

  return (
    <div
      className="default-thumbnail"
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
      
      {filename && (
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
      )}
      
      <div
        style={{
          marginTop: filename ? '4px' : '8px',
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

export default DefaultThumbnail; 