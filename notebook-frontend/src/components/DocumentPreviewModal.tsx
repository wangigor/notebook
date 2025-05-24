import React from 'react';
import { Modal, Typography } from '@douyinfe/semi-ui';
import { Document, DocumentPreview as DocumentPreviewType } from '../types';
import DocumentPreview from './document/preview';
import { getDocumentType } from './document/types/documents';

interface DocumentPreviewModalProps {
  visible: boolean;
  document: Document | DocumentPreviewType | null;
  onClose: () => void;
}

const { Text } = Typography;

const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({
  visible,
  document,
  onClose
}) => {
  const renderFileContent = () => {
    if (!document) {
      return <Text type="tertiary">此文档没有可显示的内容。</Text>;
    }

    // 处理filename字段映射：Document类型有filename字段，DocumentPreview类型使用name字段
    const filename = (document as Document).filename || document.name;
    const docType = getDocumentType(filename);
    
    // 直接使用传入的document参数，不再进行额外的API调用
    return (
      <DocumentPreview
        documentType={docType}
        filename={filename}
        documentId={document.id}
      />
    );
  };

  return (
    <Modal
      title="文档预览"
      visible={visible}
      onCancel={onClose}
      footer={null}
      closeOnEsc
      width={800}
      bodyStyle={{ maxHeight: '90vh', overflow: 'auto' }}
    >
      {document ? (
        <div className="document-preview-container" style={{ 
          padding: '16px', 
          borderRadius: '4px',
          backgroundColor: 'var(--semi-color-bg-0)',
          maxHeight: '80vh',
          overflow: 'auto'
        }}>
          {renderFileContent()}
        </div>
      ) : (
        <Text type="tertiary">未找到文档信息</Text>
      )}
    </Modal>
  );
};

export default DocumentPreviewModal; 