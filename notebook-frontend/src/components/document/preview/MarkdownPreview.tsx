import React, { useEffect, useState } from 'react';
import MarkdownRender from '../../MarkdownRender';
import { Typography, Spin } from '@douyinfe/semi-ui';
import { documents } from '../../../api/api';

interface MarkdownPreviewProps {
  documentId: number;
}

/**
 * Markdown文档预览组件
 * 使用现有的MarkdownRender组件渲染Markdown内容
 * 自行从预览API获取内容
 */
const MarkdownPreview: React.FC<MarkdownPreviewProps> = ({ documentId }) => {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchContent = async () => {
      if (!documentId) {
        setError('缺少文档ID');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        // 使用preview API获取Markdown内容
        const response = await documents.getDocumentPreview(documentId);
        
        if (response.success && response.data) {
          setContent(response.data.content || '');
        } else {
          setError('获取Markdown内容失败');
        }
      } catch (err) {
        console.error('获取Markdown内容错误:', err);
        setError('获取Markdown内容出错: ' + (err instanceof Error ? err.message : String(err)));
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [documentId]);

  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <Typography.Text type="danger">{error}</Typography.Text>
      </div>
    );
  }

  if (!content || content.trim() === '') {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <Typography.Text type="tertiary">无Markdown内容可预览</Typography.Text>
      </div>
    );
  }

  return (
    <div className="markdown-preview" style={{ padding: '16px' }}>
      <MarkdownRender content={content} />
    </div>
  );
};

export default MarkdownPreview; 