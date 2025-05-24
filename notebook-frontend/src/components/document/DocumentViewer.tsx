import React, { useState, useEffect } from 'react';
import { Spin, Typography, Button } from '@douyinfe/semi-ui';
import { IconDownload } from '@douyinfe/semi-icons';
import { DocumentType, getDocumentType } from './types/documents';
import DocumentPreview from './preview';

interface DocumentViewerProps {
  documentId: number;
  filename?: string;
  initialContent?: string;
  documentUrl?: string;
}

const { Text } = Typography;

/**
 * 统一文档查看器组件
 * 根据文档类型选择合适的预览组件来显示文档内容
 */
const DocumentViewer: React.FC<DocumentViewerProps> = ({
  documentId,
  filename = '',
  initialContent,
  documentUrl
}) => {
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState<string | undefined>(initialContent);
  const [error, setError] = useState<string | null>(null);
  const [docUrl, setDocUrl] = useState<string | undefined>(documentUrl);
  
  const documentType = getDocumentType(filename);
  
  useEffect(() => {
    if (!docUrl && documentId) {
      fetchDocument();
    }
  }, [documentId, documentType]);
  
  const fetchDocument = async () => {
    setLoading(true);
    try {
      // 实际实现时，这里应该调用API获取文档内容
      // const response = await documents.getDocument(documentId);
      // if (response.success && response.data) {
      //   setContent(response.data.content);
      //   // 构建文档URL (如果需要)
      //   setDocUrl(`/api/documents/${documentId}/download`);
      // } else {
      //   setError('无法加载文档内容');
      // }
      
      // 模拟加载文档
      setTimeout(() => {
        setContent("这是模拟的文档内容");
        setDocUrl(`/api/documents/${documentId}/download`);
        setLoading(false);
      }, 1000);
      
    } catch (error) {
      console.error('获取文档失败:', error);
      setError('获取文档失败');
      setLoading(false);
    }
  };
  
  const handleDownload = () => {
    window.open(`/api/documents/${documentId}/download`, '_blank');
  };
  
  // 渲染文档预览组件
  const renderDocumentPreview = () => {
    if (loading) {
      return (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      );
    }
    
    if (error) {
      return <Text type="danger">{error}</Text>;
    }
    
    return (
      <DocumentPreview
        documentType={documentType}
        filename={filename}
        content={content}
        documentId={documentId}
      />
    );
  };
  
  return (
    <div className="document-viewer">
      <div className="document-viewer-content">
        {renderDocumentPreview()}
      </div>
      
      <div className="document-viewer-actions" style={{ marginTop: '16px', textAlign: 'right' }}>
        <Button 
          icon={<IconDownload />}
          onClick={handleDownload}
        >
          下载文件
        </Button>
      </div>
    </div>
  );
};

export default DocumentViewer; 