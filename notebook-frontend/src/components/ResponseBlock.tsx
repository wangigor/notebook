import React, { useState, useEffect } from 'react';
import { IconComment, IconCopy } from '@douyinfe/semi-icons';
import { Typography, Button, Toast } from '@douyinfe/semi-ui';
import { renderMarkdown } from '../utils/markdownRenderer';
import './BlockStyles.css';

interface ResponseBlockProps {
  content: string;
  forceKey?: string;
  defaultCollapsed?: boolean;
  autoCollapseDelay?: number; // 自动折叠延迟时间（毫秒）
}

const ResponseBlock: React.FC<ResponseBlockProps> = ({ 
  content, 
  forceKey,
  defaultCollapsed = false,
  autoCollapseDelay = 1000 // 默认1秒后自动折叠
}) => {
  const [collapsed, setCollapsed] = useState(false); // 初始状态总是展开
  const [isRendering, setIsRendering] = useState(true); // 渲染中状态
  const toggleCollapsed = () => setCollapsed(!collapsed);
  
  const copyToClipboard = (e: React.MouseEvent) => {
    e.stopPropagation(); // 防止触发折叠/展开
    navigator.clipboard.writeText(content).then(() => {
      Toast.success('已复制到剪贴板');
    }).catch(() => {
      Toast.error('复制失败');
    });
  };
  
  // 处理内容，移除标题部分
  const processContent = (rawContent: string) => {
    // 移除标记和标题
    let processed = rawContent;
    
    // 移除可能的标记
    processed = processed.replace(/^【回复】|^\[回复\]|^回复:|^【Response】|^\[Response\]|^Response:/i, '').trim();
    
    // 移除 "## 回复" 或类似的标题行
    processed = processed.replace(/^## (回复|Response)\s*\n+/i, '').trim();
    
    return processed;
  };
  
  // 渲染Markdown内容
  const htmlContent = renderMarkdown(processContent(content));
  
  // 在渲染完成后延迟一段时间自动折叠
  useEffect(() => {
    // 设置一个渲染状态标志
    setIsRendering(true);
    
    // 延迟一段时间后更新渲染状态
    const renderTimer = setTimeout(() => {
      setIsRendering(false);
    }, 500); // 假设内容在500ms内渲染完成
    
    // 在渲染完成后延迟指定时间自动折叠
    const collapseTimer = setTimeout(() => {
      if (!defaultCollapsed) { // 只有在不是默认折叠的情况下才自动折叠
        setCollapsed(true);
      }
    }, autoCollapseDelay + 500); // 渲染完成后再延迟指定时间
    
    return () => {
      clearTimeout(renderTimer);
      clearTimeout(collapseTimer);
    };
  }, [content, autoCollapseDelay, defaultCollapsed]);
  
  return (
    <div className="response-block block-container">
      <div 
        className="block-header-compact"
        onClick={toggleCollapsed}
      >
        <div className="block-title">
          <IconComment className="block-icon" />
        </div>
        <div className="block-actions">
          <Button 
            type="tertiary"
            icon={<IconCopy />}
            size="small"
            onClick={copyToClipboard}
          />
        </div>
      </div>
      
      {(!collapsed || isRendering) && (
        <div className="block-content">
          <div 
            className="markdown-content" 
            dangerouslySetInnerHTML={{ __html: htmlContent }}
          />
        </div>
      )}
    </div>
  );
};

export default ResponseBlock; 