import React, { useEffect, useState } from 'react';
import { Typography, Spin } from '@douyinfe/semi-ui';
import SyntaxHighlighter from 'react-syntax-highlighter';
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import { documents } from '../../../api/api';

interface TextPreviewProps {
  documentId: number;
  filename: string;
}

/**
 * 文本文件预览组件
 * 支持语法高亮和根据文件扩展名自动检测语言
 * 自行从预览API获取内容
 */
const TextPreview: React.FC<TextPreviewProps> = ({ documentId, filename }) => {
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
        // 使用preview API获取文本内容
        const response = await documents.getDocumentPreview(documentId);
        
        if (response.success && response.data) {
          setContent(response.data.content || '');
        } else {
          setError('获取文本内容失败');
        }
      } catch (err) {
        console.error('获取文本内容错误:', err);
        setError('获取文本内容出错: ' + (err instanceof Error ? err.message : String(err)));
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [documentId]);

  // 根据文件名猜测语言（简化版）
  const guessLanguage = (filename: string): string => {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    const langMap: Record<string, string> = {
      js: 'javascript',
      ts: 'typescript',
      py: 'python',
      java: 'java',
      json: 'json',
      html: 'html',
      css: 'css',
      xml: 'xml',
      md: 'markdown',
      sql: 'sql',
      sh: 'bash',
      bash: 'bash',
      php: 'php',
      rb: 'ruby',
      go: 'go',
      rust: 'rust',
      cs: 'csharp',
      cpp: 'cpp',
      c: 'c',
      kt: 'kotlin',
      swift: 'swift'
    };
    
    return langMap[extension] || 'text';
  };
  
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
        <Typography.Text type="tertiary">文本内容为空</Typography.Text>
      </div>
    );
  }

  const language = guessLanguage(filename);
  
  return (
    <div className="text-preview" style={{ maxHeight: '600px', overflow: 'auto' }}>
      <SyntaxHighlighter
        language={language}
        style={docco}
        showLineNumbers={true}
        customStyle={{
          margin: 0,
          padding: '16px',
          fontSize: '14px',
          borderRadius: '4px',
          fontFamily: 'monospace'
        }}
      >
        {content}
      </SyntaxHighlighter>
    </div>
  );
};

export default TextPreview; 