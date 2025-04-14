import React, { useState } from 'react';
import { Modal, Upload, Form, Input, Button, Toast, Typography, Tabs } from '@douyinfe/semi-ui';
import { IconUpload, IconFile, IconGlobe, IconEdit } from '@douyinfe/semi-icons';
import { documents } from '../api/api';
import WebDocumentForm from './WebDocumentForm';
import CustomDocumentForm from './CustomDocumentForm';

interface DocumentUploaderProps {
  visible: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

const { Paragraph, Text } = Typography;
const { TabPane } = Tabs;

const DocumentUploader: React.FC<DocumentUploaderProps> = ({
  visible,
  onClose,
  onSuccess
}) => {
  const [uploadLoading, setUploadLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState('');
  const [metadata, setMetadata] = useState('');
  const [activeTab, setActiveTab] = useState('upload');

  // 处理文件变更
  const handleFileChange = (files: File[]) => {
    if (files && files.length > 0) {
      const selectedFile = files[0];
      setFile(selectedFile);
      
      // 自动填充文件名（去除扩展名）
      const nameWithoutExt = selectedFile.name.replace(/\.[^/.]+$/, "");
      setFileName(nameWithoutExt);
    }
  };

  // 处理上传
  const handleUpload = async () => {
    if (!file) {
      Toast.error('请选择要上传的文件');
      return;
    }

    if (!fileName.trim()) {
      Toast.error('请输入文档名称');
      return;
    }

    // 解析元数据
    let parsedMetadata = {};
    if (metadata && metadata.trim()) {
      try {
        parsedMetadata = JSON.parse(metadata);
      } catch (error) {
        Toast.error('元数据格式不正确，请输入有效的JSON');
        return;
      }
    }

    setUploadLoading(true);
    try {
      const response = await documents.uploadDocument(file, {
        name: fileName,
        ...parsedMetadata
      });

      if (response.success) {
        Toast.success('文档上传成功');
        resetForm();
        onClose();
        
        if (onSuccess) {
          onSuccess();
        }
      } else {
        Toast.error(response.message || '上传文档失败');
      }
    } catch (error: any) {
      Toast.error('上传文档失败: ' + (error.message || '未知错误'));
    } finally {
      setUploadLoading(false);
    }
  };

  // 重置表单
  const resetForm = () => {
    setFile(null);
    setFileName('');
    setMetadata('');
    setActiveTab('upload');
  };
  
  // 处理标签页变更
  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
  };
  
  // 处理其他方式添加文档成功
  const handleOtherSuccess = () => {
    if (onSuccess) {
      onSuccess();
    }
    onClose();
  };

  return (
    <Modal
      title="添加文档"
      visible={visible}
      onCancel={() => {
        resetForm();
        onClose();
      }}
      footer={
        activeTab === 'upload' ? (
          <Button 
            icon={<IconUpload />}
            type="primary"
            onClick={handleUpload}
            loading={uploadLoading}
            disabled={!file}
          >
            上传
          </Button>
        ) : null
      }
      closeOnEsc
      width={700}
    >
      <Tabs activeKey={activeTab} onChange={handleTabChange}>
        <TabPane 
          tab={<span><IconUpload style={{ marginRight: 4 }} />本地文件</span>} 
          itemKey="upload"
        >
          <div style={{ padding: '16px 0' }}>
            <Form labelPosition="left" labelWidth={100}>
              <div style={{ marginBottom: 20 }}>
                <Upload
                  action=""
                  accept=".pdf,.doc,.docx,.txt,.md,.xls,.xlsx,.csv,.json,.html,.htm"
                  draggable
                  uploadTrigger="custom"
                  beforeUpload={() => false}
                  onChange={({ fileList }) => {
                    const files = fileList.map(item => item.originFile).filter(Boolean) as File[];
                    if (files.length > 0) {
                      handleFileChange([files[0]]);
                    }
                  }}
                  onRemove={() => {
                    setFile(null);
                    setFileName('');
                  }}
                  style={{ width: '100%' }}
                >
                  {file ? (
                    <div style={{ 
                      padding: '20px', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center' 
                    }}>
                      <IconFile size="large" style={{ marginRight: 8 }} />
                      <span>{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                    </div>
                  ) : (
                    <div style={{ 
                      display: 'flex', 
                      flexDirection: 'column', 
                      alignItems: 'center', 
                      padding: '40px 20px' 
                    }}>
                      <IconUpload size="extra-large" style={{ marginBottom: 16, color: 'var(--semi-color-primary)' }} />
                      <Text>拖拽文件到此处或点击上传</Text>
                      <Paragraph type="tertiary" style={{ marginTop: 8 }}>
                        支持 PDF, Word, Excel, TXT, Markdown, CSV, JSON, HTML 等格式
                      </Paragraph>
                    </div>
                  )}
                </Upload>
              </div>

              <Form.Input
                field="name"
                label="文档名称"
                value={fileName}
                onChange={setFileName}
                placeholder="请输入文档名称"
                showClear
              />
              
              <Form.TextArea
                field="metadata"
                label="元数据（可选）"
                value={metadata}
                onChange={setMetadata}
                placeholder='请输入JSON格式的元数据，例如: {"tags": ["重要", "研究"], "category": "报告"}'
                autosize={{ minRows: 3, maxRows: 6 }}
                style={{ fontFamily: 'monospace' }}
              />
              
              <div style={{ marginTop: 16 }}>
                <Text type="tertiary">
                  元数据用于存储文档的额外信息，如标签、分类等。请使用JSON格式。
                </Text>
              </div>
            </Form>
          </div>
        </TabPane>
        
        <TabPane 
          tab={<span><IconGlobe style={{ marginRight: 4 }} />网页</span>} 
          itemKey="web"
        >
          <WebDocumentForm onSuccess={handleOtherSuccess} />
        </TabPane>
        
        <TabPane 
          tab={<span><IconEdit style={{ marginRight: 4 }} />自定义</span>} 
          itemKey="custom"
        >
          <CustomDocumentForm onSuccess={handleOtherSuccess} />
        </TabPane>
      </Tabs>
    </Modal>
  );
};

export default DocumentUploader; 