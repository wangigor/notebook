import { FC, useState, KeyboardEvent, useRef } from 'react';
import { Button, TextArea } from '@douyinfe/semi-ui';
import { IconSend } from '@douyinfe/semi-icons';

interface QueryInputProps {
  onSubmit: (query: string) => void;
  loading?: boolean;
  placeholder?: string;
}

const QueryInput: FC<QueryInputProps> = ({
  onSubmit,
  loading = false,
  placeholder = '输入您的问题...'
}) => {
  const [query, setQuery] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    if (query.trim() && !loading) {
      onSubmit(query);
      setQuery('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // 发送消息：Ctrl+Enter 或 Command+Enter
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div 
      className="input-container flex items-center gap-2"
      style={{
        padding: '16px 24px',
        borderTop: '1px solid var(--border-color)',
        backgroundColor: 'var(--card-bg)',
        position: 'relative',
        bottom: 0,
        width: '100%'
      }}
    >
      <TextArea
        autosize={{ minRows: 2, maxRows: 6 }}
        value={query}
        onChange={setQuery}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="flex-grow"
        disabled={loading}
        style={{
          fontSize: '15px',
          padding: '12px',
          minHeight: '60px',
          borderRadius: '8px',
          resize: 'none'
        }}
      />
      <Button
        icon={<IconSend />}
        type="primary"
        theme="solid"
        onClick={handleSubmit}
        loading={loading}
        disabled={loading || !query.trim()}
        style={{
          height: '50px',
          width: '90px',
          borderRadius: '8px',
          marginLeft: '8px'
        }}
      >
        发送
      </Button>
    </div>
  );
};

export default QueryInput; 