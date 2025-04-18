import React, { useEffect, useRef, useState } from 'react';
import { Chat as SemiChat, Button, Toast, Spin, Typography, Card, List, Avatar, Input, Empty } from '@douyinfe/semi-ui';
import { IconPlus, IconChevronDown, IconChevronUp, IconUser } from '@douyinfe/semi-icons';
import { Message, ChatSession } from '../types';
import { chat, agent } from '../api/api';
import { v4 as uuidv4 } from 'uuid';
import 'highlight.js/styles/github.css';
import { marked } from 'marked';
import MessageRenderer from './MessageRenderer';
import AnalyzingBlock from './AnalyzingBlock';
import AnswerBlock from './AnswerBlock';
import ThinkingBlock from './ThinkingBlock';
import ResponseBlock from './ResponseBlock';
import { parseMessageContent } from '../utils/contentParser';

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

// 根据消息类型渲染消息内容
const renderMessageContent = (message: SemiMessage) => {
  console.log('[renderMessageContent] 渲染消息:', message.role);
  if (message.role === 'system') {
    return <div className="text-gray-400 italic">系统提示: {message.content}</div>;
  } else if (message.role === 'user') {
    return <div className="whitespace-pre-wrap">{message.content}</div>;
  } else if (message.role === 'assistant') {
    console.log('[renderMessageContent] 渲染助手消息，调用formatMessageContent');
    return formatMessageContent(message.content);
  } else {
    console.warn('[renderMessageContent] 未知角色:', message.role);
    return <div className="text-red-500 italic">未知消息类型</div>;
  }
};

// Markdown渲染组件（本地实现）
const MarkdownRender = ({ format, raw }: { format: 'md' | 'mdx'; raw: string }) => {
  const [html, setHtml] = useState('');
  
  useEffect(() => {
    if (!raw) return;
    console.log(`[MarkdownRender] 渲染${format}内容: ${raw.substring(0, 30)}...`);
    
    // 延迟渲染以避免阻塞UI
    const renderMd = async () => {
      try {
        // 使用marked库进行Markdown到HTML的转换
        const renderedHtml = await marked.parse(raw);
        setHtml(renderedHtml as string);
      } catch (error) {
        console.error('[MarkdownRender] 渲染错误:', error);
        setHtml(`<div class="text-red-500">渲染错误: ${error}</div>`);
      }
    };
    
    renderMd();
  }, [raw, format]);
  
  return (
    <div 
      className="markdown-body prose prose-sm max-w-none" 
      dangerouslySetInnerHTML={{ __html: html }} 
    />
  );
};

// 格式化消息内容，成为处理 assistant 消息渲染的唯一入口
const formatMessageContent = (content: string, externalKey?: string): React.ReactNode => {
  // 开启调试模式 - 可以通过浏览器控制台查看解析过程
  const debugMode = localStorage.getItem('debugContentParser') === 'true';
  
  if (typeof content !== 'string') {
    console.warn('[formatMessageContent] 接收到非字符串内容');
    return React.isValidElement(content) ? content : '无效内容';
  }

  if (debugMode) {
    console.log('[formatMessageContent] 原始内容:', content.substring(0, 100) + '...');
  }

  // 生成唯一渲染键
  const renderKey = externalKey || `msg-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
  
  // 使用parseMessageContent解析内容获取ContentBlock数组
  const contentBlocks = parseMessageContent(content);
  
  if (debugMode) {
    console.log('[formatMessageContent] 解析后的块:', contentBlocks.map(block => ({
      type: block.type,
      contentLength: block.content.length
    })));
  }
  
  // 如果没有内容块，返回原始内容
  if (contentBlocks.length === 0) {
    return <MessageRenderer 
      key={`raw-${renderKey}`} 
      content={content} 
      useTypingEffect={true} 
      typingSpeed={5} 
      forceKey={renderKey} 
    />;
  }
  
  // 渲染各个内容块
  return (
    <div className="markdown-content" key={`content-${renderKey}`}>
      {/* 调试信息只在控制台显示 */}
      {debugMode && (console.log('[formatMessageContent] 识别到内容块数量:', contentBlocks.length), null)}
      
      {contentBlocks.map((block, index) => {
        // 为每个部分生成唯一键
        const blockKey = `${block.type}-${index}-${renderKey}`;
        const forceKey = `${blockKey}-${Date.now()}`;
        
        if (block.type === 'thinking') {
          return <ThinkingBlock key={blockKey} content={block.content} forceKey={forceKey} />;
        } else if (block.type === 'analyzing') {
          return <AnalyzingBlock key={blockKey} content={block.content} forceKey={forceKey} />;
        } else if (block.type === 'answer') {
          return <AnswerBlock key={blockKey} content={block.content} forceKey={forceKey} />;
        } else if (block.type === 'response') {
          return <ResponseBlock key={blockKey} content={block.content} forceKey={forceKey} />;
        } else if (block.type === 'document') {
          // 简单文档类型渲染
          return <div key={blockKey} className="document-block p-2 border border-blue-200 rounded bg-blue-50 my-2">
            <div className="font-medium text-blue-800">文档引用</div>
            <MessageRenderer
              key={blockKey}
              content={block.content}
              useTypingEffect={false}
              forceKey={forceKey}
            />
          </div>;
        } else { // type === 'raw'
          return <MessageRenderer 
            key={blockKey} 
            content={block.content} 
            useTypingEffect={true} 
            typingSpeed={5} 
            forceKey={forceKey} 
          />;
        }
      })}
    </div>
  );
};

// 添加样式
const styles = {
  markdownContent: {
    fontSize: "14px",
    lineHeight: "1.6",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  }
};

const SemiChatComponent: React.FC<SemiChatProps> = ({ currentSession, onCreateSession }) => {
  const [messages, setMessages] = useState<SemiMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const chatRef = useRef<any>(null);
  const messageSequenceRef = useRef(0);
  const streamingMessageRef = useRef<{ id: string | null, content: string }>({ id: null, content: '' }); // 用于跟踪流式消息状态

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
      const sessionId = currentSession.id;
      console.log('SemiChat: 会话变化，新会话ID:', sessionId);
      setMessages([]); // 清空旧消息
      const loadTimer = setTimeout(() => loadSessionMessages(sessionId), 100);
      return () => clearTimeout(loadTimer);
    } else {
      setMessages([]);
    }
  }, [currentSession?.id]);

  // 加载会话消息
  const loadSessionMessages = async (sessionId: string) => {
    try {
      setLoading(true);
      console.log('SemiChat: 开始加载会话消息, 会话ID:', sessionId);
      
      // 使用原始会话ID查询消息，不添加格式化
      const response = await chat.getMessages(sessionId);
      console.log('SemiChat: 获取消息响应:', response);
      
      if (response.success) {
        if (Array.isArray(response.data)) {
          // 检查响应是否为空数组
          if (response.data.length === 0) {
            console.warn(`SemiChat: 会话ID ${sessionId} 未返回任何消息数据`);
          }
          
          // 确保以正确的顺序排序
          const sorted = [...response.data].sort((a, b) => {
            return new Date(a.timestamp || 0).getTime() - new Date(b.timestamp || 0).getTime();
          });
          
          // 转换消息格式为Semi Chat格式
          messageSequenceRef.current = 0; // 重置序列号
          const semiMessages = sorted.map(msg => ({
            id: msg.id || uuidv4(),
            role: msg.role,
            content: msg.content,
            createAt: new Date(msg.timestamp || Date.now()).getTime(),
            status: 'complete' as const,
            sequence: messageSequenceRef.current++
          }));
          
          console.log('SemiChat: 成功加载消息，数量:', semiMessages.length);
          setMessages(semiMessages);
          
          // 滚动到底部
          setTimeout(() => {
            chatRef.current?.scrollToBottom(true);
            console.log('SemiChat: 滚动到底部');
          }, 300);
        } else {
          console.error('SemiChat: API返回的消息格式不正确:', response.data);
          Toast.warning('消息格式不正确');
          setMessages([]);
        }
      } else {
        console.error('SemiChat: 加载消息失败:', response.message);
        
        // 如果是401错误，可能需要重新登录
        if (response.message?.includes('401')) {
          Toast.error(`需要重新登录`);
          // 这里可以添加重定向到登录页面的逻辑
        } else {
          Toast.error(`加载消息失败: ${response.message}`);
        }
      }
    } catch (error: any) {
      console.error('SemiChat: 加载消息异常:', error);
      Toast.error(`加载消息失败: ${error.message || '未知错误'}`);
    } finally {
      setLoading(false);
    }
  };

  // 统一的消息更新函数
  const updateMessage = (
    messageId: string, 
    content: string, 
    status: 'loading' | 'complete' | 'error' = 'complete'
  ): void => {
    // 给每次更新生成唯一标识，便于调试
    const updateId = Math.random().toString(36).substring(2, 6);
    console.log(`[updateMessage:${updateId}] 更新消息 ID: ${messageId}, 状态: ${status}, 内容长度: ${content.length}`);
    
    setMessages(prev => {
      // 查找要更新的消息索引
      const messageIndex = prev.findIndex(msg => msg.id === messageId);
      
      // 如果找不到消息，保持原状态
      if (messageIndex === -1) {
        console.warn(`[updateMessage:${updateId}] 未找到消息 ID: ${messageId}`);
        return prev;
      }
      
      // 使用同样的方式复制和更新消息
      const updatedMessages = [...prev];
      
      // 更新消息
      updatedMessages[messageIndex] = {
        ...updatedMessages[messageIndex],
        content,
        status,
        // 对于complete状态可能需要更新其他属性
        ...(status === 'complete' ? { 
          createAt: Date.now() 
        } : {})
      };
      
      return updatedMessages.sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
    });
    
    // 尝试滚动到底部
    const scrollContainer = chatRef.current?.scrollContainer;
    const isScrolledToBottom = scrollContainer ? 
      Math.abs((scrollContainer.scrollHeight - scrollContainer.scrollTop) - scrollContainer.clientHeight) < 20 : true;
    if (isScrolledToBottom) {
      setTimeout(() => chatRef.current?.scrollToBottom(false), 0);
    }
  };

  // 发送消息
  const handleSendMessage = async (content: string, attachment?: any[]) => {
    let sessionId = currentSession?.id;
    if (!sessionId) {
      try {
        console.log('SemiChat: 创建新会话');
        const newSession = await onCreateSession();
        sessionId = newSession.id;
        console.log('SemiChat: 已创建新会话, ID:', sessionId);
      } catch (error) {
        console.error('SemiChat: 创建会话失败:', error);
        Toast.error('创建会话失败，请重试');
        return;
      }
    }

    // 1. 添加用户消息
    const userMessage: SemiMessage = {
      id: uuidv4(), 
      role: 'user', 
      content, 
      createAt: Date.now(), 
      status: 'complete', // 添加完成状态
      sequence: messageSequenceRef.current++,
    };
    setMessages(prev => [...prev, userMessage].sort((a, b) => (a.sequence || 0) - (b.sequence || 0)));

    // 2. 准备接收流式AI消息
    const tempAssistantMessageId = uuidv4();
    streamingMessageRef.current = { id: tempAssistantMessageId, content: '' };
    
    // 添加临时的AI消息占位符，使用loading状态
    const tempAssistantMessage: SemiMessage = {
      id: tempAssistantMessageId, 
      role: 'assistant', 
      content: '', 
      createAt: Date.now(), 
      status: 'loading',  // 这里保持loading状态
      sequence: messageSequenceRef.current++
    };
    setMessages(prev => [...prev, tempAssistantMessage].sort((a, b) => (a.sequence || 0) - (b.sequence || 0)));

    // 3. 处理流式响应
    const handleChunk = (chunk: string) => {
      if (!streamingMessageRef.current.id) {
        console.error('[handleChunk] 没有有效的streaming消息ID');
        return;
      }
      
      // 确保每个chunk都能正确保留换行和格式
      const safeChunk = typeof chunk === 'string' ? chunk : String(chunk);
      
      // 保留原始格式添加到内容中
      streamingMessageRef.current.content += safeChunk;
      
      // 更新消息，保持原始格式
      updateMessage(streamingMessageRef.current.id, streamingMessageRef.current.content);
    };

    // 4. 监听SSE事件
    try {
      const token = localStorage.getItem('token');
      if (!token) throw new Error("需要登录");
      
      let apiUrl = `/api/agents/query/stream?query=${encodeURIComponent(content)}`;
      if (currentSession?.id) apiUrl += `&session_id=${encodeURIComponent(currentSession.id)}`;
      // 在URL中添加token作为查询参数 (注意安全风险)
      apiUrl += `&token=${encodeURIComponent(token)}`;
        
      const eventSource = new EventSource(apiUrl);
      streamingMessageRef.current.id = tempAssistantMessageId;

      eventSource.onmessage = async (event) => {
        if (streamingMessageRef.current.id === null) { 
          eventSource.close(); 
          console.log('[onmessage] 流已关闭，关闭 EventSource');
          return; 
        }
        
        try {
          console.log(`[onmessage] 收到事件数据: ${event.data.substring(0, 50)}...`);
          const data = JSON.parse(event.data);
          console.log(`[onmessage] 解析事件: type=${data.type}`);
          
          if (data.type === "chunk") {
            // 确保 content 字段存在，即使为空字符串
            const chunkContent = data.content !== undefined ? data.content : "";
            handleChunk(chunkContent);
          } else if (data.type === "complete") {
            eventSource.close();
            // 使用累积的内容，而不是complete中的完整内容
            const finalContent = streamingMessageRef.current.content;
            const finalId = data.message_id || streamingMessageRef.current.id;
            
            console.log(`[onmessage] 完成事件，最终内容长度: ${finalContent.length}`);
            
            // 使用统一的消息更新函数，变更状态为complete强制刷新
            updateMessage(streamingMessageRef.current.id, finalContent);
            
            // 更新完成后再重置引用
            streamingMessageRef.current.id = null;
          } else if (data.type === "error") {
            eventSource.close();
            streamingMessageRef.current.id = null;
            const errorMessage = data.message || "处理查询时发生错误";
            
            console.error(`[onmessage] 错误事件: ${errorMessage}`);
            
            // 使用统一的消息更新函数
            updateMessage(tempAssistantMessageId, `错误: ${errorMessage}`, "error");
            throw new Error(errorMessage);
          }
        } catch (error) {
          eventSource.close();
          streamingMessageRef.current.id = null;
          console.error("[onmessage] 处理SSE消息失败:", error);
          
          // 使用统一的消息更新函数
          updateMessage(
            tempAssistantMessageId, 
            `处理消息时出错: ${error instanceof Error ? error.message : "未知解析错误"}`, 
            "error"
          );
        }
      };

      eventSource.onerror = (error) => {
        if (streamingMessageRef.current.id === null) return; // 忽略已完成流的错误
        eventSource.close();
        streamingMessageRef.current.id = null;
        console.error("EventSource错误:", error);
        
        // 使用统一的消息更新函数，明确指定error状态
        updateMessage(
          tempAssistantMessageId, 
          "与服务器的连接中断，请检查网络或重试", 
          "error"
        );
      };

    } catch (error: any) {
      console.error('发送消息或处理流失败:', error);
      streamingMessageRef.current.id = null; // 确保出错时重置
      
      // 使用统一的消息更新函数
      updateMessage(
        tempAssistantMessageId, 
        `发送消息失败: ${error.message || "未知错误"}`, 
        "error"
      );
    } finally {
      setLoading(false);
    }
  };

  // 清除上下文
  const handleClearContext = () => {
    setMessages([]);
    Toast.info('已清除所有对话记录');
  };

  // 添加一个专门处理渲染内容的回调函数
  const renderChatBoxContent = (props: any) => {
    const { message, className } = props;
    
    // 只为assistant消息应用我们的自定义渲染
    if (message.role === 'assistant') {
      return (
        <div 
          className={className}
          style={{ minHeight: '24px', visibility: 'visible' }}
        >
          {formatMessageContent(message.content)}
        </div>
      );
    }
    
    // 对于其他类型的消息，使用默认渲染
    return (
      <div 
        className={className}
        style={{ minHeight: '24px' }}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    );
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {loading && messages.length === 0 ? (
        <div className="flex justify-center items-center h-full">
          <Spin size="large" />
        </div>
      ) : (
        <>
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
            chatBoxRenderConfig={{
              renderChatBoxContent: renderChatBoxContent
            }}
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
        </>
      )}
      {/* 添加注释说明如何在控制台启用调试模式 */}
      {/* 
        调试说明:
        在浏览器控制台(F12)中执行以下命令启用/禁用调试:
        localStorage.setItem('debugContentParser', 'true'); // 启用调试
        localStorage.setItem('debugContentParser', 'false'); // 禁用调试
        刷新页面后生效
      */}
    </div>
  );
};

export default SemiChatComponent; 