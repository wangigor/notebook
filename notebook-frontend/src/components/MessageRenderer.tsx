import { FC, useEffect, useState, useRef, useId, useLayoutEffect } from 'react';
import { Typography, Spin } from '@douyinfe/semi-ui';
import { marked } from 'marked';
import 'highlight.js/styles/github.css';

interface MessageRendererProps {
  content: string;
  typing?: boolean;
  typingSpeed?: number;
  forceKey?: string; // 用于强制更新的key
}

/**
 * 消息渲染器组件，支持打字机效果
 */
const MessageRenderer: FC<MessageRendererProps> = ({
  content,
  typing = true,
  typingSpeed = 10, // 每个字符的显示速度（毫秒）
  forceKey,
}) => {
  const uniqueId = useId(); // 生成唯一ID
  const instanceId = useRef(`mr-${Math.random().toString(36).substring(2, 8)}`).current; // 实例ID
  const [displayedContent, setDisplayedContent] = useState('');
  const [htmlContent, setHtmlContent] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [typingComplete, setTypingComplete] = useState(false);
  const contentRef = useRef(content || '');
  const charIndexRef = useRef(0);
  const timeoutRef = useRef<number | null>(null);
  const prevContentRef = useRef('');
  const forceUpdateRef = useRef(0); // 用于强制重新计算
  const mountTimeRef = useRef(Date.now()); // 记录组件挂载时间
  
  // 组件挂载和卸载处理
  useLayoutEffect(() => {
    // 设置一个间隔定时器防止打字效果停滞
    const intervalId = setInterval(() => {
      if (isTyping && !typingComplete && charIndexRef.current < contentRef.current.length) {
        const lastCharTime = Date.now() - mountTimeRef.current;
        if (lastCharTime > 3000) { // 如果3秒内没有进展
          // 恢复打字效果
          forceUpdateRef.current += 1;
          setIsTyping(true);
          setTypingComplete(false);
          
          if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
          }
        }
      }
    }, 1000);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      clearInterval(intervalId);
    };
  }, []);
  
  // 处理forceKey变化
  useEffect(() => {
    if (forceKey) {
      forceUpdateRef.current += 1;
      
      // 清除打字计时器
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      
      // 重置打字状态
      if (typing) {
        charIndexRef.current = 0; // 从头开始
        setDisplayedContent(''); // 清空已显示内容
        setIsTyping(true); // 激活打字效果
        setTypingComplete(false); // 重置完成状态
      }
    }
  }, [forceKey, typing]);

  // 处理content变化
  useEffect(() => {
    const safeContent = content || '';
    const contentChanged = prevContentRef.current !== safeContent;
    
    // 更新内容引用
    contentRef.current = safeContent;
    
    // 内容变化或有强制更新key时重置状态
    if (contentChanged || forceKey) {
      // 清除打字超时
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      
      // 处理不需要打字效果的情况
      if (!typing) {
        setDisplayedContent(safeContent);
        setIsTyping(false);
        setTypingComplete(true);
      } else {
        // 重置打字状态
        charIndexRef.current = 0;
        setDisplayedContent('');
        setIsTyping(true);
        setTypingComplete(false);
        forceUpdateRef.current += 1;
      }
      
      // 保存新内容
      prevContentRef.current = safeContent;
    }
  }, [content, typing, forceKey]);

  // 打字效果逻辑
  useEffect(() => {
    if (!isTyping) return;
    
    const currentContent = contentRef.current;
    
    // 没有内容则跳过
    if (!currentContent) {
      setIsTyping(false);
      return;
    }
    
    // 已经到达内容末尾，标记为完成
    if (charIndexRef.current >= currentContent.length) {
      setTypingComplete(true);
      setIsTyping(false);
      return;
    }
    
    // 计算打字速度
    const baseSpeed = typingSpeed || 10;
    const adjustedSpeed = currentContent.length > 500
      ? Math.max(1, baseSpeed / 4)  // 长内容加速
      : currentContent.length > 200
        ? Math.max(1, baseSpeed / 2)  // 中等内容
        : baseSpeed;  // 短内容
    
    // 下一个字符位置
    let nextCharIndex = charIndexRef.current + 1;
    
    // 连续处理特殊字符
    if (currentContent[charIndexRef.current] === '\n' || 
        currentContent[charIndexRef.current] === ' ') {
      while (
        nextCharIndex < currentContent.length && 
        (currentContent[nextCharIndex] === '\n' || 
         currentContent[nextCharIndex] === ' ')
      ) {
        nextCharIndex++;
      }
    }
    
    // 处理代码块，加速
    const isCodeBlock = 
      currentContent.substring(charIndexRef.current).startsWith('```') || 
      (charIndexRef.current > 2 && currentContent.substring(charIndexRef.current-3, charIndexRef.current).includes('```'));
    
    // 设置下一个打字超时
    timeoutRef.current = window.setTimeout(() => {
      // 更新要显示的内容
      const newDisplayContent = currentContent.substring(0, nextCharIndex);
      setDisplayedContent(newDisplayContent);
      charIndexRef.current = nextCharIndex;
    }, isCodeBlock ? adjustedSpeed / 2 : adjustedSpeed);
    
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [isTyping, typingSpeed]);

  // 将Markdown转换为HTML
  useEffect(() => {
    if (!displayedContent) {
      setHtmlContent('');
      return;
    }
    
    const renderMarkdown = async () => {
      try {
        const rendered = await marked.parse(displayedContent);
        setHtmlContent(rendered as string);
      } catch (error) {
        console.error(`渲染Markdown错误:`, error);
        setHtmlContent(`<div style="color: red;">渲染错误: ${error}</div>`);
      }
    };
    
    renderMarkdown();
  }, [displayedContent]);

  // 打字机光标样式
  const cursorStyle = `
    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0; }
    }
    .cursor {
      display: inline-block;
      width: 2px;
      height: 16px;
      background-color: #333;
      margin-left: 2px;
      vertical-align: middle;
      animation: blink 1s step-end infinite;
    }
  `;

  // 计算组件key，用于强制更新
  const computedKey = `mr-${instanceId}-${forceUpdateRef.current}-${forceKey || ''}`;

  return (
    <div className={`message-content ${isTyping ? 'typing-active' : ''}`} key={computedKey} data-instance={instanceId}>
      <style>{cursorStyle}</style>
      
      {/* 调试指示器，仅在本地环境显示 */}
      {(window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && (
        <div className="debug-indicator" style={{ 
          fontSize: '10px',
          padding: '2px 5px',
          margin: '0 0 5px 0', 
          color: '#666',
          backgroundColor: isTyping ? '#e6f7ff' : (typingComplete ? '#f6ffed' : '#fff7e6'),
          border: `1px solid ${isTyping ? '#91d5ff' : (typingComplete ? '#b7eb8f' : '#ffe58f')}`,
          borderRadius: '3px',
          display: 'inline-block'
        }}>
          {isTyping ? '⌨️ 打字中...' : (typingComplete ? '✓ 完成' : '⏸ 准备')} 
          <span style={{ marginLeft: '5px', fontSize: '9px' }}>
            {displayedContent.length}/{contentRef.current.length || 0}字符
          </span>
        </div>
      )}
      
      {/* Markdown内容 */}
      <div
        className="markdown-body prose prose-sm max-w-none"
        dangerouslySetInnerHTML={{ __html: htmlContent }}
      />
      
      {/* 打字指示器 */}
      {isTyping && !typingComplete && (
        <div className="typing-indicator-container" style={{ display: 'flex', marginTop: '8px' }}>
          <div className="typing-indicator" style={{ display: 'flex', gap: '5px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#606266',
                animation: 'typing 1s infinite',
                display: 'inline-block',
              }}
            />
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#606266',
                animation: 'typing 1s infinite',
                animationDelay: '0.2s',
                display: 'inline-block',
              }}
            />
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#606266',
                animation: 'typing 1s infinite',
                animationDelay: '0.4s',
                display: 'inline-block',
              }}
            />
            <style>{`
              @keyframes typing {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-5px); }
              }
              .typing-active {
                border-left: 3px solid #1890ff;
                padding-left: 5px;
              }
            `}</style>
          </div>
        </div>
      )}
      
      {/* 完成状态的光标 */}
      {typingComplete && (
        <span className="cursor" style={{ display: 'inline-block' }}></span>
      )}
    </div>
  );
};

export default MessageRenderer; 