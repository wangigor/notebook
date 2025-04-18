import { BlockType, ContentBlock, DocumentReference, generateBlockId } from '../types/content';

// 为不同块类型准备内容显示格式
function prepareContentForDisplay(content: string, blockType: BlockType): string {
  switch (blockType) {
    case 'thinking':
      // 为思考过程添加明确的标题，但不再添加引用格式
      return `## 思考过程\n\n${content}`;
    case 'analyzing':
      // 为分析内容添加明确的标题和内容分隔
      return `## 分析过程\n\n${content}`;
    case 'document':
      // 文档引用格式
      return content;
    case 'answer':
      // 答案内容保持原样
      return content;
    case 'response':
      // 回复内容保持原样
      return content;
    default:
      return content;
  }
}

// 块类型映射函数
function mapToBlockType(marker: string): BlockType {
  if (/思考过程|AI思考/.test(marker)) return 'thinking';
  if (/分析|AI分析中|AI分析/.test(marker)) return 'analyzing';
  if (/回答|答案/.test(marker)) return 'answer';
  if (/回复|Response/.test(marker)) return 'response';
  if (/文档|引用|参考资料/.test(marker)) return 'document';
  return 'raw';
}

// 创建内容块函数
function createContentBlock(type: BlockType, rawContent: string): ContentBlock {
  const formattedContent = prepareContentForDisplay(rawContent, type);
  
  // 根据不同类型设置默认值，现在默认所有类型都启用打字效果
  const isTypingEnabled = true; // 所有块都启用打字效果
  
  // 为不同类型设置不同的打字速度
  let typingSpeed = 10; // 默认速度
  if (type === 'thinking') typingSpeed = 15; // 思考过程快一些
  else if (type === 'analyzing') typingSpeed = 12; // 分析过程中等
  else if (type === 'answer') typingSpeed = 5; // 答案内容慢一些
  
  // 默认不折叠
  const defaultCollapsed = false;
  
  return {
    id: generateBlockId(),
    type,
    content: formattedContent,
    renderOptions: { 
      typing: isTypingEnabled,
      speed: typingSpeed,
      collapsed: defaultCollapsed
    }
  };
}

// 创建简单的原始内容块
function createRawBlock(content: string): ContentBlock {
  return {
    id: generateBlockId(),
    type: 'raw',
    content, // 直接使用原始内容，不做任何处理
    renderOptions: { 
      typing: false, 
      speed: 5 
    }
  };
}

// 创建文档块函数
function createDocumentBlock(name: string, content: string, url?: string): ContentBlock {
  const docRef: DocumentReference = {
    name,
    content,
    url
  };
  
  // 使用类型断言
  const block = {
    id: generateBlockId(),
    type: 'document' as BlockType,
    content: `引用文档: ${name}\n${content}`,
    document: docRef,
    renderOptions: {
      typing: false,
      collapsed: true
    }
  };
  
  return block as ContentBlock;
}

/**
 * 检查是否开启了调试模式
 */
export const isDebugMode = (): boolean => {
  return localStorage.getItem('debugContentParser') === 'true';
};

/**
 * 调试日志输出
 */
export const debugLog = (...args: any[]): void => {
  if (isDebugMode()) {
    console.log('[ContentParser]', ...args);
  }
};

/**
 * 格式化消息内容
 * @param content 原始消息内容
 * @returns 格式化后的内容块数组
 */
export const parseMessageContent = (content: string): ContentBlock[] => {
  if (!content) return [];
  
  const debugMode = isDebugMode();
  debugLog('开始解析消息内容:', content);
  
  try {
    const contentBlocks: ContentBlock[] = [];
    
    // 严格匹配后端定义的块标记格式，不尝试智能化处理
    const blockPattern = /【(思考过程|AI分析中|AI思考|AI分析|分析中|回答|答案|回复|Response|文档|引用|参考资料)】\s*([\s\S]*?)(?=(?:【)|$)/g;
    
    if (debugMode) console.log('使用正则表达式:', blockPattern.source);
    
    // 保持原始块标记匹配
    const matches = Array.from(content.matchAll(blockPattern));
    
    if (debugMode) console.log('找到匹配数量:', matches.length);
    
    if (matches.length === 0) {
      // 如果没有匹配任何块，将整个内容作为原始内容处理
      // 不尝试智能判断内容类型
      return [createRawBlock(content)];
    }
    
    // 处理匹配到的块
    for (const match of matches) {
      const marker = match[1];
      const blockContent = match[2];
      const blockType = mapToBlockType(marker);
      contentBlocks.push(createContentBlock(blockType, blockContent));
    }
    
    return contentBlocks;
  } catch (error) {
    console.error('解析消息内容时出错:', error);
    // 出错时返回原始内容
    return [createRawBlock(content)];
  }
};

/**
 * 格式化消息内容为内容块数组
 * @param content 原始消息内容
 * @returns 格式化后的内容块数组
 */
export const formatMessageContent = (content: string): ContentBlock[] => {
  // 如果内容解析失败，确保返回原始内容
  const contentBlocks = parseMessageContent(content);
  
  if (contentBlocks.length === 0) {
    // 如果没有内容块，则创建一个原始内容块
    return [createRawBlock(content)];
  }

  return contentBlocks;
}; 