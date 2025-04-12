import { FC, useEffect, useRef } from 'react';
import { Empty, Spin, Avatar, Typography } from '@douyinfe/semi-ui';
import { IconUser, IconComment } from '@douyinfe/semi-icons';
import { Message } from '../types';
import MessageRenderer from './MessageRenderer';

interface MessageListProps {
  messages: Message[];
  loading?: boolean;
}

const MessageList: FC<MessageListProps> = ({ messages, loading = false }) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 当消息更新时自动滚动到底部
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // 如果没有消息，显示引导用户开始对话的提示
  if (messages.length === 0 && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8">
        <Empty
          image={<IconComment size="large" />}
          title="没有消息"
          description="开始新的对话，探索知识库"
        />
      </div>
    );
  }

  return (
    <div 
      className="messages-container p-4 flex flex-col gap-4"
      style={{ 
        flex: '1 1 auto', 
        height: '100%',
        overflowY: 'auto',
        paddingBottom: '16px'
      }}
    >
      {messages.map((message) => (
        <div
          key={message.id}
          className={`message-row flex ${
            message.role === 'user' ? 'justify-end' : 'justify-start'
          }`}
        >
          <div
            className={`message-bubble ${message.role} max-w-3/4 ${
              message.role === 'user' ? 'ml-auto' : 'mr-auto'
            } flex gap-3`}
          >
            <Avatar
              size="small"
              color={message.role === 'user' ? 'light-blue' : 'grey'}
              icon={message.role === 'user' ? <IconUser /> : <IconComment />}
            />
            <div>
              {message.role === 'assistant' ? (
                <MessageRenderer 
                  content={message.content} 
                  typing={true}
                  typingSpeed={5}
                />
              ) : (
                <Typography.Text>{message.content}</Typography.Text>
              )}
              
              {message.timestamp && (
                <Typography.Text type="tertiary" size="small" className="mt-1 block">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </Typography.Text>
              )}
            </div>
          </div>
        </div>
      ))}

      {/* 加载指示器 */}
      {loading && (
        <div className="flex justify-center p-4">
          <Spin size="small" />
        </div>
      )}
      
      {/* 用于自动滚动的标记 */}
      <div ref={messagesEndRef} />
    </div>
  );
};

export default MessageList; 