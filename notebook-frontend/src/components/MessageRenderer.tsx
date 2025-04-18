import React, { useEffect, useState, useRef } from 'react';
import { marked } from 'marked';

interface MessageRendererProps {
  content: string;
  useTypingEffect?: boolean;
  typingSpeed?: number;
  forceKey?: string;
}

const MessageRenderer: React.FC<MessageRendererProps> = ({
  content,
  useTypingEffect = false,
  typingSpeed = 15,
  forceKey,
}) => {
  const [htmlContent, setHtmlContent] = useState<string>('');
  const instanceId = useRef(Math.random().toString(36).substring(7)).current;
  const forceUpdateRef = useRef(0);

  useEffect(() => {
    if (!content) {
      setHtmlContent('');
      return;
    }

    try {
      marked.setOptions({
        breaks: true,
        gfm: true,
      });
      
      const parsedHtml = String(marked.parse(content));
      setHtmlContent(parsedHtml);
    } catch (error) {
      console.error('Markdown解析错误:', error);
      setHtmlContent(`<pre style="white-space: pre-wrap; word-break: break-word;">${content}</pre>`);
    }
  }, [content]);

  // 计算组件key，用于强制更新
  const computedKey = `mr-${instanceId}-${forceUpdateRef.current}-${forceKey || ''}`;

  return (
    <div 
      key={computedKey}
      style={{ display: 'block', width: '100%', minHeight: '24px' }}
    >
      <div
        className="markdown-content"
        style={{ 
          visibility: 'visible',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word'
        }}
        dangerouslySetInnerHTML={{ __html: htmlContent }}
      />
    </div>
  );
};

export default MessageRenderer; 