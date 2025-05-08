import React, { useState, useEffect } from 'react';
import { Modal, Spin, Typography, Tabs, Button } from '@douyinfe/semi-ui';
import { IconDownload } from '@douyinfe/semi-icons';
import { Document, DocumentPreview } from '../types';
import { documents } from '../api/api';
import MarkdownRender from './MarkdownRender';

interface DocumentPreviewModalProps {
  visible: boolean;
  document: Document | DocumentPreview | null;
  onClose: () => void;
}

const { Text, Title } = Typography;
const { TabPane } = Tabs;

const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({
  visible,
  document,
  onClose
}) => {
  const [loading, setLoading] = useState(false);
  const [documentData, setDocumentData] = useState<Document | null>(null);
  const [activeTab, setActiveTab] = useState('content');

  useEffect(() => {
    if (visible && document) {
      fetchDocumentData();
    } else {
      setDocumentData(null);
    }
  }, [visible, document]);

  const fetchDocumentData = async () => {
    if (!document) return;
    
    setLoading(true);
    try {
      const response = await documents.getDocument(document.id);
      if (response.success && response.data) {
        setDocumentData(response.data);
      }
    } catch (error) {
      console.error('获取文档详情失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const getFileTypeColor = (filename: string = ''): string => {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    
    const typeColors: Record<string, string> = {
      pdf: 'red',
      doc: 'blue',
      docx: 'blue',
      txt: 'green',
      md: 'cyan',
      json: 'purple',
      csv: 'orange',
      xls: 'yellow',
      xlsx: 'yellow'
    };
    
    return typeColors[extension] || 'grey';
  };

  const renderFileContent = () => {
    if (!documentData?.content) {
      return <Text type="tertiary">此文档没有可显示的内容。</Text>;
    }

    const extension = documentData.filename?.split('.').pop()?.toLowerCase() || '';
    
    if (extension === 'md') {
      return <MarkdownRender content={documentData.content} />;
    } else if (['pdf', 'doc', 'docx', 'xls', 'xlsx'].includes(extension)) {
      return (
        <div className="text-center p-4">
          <Text>此文件类型不支持直接预览。请下载后查看。</Text>
          <div className="mt-4">
            <Button 
              icon={<IconDownload />}
              onClick={() => handleDownload()}
            >
              下载文件
            </Button>
          </div>
        </div>
      );
    } else {
      // 纯文本显示
      return (
        <div style={{ 
          whiteSpace: 'pre-wrap', 
          fontFamily: 'monospace', 
          maxHeight: '500px', 
          overflow: 'auto', 
          padding: '16px',
          backgroundColor: 'var(--semi-color-bg-0)',
          borderRadius: '4px'
        }}>
          {documentData.content}
        </div>
      );
    }
  };

  const handleDownload = () => {
    if (!documentData) return;
    
    // 创建下载链接
    window.open(`/api/documents/${documentData.id}/download`, '_blank');
  };

  return (
    <Modal
      title="文档预览"
      visible={visible}
      onCancel={onClose}
      footer={null}
      closeOnEsc
      width={800}
      bodyStyle={{ maxHeight: '80vh', overflow: 'auto' }}
    >
      {loading ? (
        <div className="flex justify-center items-center p-10">
          <Spin size="large" />
        </div>
      ) : documentData ? (
        <div>
          <div className="mb-4">
            <Title heading={5}>{documentData.name}</Title>
            <div className="flex items-center gap-2 mt-2">
              <Text type="secondary">文件名: {documentData.filename || documentData.name}</Text>
              <Text type="secondary">•</Text>
              <Text type="secondary">
                上传时间: {new Date(documentData.created_at).toLocaleString()}
              </Text>
            </div>
          </div>

          <Tabs activeKey={activeTab} onChange={setActiveTab}>
            <TabPane tab="文档内容" itemKey="content">
              {renderFileContent()}
            </TabPane>
            
            <TabPane tab="提取文本" itemKey="extracted">
              <div style={{ 
                whiteSpace: 'pre-wrap', 
                fontFamily: 'monospace', 
                maxHeight: '500px', 
                overflow: 'auto', 
                padding: '16px',
                backgroundColor: 'var(--semi-color-bg-0)',
                borderRadius: '4px'
              }}>
                {documentData.extracted_text || <Text type="tertiary">无提取文本</Text>}
              </div>
            </TabPane>
            
            <TabPane tab="元数据" itemKey="metadata">
              <div style={{ 
                whiteSpace: 'pre-wrap', 
                fontFamily: 'monospace', 
                maxHeight: '500px', 
                overflow: 'auto', 
                padding: '16px',
                backgroundColor: 'var(--semi-color-bg-0)',
                borderRadius: '4px'
              }}>
                {documentData.metadata 
                  ? JSON.stringify(documentData.metadata, null, 2) 
                  : <Text type="tertiary">无元数据</Text>}
              </div>
            </TabPane>
          </Tabs>
          
          <div className="flex justify-end mt-4">
            <Button 
              icon={<IconDownload />}
              onClick={handleDownload}
            >
              下载文件
            </Button>
          </div>
        </div>
      ) : (
        <Text type="tertiary">未找到文档信息</Text>
      )}
    </Modal>
  );
};

export default DocumentPreviewModal; 