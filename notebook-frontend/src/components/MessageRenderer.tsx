import { FC, useEffect, useState, useRef } from 'react';
import { Typography, Spin } from '@douyinfe/semi-ui';

interface MessageRendererProps {
  content: string;
  typing?: boolean;
  typingSpeed?: number;
}

/**
 * 消息渲染器组件，支持打字机效果
 */
const MessageRenderer: FC<MessageRendererProps> = ({
  content,
  typing = true,
  typingSpeed = 10, // 每个字符的显示速度（毫秒）
}) => {
  const [displayedContent, setDisplayedContent] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const contentRef = useRef(content);
  const lastTimeRef = useRef(0);
  const timeoutRef = useRef<number | null>(null);

  // 当内容变化时，更新内容引用
  useEffect(() => {
    // 调试内容变化
    console.log('内容变化:', { 
      oldContent: contentRef.current, 
      newContent: content,
      displayedLength: displayedContent.length,
      isTyping
    });
    
    // 如果当前显示的内容已经包含了新内容的前缀，则只追加新内容
    if (content.startsWith(contentRef.current) && isTyping) {
      contentRef.current = content;
      return;
    }
    
    // 内容完全变化时，重置打字状态
    if (content !== contentRef.current) {
      contentRef.current = content;
      
      if (typing) {
        // 如果启用了打字效果，且内容发生变化
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }
        
        setIsTyping(true);
        
        // 如果新内容包含已显示内容的前缀，保留已显示内容
        if (content.startsWith(displayedContent)) {
          // 无需重置显示内容，只需继续显示后续内容
        } else if (displayedContent.length > 0 && !content.startsWith(displayedContent)) {
          // 如果内容完全改变，重置显示内容
          setDisplayedContent('');
        }
      } else {
        // 如果没有启用打字效果，直接显示全部内容
        setDisplayedContent(content);
      }
    }
  }, [content, typing, isTyping, displayedContent]);

  // 打字效果
  useEffect(() => {
    if (!typing || !isTyping) return;
    
    if (displayedContent.length >= contentRef.current.length) {
      setIsTyping(false);
      return;
    }
    
    const now = Date.now();
    const delta = now - lastTimeRef.current;
    
    // 根据时间差来决定显示几个字符
    const charsToAdd = Math.max(1, Math.floor(delta / typingSpeed));
    
    // 计算下一个要显示的字符的位置
    const nextPos = Math.min(displayedContent.length + charsToAdd, contentRef.current.length);
    
    if (nextPos > displayedContent.length) {
      // 如果是流式输入，调整打字速度让体验更自然
      const adjustedTypingSpeed = contentRef.current.length > 100 ? 1 : typingSpeed;
      
      timeoutRef.current = window.setTimeout(() => {
        setDisplayedContent(contentRef.current.substring(0, nextPos));
        lastTimeRef.current = now;
      }, adjustedTypingSpeed);
    } else {
      setIsTyping(false);
    }
    
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [displayedContent, typing, typingSpeed, isTyping]);

  return (
    <div className="message-content">
      <Typography.Text className="whitespace-pre-wrap">
        {displayedContent}
        {isTyping && (
          <span className="typing-indicator">
            <Spin size="small" />
          </span>
        )}
      </Typography.Text>
    </div>
  );
};

export default MessageRenderer; 