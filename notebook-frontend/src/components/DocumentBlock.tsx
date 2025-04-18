import React, { useState } from 'react';
import { IconFile, IconChevronDown, IconChevronUp, IconLink } from '@douyinfe/semi-icons';
import { Typography, Button, Card } from '@douyinfe/semi-ui';
import { DocumentReference } from '../types/content';
import { renderMarkdown } from '../utils/markdownRenderer';
import './BlockStyles.css';

interface DocumentBlockProps {
  document: DocumentReference;
  forceKey?: string;
  defaultCollapsed?: boolean;
}

const DocumentBlock: React.FC<DocumentBlockProps> = ({ 
  document, 
  forceKey,
  defaultCollapsed = true
}) => {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const toggleCollapsed = () => setCollapsed(!collapsed);
  
  // 渲染Markdown内容
  const htmlContent = renderMarkdown(document.content);
  
  return (
    <div className="document-block block-container">
      <div 
        className="block-header"
        onClick={toggleCollapsed}
      >
        <div className="block-title">
          <IconFile className="block-icon" />
          <Typography.Text strong>引用文档: {document.name}</Typography.Text>
        </div>
        <Button 
          type="tertiary" 
          icon={collapsed ? <IconChevronDown /> : <IconChevronUp />} 
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            toggleCollapsed();
          }}
        />
      </div>
      
      {!collapsed && (
        <div className="block-content">
          <Card>
            <div 
              className="document-content"
              dangerouslySetInnerHTML={{ __html: htmlContent }}
            />
            {document.url && (
              <div className="document-link">
                <Button 
                  icon={<IconLink />} 
                  theme="borderless" 
                  size="small"
                  onClick={() => window.open(document.url, '_blank')}
                >
                  查看原文
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};

export default DocumentBlock; 