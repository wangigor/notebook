import React, { useState } from 'react';
import { Input, Button, Toast, Form, Typography } from '@douyinfe/semi-ui';
import { IconGlobe } from '@douyinfe/semi-icons';
import { documents } from '../api/api';

interface WebDocumentFormProps {
  onSuccess?: () => void;
}

const { Text } = Typography;

const WebDocumentForm: React.FC<WebDocumentFormProps> = ({ onSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [url, setUrl] = useState('');

  // 处理提交
  const handleSubmit = async () => {
    if (!url) {
      Toast.error('请输入网页URL');
      return;
    }

    if (!isValidUrl(url)) {
      Toast.error('请输入有效的URL，格式如：https://example.com');
      return;
    }

    setLoading(true);
    try {
      const response = await documents.loadFromWeb(url);
      
      if (response.success) {
        Toast.success('网页内容已成功加载');
        setUrl('');
        if (onSuccess) {
          onSuccess();
        }
      } else {
        Toast.error(response.message || '加载网页失败');
      }
    } catch (error: any) {
      Toast.error('加载网页失败: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // 验证URL
  const isValidUrl = (string: string): boolean => {
    try {
      new URL(string);
      return true;
    } catch (_) {
      return false;
    }
  };

  return (
    <div className="web-document-form">
      <Form onSubmit={handleSubmit}>
        <Form.Input
          field="url"
          label="网页URL"
          placeholder="请输入完整的网页URL，例如：https://example.com"
          value={url}
          onChange={setUrl}
          prefix={<IconGlobe />}
          showClear
          validateStatus={url ? (isValidUrl(url) ? 'success' : 'error') : undefined}
          help={url && !isValidUrl(url) ? '请输入有效的URL，格式如：https://example.com' : undefined}
        />
        
        <div style={{ marginTop: 16 }}>
          <Text type="tertiary">
            从网页加载内容将会提取网页的文本内容并创建为新文档。支持大多数网页，
            但部分需要登录或动态加载的内容可能无法完全提取。
          </Text>
        </div>
        
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Button 
            type="primary" 
            theme="solid" 
            htmlType="submit"
            loading={loading}
            disabled={!url || !isValidUrl(url)}
            icon={<IconGlobe />}
          >
            加载网页
          </Button>
        </div>
      </Form>
    </div>
  );
};

export default WebDocumentForm; 