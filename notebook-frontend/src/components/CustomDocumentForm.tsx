import React, { useState } from 'react';
import { Input, Button, Toast, Form, Typography, Select } from '@douyinfe/semi-ui';
import { IconEdit, IconSave } from '@douyinfe/semi-icons';
import { documents } from '../api/api';

interface CustomDocumentFormProps {
  onSuccess?: () => void;
}

const { Text } = Typography;
const { Option } = Select;

const CustomDocumentForm: React.FC<CustomDocumentFormProps> = ({ onSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState('');
  const [content, setContent] = useState('');
  const [fileType, setFileType] = useState('txt');

  // 处理提交
  const handleSubmit = async () => {
    if (!name) {
      Toast.error('请输入文档名称');
      return;
    }

    if (!content) {
      Toast.error('请输入文档内容');
      return;
    }

    setLoading(true);
    try {
      const response = await documents.createCustomDocument(name, content, fileType);
      
      if (response.success) {
        Toast.success('文档创建成功');
        resetForm();
        if (onSuccess) {
          onSuccess();
        }
      } else {
        Toast.error(response.message || '文档创建失败');
      }
    } catch (error: any) {
      Toast.error('文档创建失败: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // 重置表单
  const resetForm = () => {
    setName('');
    setContent('');
    setFileType('txt');
  };

  return (
    <div className="custom-document-form">
      <Form onSubmit={handleSubmit}>
        <Form.Input
          field="name"
          label="文档名称"
          placeholder="请输入文档名称"
          value={name}
          onChange={setName}
          showClear
          rules={[
            { required: true, message: '请输入文档名称' }
          ]}
        />
        
        <Form.Select
          field="fileType"
          label="文档类型"
          value={fileType}
          onChange={(value) => setFileType(value as string)}
          style={{ marginBottom: 16 }}
        >
          <Option value="txt">纯文本 (TXT)</Option>
          <Option value="md">Markdown (MD)</Option>
          <Option value="json">JSON</Option>
          <Option value="html">HTML</Option>
          <Option value="csv">CSV</Option>
        </Form.Select>
        
        <Form.TextArea
          field="content"
          label="文档内容"
          placeholder={
            fileType === 'md' ? '# 标题\n\n正文内容...' :
            fileType === 'json' ? '{\n  "key": "value"\n}' :
            fileType === 'html' ? '<html>\n  <body>\n    <h1>标题</h1>\n    <p>正文内容...</p>\n  </body>\n</html>' :
            fileType === 'csv' ? 'id,name,age\n1,张三,25\n2,李四,30' :
            '请输入文档内容...'
          }
          value={content}
          onChange={setContent}
          rows={12}
          showClear
          style={{ fontFamily: 'monospace' }}
          rules={[
            { required: true, message: '请输入文档内容' }
          ]}
        />
        
        <div style={{ marginTop: 16 }}>
          <Text type="tertiary">
            自定义文档将直接保存您输入的内容，无需上传文件。
            请选择合适的文档类型，以便系统能正确解析内容。
          </Text>
        </div>
        
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Button 
            type="tertiary" 
            style={{ marginRight: 8 }}
            onClick={resetForm}
          >
            重置
          </Button>
          
          <Button 
            type="primary" 
            theme="solid" 
            htmlType="submit"
            loading={loading}
            disabled={!name || !content}
            icon={<IconSave />}
          >
            创建文档
          </Button>
        </div>
      </Form>
    </div>
  );
};

export default CustomDocumentForm; 