import React, { useState } from 'react';
import { Input, Button, Toast, Form, Typography, Select, Banner, Tooltip, Steps } from '@douyinfe/semi-ui';
import { IconEdit, IconSave, IconInfoCircle } from '@douyinfe/semi-icons';
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

  // 获取提交按钮的禁用提示
  const getSubmitTooltip = (): string => {
    if (!name) return '请输入文档名称';
    if (!content) return '请输入文档内容';
    return '';
  };

  // 获取当前完成的步骤数
  const getCompletedSteps = (): number => {
    let steps = 0;
    if (name) steps++;
    if (content) steps++;
    return steps;
  };

  // 获取适合当前文档类型的示例内容
  const getPlaceholderByFileType = () => {
    switch (fileType) {
      case 'md': 
        return '# 标题\n\n正文内容...';
      case 'json': 
        return '{\n  "key": "value"\n}';
      case 'html': 
        return '<html>\n  <body>\n    <h1>标题</h1>\n    <p>正文内容...</p>\n  </body>\n</html>';
      case 'csv': 
        return 'id,name,age\n1,张三,25\n2,李四,30';
      default:
        return '请输入文档内容...';
    }
  };

  return (
    <div className="custom-document-form">
      <Banner
        type="info"
        icon={<IconInfoCircle />}
        title="创建自定义文档"
        description="自定义文档将直接保存您输入的内容，无需上传文件。请选择合适的文档类型，以便系统能正确解析内容。"
        style={{ marginBottom: 16 }}
      />

      {/* 步骤指示器 */}
      <div style={{ marginBottom: 16 }}>
        <Steps type="basic" current={getCompletedSteps()} size="small">
          <Steps.Step title="输入文档名称" status={name ? 'finish' : 'wait'} />
          <Steps.Step title="输入文档内容" status={content ? 'finish' : 'wait'} />
        </Steps>
      </div>

      <Form onSubmit={handleSubmit}>
        <Form.Input
          field="name"
          label={<>文档名称 <Text type="danger">*</Text></>}
          placeholder="请输入文档名称"
          showClear
          value={name}
          validateStatus={name ? 'success' : 'error'}
          helpText={!name ? '请输入文档名称' : undefined}
          onChange={val => setName(val)}
        />
        
        <Form.Select
          field="fileType"
          label="文档类型"
          style={{ marginBottom: 16 }}
          value={fileType}
          onChange={val => setFileType(val as string)}
        >
          <Option value="txt">纯文本 (TXT)</Option>
          <Option value="md">Markdown (MD)</Option>
          <Option value="json">JSON</Option>
          <Option value="html">HTML</Option>
          <Option value="csv">CSV</Option>
        </Form.Select>
        
        <Form.TextArea
          field="content"
          label={<>文档内容 <Text type="danger">*</Text></>}
          placeholder={getPlaceholderByFileType()}
          rows={12}
          showClear
          value={content}
          style={{ fontFamily: 'monospace' }}
          validateStatus={content ? 'success' : 'error'}
          helpText={!content ? '请输入文档内容' : undefined}
          onChange={val => setContent(val)}
        />
        
        {/* 表单状态提示 */}
        <Banner 
          style={{ marginTop: 16 }}
          type={name && content ? "success" : "warning"} 
          description={
            <div>
              <div style={{ fontWeight: 'bold' }}>状态:</div>
              <ul style={{ paddingLeft: 20, margin: '4px 0 0 0' }}>
                <li style={{ color: name ? 'var(--semi-color-success)' : 'var(--semi-color-danger)' }}>
                  {name ? '✓ 已输入文档名称' : '× 请输入文档名称'}
                </li>
                <li style={{ color: content ? 'var(--semi-color-success)' : 'var(--semi-color-danger)' }}>
                  {content ? '✓ 已输入文档内容' : '× 请输入文档内容'}
                </li>
              </ul>
            </div>
          }
        />
        
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Button 
            type="tertiary" 
            style={{ marginRight: 8 }}
            onClick={resetForm}
          >
            重置
          </Button>
          
          <Tooltip
            content={getSubmitTooltip()}
            position="top"
            trigger="hover"
            visible={!name || !content ? undefined : false}
          >
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
          </Tooltip>
        </div>
      </Form>
    </div>
  );
};

export default CustomDocumentForm; 