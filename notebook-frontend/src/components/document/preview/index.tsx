import React from 'react';
import { DocumentType } from '../types/documents';
import PdfPreview from './PdfPreview';
import MarkdownPreview from './MarkdownPreview';
import TextPreview from './TextPreview';
import WordPreview from './WordPreview';
import { Typography } from '@douyinfe/semi-ui';
import { IconFile } from '@douyinfe/semi-icons';

interface DocumentPreviewProps {
  documentType: DocumentType;
  filename: string;
  documentId: number;
}

/**
 * 文档预览主入口组件
 * 根据文档类型选择适当的预览组件渲染内容
 * 各预览组件自行负责获取所需数据
 */
const DocumentPreview: React.FC<DocumentPreviewProps> = ({
  documentType,
  filename,
  documentId
}) => {
  switch (documentType) {
    case DocumentType.PDF:
      return <PdfPreview documentId={documentId} />;
      
    case DocumentType.WORD:
    case DocumentType.WORD_X:
      // WordPreview需要documentId来获取二进制数据
      return <WordPreview documentId={documentId} />;
      
    case DocumentType.MARKDOWN:
      // MarkdownPreview自行使用preview接口获取数据
      return <MarkdownPreview documentId={documentId} />;
      
    case DocumentType.TEXT:
      // TextPreview自行使用preview接口获取数据
      return <TextPreview documentId={documentId} filename={filename} />;
      
    default:
      return (
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <IconFile size="extra-large" style={{ color: '#ccc', marginBottom: '16px' }} />
          <Typography.Text>此文件类型({documentType})不支持预览，请下载后查看。</Typography.Text>
        </div>
      );
  }
};

export default DocumentPreview; 