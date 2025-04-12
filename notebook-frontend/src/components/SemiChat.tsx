import React, { useEffect, useRef, useState } from 'react';
import { Chat as SemiChat, Button, Toast, Spin, Typography, Card, MarkdownRender } from '@douyinfe/semi-ui';
import { IconPlus, IconChevronDown, IconChevronUp } from '@douyinfe/semi-icons';
import { Message, ChatSession } from '../types';
import { chat, agent } from '../api/api';
import { v4 as uuidv4 } from 'uuid';
import 'highlight.js/styles/github.css';

// 转换Message类型为Semi Chat所需的格式
interface SemiMessage {
  role: string;
  id: string;
  content: string;
  createAt: number;
  status?: 'loading' | 'error' | 'complete';
  attachment?: any[];
  renderContent?: React.ReactNode;
  sequence?: number; // 添加序列号字段
}

interface SemiChatProps {
  currentSession: ChatSession | null;
  onCreateSession: () => Promise<ChatSession>;
}

// 思考过程组件
const ThinkingBlock = ({ content }: { content: string }) => {
  const [expanded, setExpanded] = useState(true);
  
  return (
    <Card
      style={{ 
        marginBottom: '12px',
        borderRadius: '8px',
        backgroundColor: 'rgba(216, 236, 255, 0.4)',
        borderColor: 'rgba(91, 155, 213, 0.3)'
      }}
      headerStyle={{ 
        backgroundColor: 'rgba(216, 236, 255, 0.8)',
        padding: '8px 16px',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}
      bodyStyle={{ 
        padding: expanded ? '16px' : '0',
        height: expanded ? 'auto' : '0',
        overflow: 'hidden',
        transition: 'height 0.3s ease-in-out'
      }}
      header={
        <div 
          style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          onClick={() => setExpanded(!expanded)}
        >
          <Typography.Title heading={6} style={{ margin: 0 }}>AI思考过程</Typography.Title>
          {expanded ? <IconChevronUp /> : <IconChevronDown />}
        </div>
      }
    >
      <MarkdownRender format="md" raw={content} />
    </Card>
  );
};

// 回答组件
const AnswerBlock = ({ content }: { content: string }) => {
  return (
    <div style={{ marginTop: '12px' }}>
      <Typography.Title heading={6} style={{ margin: '0 0 8px 0' }}>回答</Typography.Title>
      <MarkdownRender format="md" raw={content} />
    </div>
  );
};

// 分析中组件
const AnalyzingBlock = ({ content }: { content: string }) => {
  return (
    <Card
      style={{ 
        marginBottom: '12px',
        borderRadius: '8px',
        backgroundColor: 'rgba(255, 245, 224, 0.4)',
        borderColor: 'rgba(255, 192, 0, 0.3)'
      }}
      headerStyle={{ 
        backgroundColor: 'rgba(255, 245, 224, 0.8)',
        padding: '8px 16px',
      }}
      bodyStyle={{ padding: '16px' }}
      header={<Typography.Title heading={6} style={{ margin: 0 }}>分析中</Typography.Title>}
    >
      <MarkdownRender format="md" raw={content} />
    </Card>
  );
};

// 格式化消息内容，处理思考过程和回答的格式
const formatMessageContent = (content: string): React.ReactNode => {
  if (!content.includes('【思考过程】') && !content.includes('【回答】')) {
    return <MarkdownRender format="md" raw={content} />;
  }

  const parts = [];
  let currentPart = '';
  let currentType = '';
  
  // 查找思考过程和回答部分
  const lines = content.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    if (line.includes('【思考过程】')) {
      if (currentPart && currentType) {
        parts.push({ type: currentType, content: currentPart });
      }
      currentType = 'thinking';
      currentPart = line.replace('【思考过程】', '') + '\n';
    } else if (line.includes('【回答】')) {
      if (currentPart && currentType) {
        parts.push({ type: currentType, content: currentPart });
      }
      currentType = 'answer';
      currentPart = line.replace('【回答】', '') + '\n';
    } else if (line.includes('【AI分析中】')) {
      if (currentPart && currentType) {
        parts.push({ type: currentType, content: currentPart });
      }
      currentType = 'analyzing';
      currentPart = line.replace('【AI分析中】', '') + '\n';
    } else {
      currentPart += line + '\n';
    }
  }
  
  if (currentPart && currentType) {
    parts.push({ type: currentType, content: currentPart });
  }
  
  // 如果没有找到特定标记，返回原始内容
  if (parts.length === 0) {
    return <MarkdownRender format="md" raw={content} />;
  }
  
  // 渲染不同样式的部分
  return (
    <div>
      {parts.map((part, index) => {
        if (part.type === 'thinking') {
          return <ThinkingBlock key={index} content={part.content} />;
        } else if (part.type === 'analyzing') {
          return <AnalyzingBlock key={index} content={part.content} />;
        } else if (part.type === 'answer') {
          return <AnswerBlock key={index} content={part.content} />;
        } else {
          return <MarkdownRender format="md" raw={part.content} key={index} />;
        }
      })}
    </div>
  );
};

const SemiChatComponent: React.FC<SemiChatProps> = ({ currentSession, onCreateSession }) => {
  const [messages, setMessages] = useState<SemiMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const chatRef = useRef<any>(null);
  const messageSequenceRef = useRef(0); // 用于生成消息序列号

  // 配置角色信息
  const roleConfig = {
    user: {
      name: '用户',
      avatar: 'https://lf3-static.bytednsdoc.com/obj/eden-cn/ptlz_zlp/ljhwZthlaukjlkulzlp/docs-icon.png'
    },
    assistant: {
      name: 'AI助手',
      avatar: 'https://lf3-static.bytednsdoc.com/obj/eden-cn/ptlz_zlp/ljhwZthlaukjlkulzlp/other/logo.png'
    },
    system: {
      name: '系统',
      avatar: 'https://lf3-static.bytednsdoc.com/obj/eden-cn/ptlz_zlp/ljhwZthlaukjlkulzlp/other/logo.png'
    }
  };

  // 当会话改变时，加载消息
  useEffect(() => {
    if (currentSession) {
      loadSessionMessages(currentSession.id);
    } else {
      setMessages([]);
    }
  }, [currentSession]);

  // 加载会话消息
  const loadSessionMessages = async (sessionId: string) => {
    try {
      setLoading(true);
      // 确保会话ID格式正确
      const formattedSessionId = sessionId.startsWith('session_') ? sessionId : `session_${sessionId}`;
      // 使用会话ID查询消息
      const response = await chat.getMessages(formattedSessionId);
      
      if (response.success) {
        // 转换消息格式为Semi Chat格式
        const semiMessages = response.data.map(msg => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          createAt: new Date(msg.timestamp || Date.now()).getTime(),
          status: 'complete' as const,
          renderContent: msg.role === 'assistant' ? formatMessageContent(msg.content) : undefined,
          sequence: messageSequenceRef.current++
        }));
        setMessages(semiMessages);
        setTimeout(() => {
          chatRef.current?.scrollToBottom(true);
        }, 100);
      } else {
        Toast.error('加载消息失败：' + response.message);
      }
    } catch (error: any) {
      console.error('Failed to load messages:', error);
      Toast.error('加载消息失败：' + (error.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  };

  // 发送消息
  const handleSendMessage = async (content: string, attachment?: any[]) => {
    // 如果没有当前会话，创建一个新会话
    let sessionId = currentSession?.id;
    if (!sessionId) {
      try {
        const newSession = await onCreateSession();
        sessionId = newSession.id;
      } catch (error) {
        Toast.error('创建会话失败，请重试');
        return;
      }
    }

    // 创建用户消息
    const userMessage: SemiMessage = {
      id: uuidv4(),
      role: 'user',
      content,
      createAt: Date.now(),
      sequence: messageSequenceRef.current++,
    };

    // 添加用户消息到UI
    setMessages(prev => [...prev, userMessage].sort((a, b) => (a.sequence || 0) - (b.sequence || 0)));

    try {
      // 保存用户消息到服务器
      await chat.sendMessage(sessionId!, content);

      // 添加AI消息加载状态
      const tempAssistantMessageId = uuidv4();
      const tempAssistantMessage: SemiMessage = {
        id: tempAssistantMessageId,
        role: 'assistant',
        content: '',
        createAt: Date.now(),
        status: 'loading',
        sequence: messageSequenceRef.current++,
      };

      setMessages(prev => [...prev, tempAssistantMessage].sort((a, b) => (a.sequence || 0) - (b.sequence || 0)));

      // 使用agent.query处理流式响应
      let responseContent = '';
      const handleChunk = (chunk: string) => {
        // 记录数据更新前的滚动位置
        const scrollContainer = chatRef.current?.scrollContainer;
        const isScrolledToBottom = scrollContainer ? 
          Math.abs((scrollContainer.scrollHeight - scrollContainer.scrollTop) - scrollContainer.clientHeight) < 10 : true;
          
        responseContent += chunk;
        
        // 确保当前内容始终有正确的分隔标记
        let formattedContent = responseContent;
        // 如果还没有出现【回答】标记，但内容已经不再包含AI分析中，则添加一个隐式的回答标记
        if (!formattedContent.includes('【回答】') && 
            !formattedContent.includes('【AI分析中】') &&
            formattedContent.trim().length > 0) {
          formattedContent = '【回答】\n' + formattedContent;
        }
        
        // 立即更新状态，确保实时渲染
        setMessages(prev => {
          const updatedMessages = [...prev];
          const tempIndex = updatedMessages.findIndex(msg => msg.id === tempAssistantMessageId);
          
          if (tempIndex !== -1) {
            // 确保应用renderContent以保持Markdown格式
            updatedMessages[tempIndex] = {
              ...updatedMessages[tempIndex],
              content: formattedContent,
              renderContent: formatMessageContent(formattedContent)
            };
          }
          
          return updatedMessages;
        });
        
        // 如果之前滚动条在底部，则继续保持在底部
        if (isScrolledToBottom) {
          setTimeout(() => {
            chatRef.current?.scrollToBottom(false);
          }, 0);
        }
      };

      try {
        // 使用API封装的方法发送请求，而不是直接使用EventSource
        await agent.query(content, sessionId, handleChunk);
        
        // 完成后更新状态
        setMessages(prev => {
          const updatedMessages = [...prev];
          const tempIndex = updatedMessages.findIndex(msg => msg.id === tempAssistantMessageId);
          
          if (tempIndex !== -1) {
            updatedMessages[tempIndex] = {
              ...updatedMessages[tempIndex],
              status: 'complete',
            };
          }
          
          return updatedMessages.sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
        });
      } catch (error: any) {
        console.error('处理流式消息出错:', error);
        Toast.error('处理流式消息时发生错误');
        
        // 添加错误消息到对话
        setMessages(prev => {
          const filteredMessages = prev.filter(msg => msg.id !== tempAssistantMessageId);
          return [
            ...filteredMessages,
            {
              id: uuidv4(),
              role: 'assistant',
              content: `处理您的查询时发生错误: ${error.message || '未知错误'}`,
              createAt: Date.now(),
              status: 'error' as const,
              sequence: messageSequenceRef.current++,
            }
          ].sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
        });
      }
    } catch (error: any) {
      console.error('Failed to process query:', error);
      
      // 添加错误消息到对话
      setMessages(prev => {
        const filteredMessages = prev.filter(msg => msg.role !== 'assistant' || msg.content !== '' || msg.status !== 'loading');
        return [
          ...filteredMessages,
          {
            id: uuidv4(),
            role: 'assistant',
            content: `处理您的查询时发生错误: ${error.message || '未知错误'}`,
            createAt: Date.now(),
            status: 'error' as const,
            sequence: messageSequenceRef.current++,
          }
        ].sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
      });
      
      const errorMessage = error.message || '未知错误';
      Toast.error(`处理查询失败：${errorMessage}`);
    }
  };

  // 清除上下文
  const handleClearContext = () => {
    setMessages([]);
    Toast.info('已清除所有对话记录');
  };

  // 自定义渲染消息内容
  const renderMessageContent = (item: SemiMessage) => {
    if (item.renderContent) {
      return item.renderContent;
    }
    return item.content;
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {loading && messages.length === 0 ? (
        <div className="flex justify-center items-center h-full">
          <Spin size="large" />
        </div>
      ) : (
        <SemiChat
          ref={chatRef}
          style={{ 
            height: '100%',
            border: '1px solid var(--semi-color-border)',
            borderRadius: '8px'
          }}
          chats={messages}
          roleConfig={roleConfig}
          onMessageSend={handleSendMessage}
          showClearContext={true}
          onClearContext={handleClearContext}
          placeholder="输入您的问题..."
          mode="bubble"
          align="leftRight"
          renderMessageContent={renderMessageContent}
          bottomSlot={
            !currentSession ? (
              <div style={{ padding: '12px', textAlign: 'center' }}>
                <Button icon={<IconPlus />} theme="light" onClick={() => onCreateSession()}>
                  新建会话
                </Button>
              </div>
            ) : null
          }
        />
      )}
    </div>
  );
};

export default SemiChatComponent; 