import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Button, Toast, Spin, Tabs, Typography, Notification } from '@douyinfe/semi-ui';
import { IconSave } from '@douyinfe/semi-icons';
import { documents } from '../api/api';
import { Document, DocumentPreview } from '../types';

interface DocumentEditModalProps {
  visible: boolean;
  document: Document | DocumentPreview;
  onClose: () => void;
  onSuccess: (updatedDoc: Document) => void;
}

const { Text } = Typography;

const DocumentEditModal: React.FC<DocumentEditModalProps> = ({
  visible,
  document,
  onClose,
  onSuccess
}) => {
  const [loading, setLoading] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('basic');
  
  // 表单数据
  const [formData, setFormData] = useState({
    name: '',
    metadata: '',
    content: '',
    extracted_text: ''
  });
  
  // 加载文档信息
  useEffect(() => {
    if (visible && document) {
      loadDocument();
    }
  }, [visible, document]);
  
  const loadDocument = async () => {
    setLoading(true);
    try {
      const response = await documents.getDocument(document.id);
      
      if (response.success && response.data) {
        setFormData({
          name: response.data.name || '',
          metadata: JSON.stringify(response.data.metadata || {}, null, 2),
          content: response.data.content || '',
          extracted_text: response.data.extracted_text || ''
        });
      } else {
        Toast.error(response.message || '获取文档信息失败');
      }
    } catch (error: any) {
      Toast.error('获取文档信息失败: ' + (error.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  };
  
  // 处理表单值变化
  const handleChange = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };
  
  // 处理表单提交
  const handleSubmit = async (values: { name: string; metadata: string }) => {
    setLoading(true);
    
    try {
      // 验证元数据是否为有效的JSON
      let parsedMetadata = {};
      try {
        parsedMetadata = JSON.parse(values.metadata);
        if (typeof parsedMetadata !== 'object' || parsedMetadata === null) {
          throw new Error('元数据必须是有效的JSON对象');
        }
      } catch (err) {
        Notification.error({
          title: '格式错误',
          content: '元数据必须是有效的JSON格式',
          duration: 3
        });
        setLoading(false);
        return;
      }
      
      // 更新文档
      const updateData = {
        name: values.name,
        metadata: parsedMetadata
      };
      
      const response = await documents.updateDocument(document.id, updateData);
      
      if (response.success) {
        Notification.success({
          title: '更新成功',
          content: '文档信息已成功更新',
          duration: 3
        });
        
        // 返回更新后的文档
        onSuccess({
          ...document,
          ...updateData
        });
      } else {
        throw new Error(response.message || '更新失败');
      }
    } catch (error) {
      console.error('文档更新失败:', error);
      Notification.error({
        title: '更新失败',
        content: error instanceof Error ? error.message : '更新文档时发生错误',
        duration: 3
      });
    } finally {
      setLoading(false);
    }
  };
  
  // 预览不可编辑的二进制文件
  const renderBinaryFilePreview = () => {
    if (document?.file_type && ['pdf', 'doc', 'docx', 'xls', 'xlsx'].includes(document.file_type)) {
      return (
        <div style={{ padding: '16px', textAlign: 'center' }}>
          <Typography.Title heading={5}>二进制文件</Typography.Title>
          <Typography.Paragraph>
            此类型的文件内容不能直接编辑。您只能修改文件名称和元数据。
            如需修改文件内容，请上传新版本的文件。
          </Typography.Paragraph>
        </div>
      );
    }
    return null;
  };
  
  return (
    <Modal
      title="编辑文档信息"
      visible={visible}
      onCancel={onClose}
      footer={null}
      closeOnEsc
      width={600}
    >
      <Form form={form} onSubmit={handleSubmit} labelPosition="left" labelWidth={100}>
        <Form.Input
          field="name"
          label="文档名称"
          placeholder="请输入文档名称"
          rules={[{ required: true, message: '请输入文档名称' }]}
        />
        
        <div style={{ marginBottom: 16 }}>
          <Text strong>文件名: </Text>
          <Text>{document?.filename}</Text>
        </div>
        
        <Form.TextArea
          field="metadata"
          label="元数据 (JSON)"
          placeholder="请输入有效的JSON格式元数据"
          rows={10}
          rules={[
            { 
              required: true, 
              message: '请输入元数据' 
            },
            {
              validator: (rule, value) => {
                try {
                  if (!value) return true;
                  const parsed = JSON.parse(value);
                  return typeof parsed === 'object' && parsed !== null;
                } catch (e) {
                  return false;
                }
              },
              message: '必须是有效的JSON格式'
            }
          ]}
        />
        
        <div style={{ marginTop: 24, textAlign: 'right' }}>
          <Button type="tertiary" style={{ marginRight: 8 }} onClick={onClose}>
            取消
          </Button>
          <Button 
            type="primary" 
            htmlType="submit" 
            loading={loading}
            icon={<IconSave />}
          >
            保存修改
          </Button>
        </div>
      </Form>
    </Modal>
  );
};

export default DocumentEditModal; 