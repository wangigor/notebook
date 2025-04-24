import React, { useState } from 'react';
import { Input, Button, Toast, Form, Typography, Banner, Tooltip } from '@douyinfe/semi-ui';
import { IconGlobe, IconInfoCircle } from '@douyinfe/semi-icons';
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
        // 重置状态
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

  // 获取提交按钮禁用提示
  const getSubmitTooltip = (): string => {
    if (!url) return '请输入网页URL';
    if (!isValidUrl(url)) return '请输入有效的URL格式';
    return '';
  };

  return (
    <div className="web-document-form">
      <Banner
        type="info"
        icon={<IconInfoCircle />}
        title="从网页创建文档"
        description="系统将提取网页内容并自动创建文档。支持大多数网页，但部分需要登录或动态加载的内容可能无法完全提取。"
        style={{ marginBottom: 16 }}
      />
      
      <Form onSubmit={handleSubmit}>
        <Form.Input
          field="url"
          label={<>网页URL <Text type="danger">*</Text></>}
          placeholder="请输入完整的网页URL，例如：https://example.com"
          prefix={<IconGlobe />}
          showClear
          value={url}
          validateStatus={url ? (isValidUrl(url) ? 'success' : 'error') : 'default'}
          helpText={url && !isValidUrl(url) ? '请输入有效的URL，格式如：https://example.com' : undefined}
          onChange={val => setUrl(val)}
        />
        
        <div style={{ marginTop: 16 }}>
          <Banner 
            type={url && isValidUrl(url) ? "success" : "warning"} 
            description={
              <div>
                <div style={{ fontWeight: 'bold' }}>状态:</div>
                <ul style={{ paddingLeft: 20, margin: '4px 0 0 0' }}>
                  <li style={{ color: url ? 'var(--semi-color-success)' : 'var(--semi-color-danger)' }}>
                    {url ? '✓ 已输入URL' : '× 请输入网页URL'}
                  </li>
                  {url && (
                    <li style={{ color: isValidUrl(url) ? 'var(--semi-color-success)' : 'var(--semi-color-danger)' }}>
                      {isValidUrl(url) ? '✓ URL格式正确' : '× URL格式不正确'}
                    </li>
                  )}
                </ul>
              </div>
            }
          />
        </div>
        
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Tooltip
            content={getSubmitTooltip()}
            position="top"
            trigger="hover"
            visible={!url || !isValidUrl(url) ? undefined : false}
          >
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
          </Tooltip>
        </div>
      </Form>
    </div>
  );
};

export default WebDocumentForm; 