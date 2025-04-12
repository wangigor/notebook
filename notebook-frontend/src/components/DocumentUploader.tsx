import React, { useState } from 'react';
import { Modal, Upload, Toast, Button, Typography, Space } from '@douyinfe/semi-ui';
import { IconUpload } from '@douyinfe/semi-icons';
import { agent } from '../api/api';
import { UploadProps, FileItem } from '@douyinfe/semi-ui/lib/es/upload';

interface DocumentUploaderProps {
  visible: boolean;
  onClose: () => void;
}

const DocumentUploader: React.FC<DocumentUploaderProps> = ({ visible, onClose }) => {
  const [uploading, setUploading] = useState(false);
  const [fileList, setFileList] = useState<FileItem[]>([]);

  const handleBeforeUpload = (file: File) => {
    // 只接受文本类型文件
    const acceptTypes = [
      'text/plain', 
      'text/csv', 
      'text/markdown',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/json'
    ];
    
    const isAccepted = acceptTypes.includes(file.type) || 
                       file.name.endsWith('.txt') || 
                       file.name.endsWith('.md') ||
                       file.name.endsWith('.pdf') ||
                       file.name.endsWith('.doc') ||
                       file.name.endsWith('.docx') ||
                       file.name.endsWith('.csv') ||
                       file.name.endsWith('.json');
                       
    if (!isAccepted) {
      Toast.error('不支持的文件类型');
      return false;
    }
    
    // 大小限制 10MB
    const isLt10M = file.size / 1024 / 1024 < 10;
    if (!isLt10M) {
      Toast.error('文件大小不能超过10MB');
      return false;
    }
    
    return true;
  };

  const handleUpload = async () => {
    if (fileList.length === 0) {
      Toast.warning('请先选择要上传的文件');
      return;
    }

    setUploading(true);
    
    try {
      // 上传所有文件
      for (const item of fileList) {
        if (item.fileInstance) {
          Toast.info(`开始上传: ${item.name}`);
          const response = await agent.uploadDocument(item.fileInstance);
          
          if (response.success) {
            Toast.success(`${item.name} 上传成功`);
          } else {
            Toast.error(`${item.name} 上传失败: ${response.message}`);
          }
        }
      }
      
      // 上传完成后清空列表
      setFileList([]);
      onClose();
    } catch (error: any) {
      console.error('文档上传失败:', error);
      Toast.error('上传失败: ' + (error.message || '未知错误'));
    } finally {
      setUploading(false);
    }
  };

  const handleChange: UploadProps['onChange'] = ({ fileList: newFileList }) => {
    setFileList(newFileList);
  };

  return (
    <Modal
      title="上传文档"
      visible={visible}
      onCancel={onClose}
      footer={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={uploading} onClick={handleUpload}>
            上传
          </Button>
        </Space>
      }
      closeOnEsc
      width={600}
    >
      <div style={{ padding: '20px 0' }}>
        <Typography.Paragraph>
          上传文档到知识库，支持 .txt, .pdf, .doc, .docx, .md, .csv, .json 格式，单文件大小不超过10MB。
        </Typography.Paragraph>
        
        <Upload
          action=""
          fileList={fileList}
          onChange={handleChange}
          beforeUpload={handleBeforeUpload as any}
          accept=".txt,.pdf,.doc,.docx,.md,.csv,.json"
          customRequest={({ onSuccess }) => onSuccess && onSuccess({})}
          showUploadList
          className="upload-wrapper"
          draggable
        >
          <div style={{ height: 180, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
            <IconUpload size="extra-large" />
            <Typography.Title heading={6} style={{ margin: '12px 0' }}>
              点击或拖拽文件到此区域上传
            </Typography.Title>
            <Typography.Text type="tertiary">
              支持单个或批量上传
            </Typography.Text>
          </div>
        </Upload>
      </div>
    </Modal>
  );
};

export default DocumentUploader; 