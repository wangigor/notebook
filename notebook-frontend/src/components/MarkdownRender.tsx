import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Typography, Space } from '@douyinfe/semi-ui';

interface MarkdownRenderProps {
  content: string;
  className?: string;
}

const { Text, Title, Paragraph } = Typography;

const MarkdownRender: React.FC<MarkdownRenderProps> = ({ content, className }) => {
  return (
    <div className={`markdown-render ${className || ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          h1: ({ node, ...props }) => <Title heading={1} style={{ margin: '24px 0 16px' }} {...props} />,
          h2: ({ node, ...props }) => <Title heading={2} style={{ margin: '24px 0 16px' }} {...props} />,
          h3: ({ node, ...props }) => <Title heading={3} style={{ margin: '20px 0 12px' }} {...props} />,
          h4: ({ node, ...props }) => <Title heading={4} style={{ margin: '16px 0 8px' }} {...props} />,
          h5: ({ node, ...props }) => <Title heading={5} style={{ margin: '12px 0 8px' }} {...props} />,
          h6: ({ node, ...props }) => <Title heading={6} style={{ margin: '12px 0 8px' }} {...props} />,
          p: ({ node, ...props }) => <Paragraph spacing="extended" {...props} />,
          a: ({ node, ...props }) => <a style={{ color: 'var(--semi-color-primary)' }} target="_blank" rel="noopener noreferrer" {...props} />,
          strong: ({ node, ...props }) => <Text strong {...props} />,
          em: ({ node, ...props }) => <Text type="tertiary" italic {...props} />,
          del: ({ node, ...props }) => <Text delete {...props} />,
          hr: () => <div style={{ margin: '16px 0', borderBottom: '1px solid var(--semi-color-border)' }} />,
          blockquote: ({ node, ...props }) => (
            <div style={{ 
              borderLeft: '4px solid var(--semi-color-primary)', 
              paddingLeft: 16, 
              margin: '16px 0',
              color: 'var(--semi-color-text-2)'
            }} {...props} />
          ),
          ul: ({ node, ...props }) => <ul style={{ margin: '8px 0', paddingLeft: 20 }} {...props} />,
          ol: ({ node, ...props }) => <ol style={{ margin: '8px 0', paddingLeft: 20 }} {...props} />,
          li: ({ node, ...props }) => <li style={{ margin: '4px 0' }} {...props} />,
          table: ({ node, ...props }) => (
            <div style={{ overflowX: 'auto', margin: '16px 0' }}>
              <table style={{ 
                width: '100%', 
                borderCollapse: 'collapse',
                border: '1px solid var(--semi-color-border)'
              }} {...props} />
            </div>
          ),
          thead: ({ node, ...props }) => <thead style={{ backgroundColor: 'var(--semi-color-fill-0)' }} {...props} />,
          tbody: ({ node, ...props }) => <tbody {...props} />,
          tr: ({ node, ...props }) => <tr style={{ borderBottom: '1px solid var(--semi-color-border)' }} {...props} />,
          th: ({ node, ...props }) => (
            <th style={{ 
              padding: '8px 16px', 
              textAlign: 'left', 
              borderRight: '1px solid var(--semi-color-border)'
            }} {...props} />
          ),
          td: ({ node, ...props }) => (
            <td style={{ 
              padding: '8px 16px', 
              textAlign: 'left', 
              borderRight: '1px solid var(--semi-color-border)'
            }} {...props} />
          ),
          code: ({ node, inline, className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || '');
            return !inline && match ? (
              <SyntaxHighlighter
                style={vscDarkPlus}
                language={match[1]}
                PreTag="div"
                customStyle={{
                  margin: '16px 0',
                  borderRadius: '4px',
                  fontSize: '14px',
                }}
                {...props}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code
                className={className}
                style={{
                  padding: '2px 4px',
                  borderRadius: '3px',
                  backgroundColor: 'var(--semi-color-fill-1)',
                  fontSize: '85%',
                  fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace',
                }}
                {...props}
              >
                {children}
              </code>
            );
          },
          img: ({ node, ...props }) => (
            <img style={{ maxWidth: '100%', margin: '16px 0' }} {...props} alt={props.alt || '图片'} />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRender; 