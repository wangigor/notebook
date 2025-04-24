import React, { useState, useEffect } from 'react';
import { Modal, Upload, Form, Input, Button, Toast, Typography, Tabs, Tooltip, Banner, Steps } from '@douyinfe/semi-ui';
import { IconUpload, IconFile, IconGlobe, IconEdit, IconInfoCircle } from '@douyinfe/semi-icons';
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

  // 添加useEffect跟踪file状态变化
  useEffect(() => {
    console.log('file状态已更新:', file ? `${file.name} (${file.size} bytes)` : 'null');
  }, [file]);

  // 验证JSON字符串
  const isValidJson = (jsonString: string): boolean => {
    if (!jsonString.trim()) return true;
    try {
      JSON.parse(jsonString);
      return true;
    } catch (e) {
      return false;
    }
  };

  // 验证表单是否有效
  const isFormValid = (): boolean => {
    return !!file && !!fileName.trim() && (metadata ? isValidJson(metadata) : true);
  };

  // 获取上传按钮的禁用提示
  const getUploadButtonTooltip = (): string => {
    if (!file) return '请选择要上传的文件';
    if (!fileName.trim()) return '请输入文档名称';
    if (metadata && !isValidJson(metadata)) return '元数据格式不正确，请输入有效的JSON';
    return '';
  };

  // 获取已完成步骤数
  const getCompletedSteps = (): number => {
    let steps = 0;
    if (file) steps++;
    if (fileName.trim()) steps++;
    if (!metadata || isValidJson(metadata)) steps++;
    return steps;
  };

  // 处理文件变更
  const handleFileChange = (files: any[]) => {
    if (files && files.length > 0) {
      const selectedFile = files[0];
      console.log('文件已选择:', selectedFile.name);
      
      // 保存文件对象到状态
      setFile(selectedFile);
      
      // 自动填充文件名（去除扩展名）
      const nameWithoutExt = selectedFile.name.replace(/\.[^/.]+$/, "");
      setFileName(nameWithoutExt);
    } else {
      console.log('没有选择文件或文件已清除');
      setFile(null);
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
      // 获取文件的二进制数据
      // 根据file对象的类型采取不同的策略
      let fileToUpload: File;
      
      if (file instanceof File) {
        // 如果已经是File实例，直接使用
        fileToUpload = file;
      } else if (file.url && file.url.startsWith('blob:')) {
        // 如果是Semi UI的文件对象且有blob URL
        try {
          const response = await fetch(file.url);
          const blob = await response.blob();
          fileToUpload = new File([blob], file.name, { type: blob.type });
        } catch (error) {
          console.error('转换文件对象失败:', error);
          Toast.error('处理文件失败');
          setUploadLoading(false);
          return;
        }
      } else {
        // 处理其他情况，尝试使用File API
        console.warn('未知的文件对象类型，尝试直接上传');
        fileToUpload = file as any;
      }

      const response = await documents.uploadDocument(fileToUpload, {
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
      console.error('上传文档错误:', error);
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
          <Tooltip
            content={getUploadButtonTooltip()}
            position="top"
            trigger="hover"
            visible={!isFormValid() ? undefined : false}
          >
            <Button 
              icon={<IconUpload />}
              type="primary"
              onClick={handleUpload}
              loading={uploadLoading}
              disabled={!isFormValid()}
            >
              上传
            </Button>
          </Tooltip>
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
            <Form 
              labelPosition="left" 
              labelWidth={100}
            >
              {/* 添加表单完成进度指示器 */}
              <div style={{ marginBottom: 20 }}>
                <Steps type="basic" current={getCompletedSteps()} size="small">
                  <Steps.Step title="选择文件" status={file ? 'finish' : 'wait'} />
                  <Steps.Step title="文档命名" status={fileName.trim() ? 'finish' : 'wait'} />
                  <Steps.Step 
                    title="添加元数据" 
                    status={metadata && !isValidJson(metadata) ? 'error' : metadata ? 'finish' : 'wait'} 
                  />
                </Steps>
              </div>

              {/* 提交条件可视化反馈 */}
              <Banner
                type="info"
                icon={<IconInfoCircle />}
                title="上传须知"
                description={
                  <ul style={{ paddingLeft: 20, margin: '8px 0 0 0' }}>
                    <li style={{ 
                      color: file ? 'var(--semi-color-success)' : 'var(--semi-color-danger)',
                      transition: 'color 0.3s' // 添加颜色过渡效果
                    }}>
                      {file ? `✓ 已选择文件: ${file.name}` : '× 请选择要上传的文件'}
                    </li>
                    <li style={{ 
                      color: fileName.trim() ? 'var(--semi-color-success)' : 'var(--semi-color-danger)',
                      transition: 'color 0.3s' // 添加颜色过渡效果
                    }}>
                      {fileName.trim() ? '✓ 已填写文档名称' : '× 请输入文档名称'}
                    </li>
                    {metadata && (
                      <li style={{ color: isValidJson(metadata) ? 'var(--semi-color-success)' : 'var(--semi-color-danger)' }}>
                        {isValidJson(metadata) ? '✓ 元数据格式正确' : '× 元数据必须是有效的JSON格式'}
                      </li>
                    )}
                  </ul>
                }
                style={{ marginBottom: 20 }}
              />
              
              <div style={{ marginBottom: 20 }}>
                <Upload
                  action="#"
                  accept=".pdf,.doc,.docx,.txt,.md,.xls,.xlsx,.csv,.json,.html,.htm"
                  draggable
                  uploadTrigger="custom"
                  beforeUpload={() => false}
                  onChange={({ fileList }) => {
                    if (fileList && fileList.length > 0) {
                      handleFileChange([...fileList]);
                    } else {
                      setFile(null);
                      setFileName('');
                    }
                  }}
                  onRemove={() => {
                    setFile(null);
                    setFileName('');
                  }}
                  style={{ width: '100%' }}
                  limit={1}
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
                label={<>文档名称 <Text type="danger">*</Text></>}
                value={fileName}
                onChange={setFileName}
                placeholder="请输入文档名称"
                showClear
                validateStatus={fileName.trim() ? 'success' : 'error'}
                helpText={!fileName.trim() ? '文档名称不能为空' : undefined}
              />
              
              <Form.TextArea
                field="metadata"
                label="元数据（可选）"
                value={metadata}
                onChange={setMetadata}
                placeholder='请输入JSON格式的元数据，例如: {"tags": ["重要", "研究"], "category": "报告"}'
                autosize={{ minRows: 3, maxRows: 6 }}
                style={{ fontFamily: 'monospace' }}
                validateStatus={metadata && !isValidJson(metadata) ? 'error' : undefined}
                helpText={metadata && !isValidJson(metadata) ? 'JSON格式不正确，请检查语法' : undefined}
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