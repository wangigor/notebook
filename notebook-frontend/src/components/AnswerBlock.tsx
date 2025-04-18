import React, { useState } from 'react';
import { IconComment, IconCopy } from '@douyinfe/semi-icons';
import { Typography, Button, Toast } from '@douyinfe/semi-ui';
import { renderMarkdown } from '../utils/markdownRenderer';
import './BlockStyles.css';

interface AnswerBlockProps {
  content: string;
  forceKey?: string;
  defaultCollapsed?: boolean;
}

const AnswerBlock: React.FC<AnswerBlockProps> = ({ 
  content, 
  forceKey,
  defaultCollapsed = false // 回答块默认始终展开
}) => {
  // 回答块默认展开且不自动折叠
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
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
    processed = processed.replace(/^【回答】|^\[回答\]|^回答:|^【答案】|^\[答案\]|^答案:/i, '').trim();
    
    // 移除 "## 回答" 或类似的标题行
    processed = processed.replace(/^## (回答|答案)\s*\n+/i, '').trim();
    
    return processed;
  };
  
  // 渲染Markdown内容
  const htmlContent = renderMarkdown(processContent(content));
  
  return (
    <div className="answer-block block-container">
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
      
      {!collapsed && (
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

export default AnswerBlock; 