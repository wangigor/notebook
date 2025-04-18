import { marked } from 'marked';

/**
 * 渲染Markdown内容为HTML
 * @param markdown Markdown格式的文本内容
 * @returns 渲染后的HTML字符串
 */
export function renderMarkdown(markdown: string): string {
  try {
    if (!markdown) return '';
    
    // 添加options确保正确处理换行和结构
    return marked.parse(markdown, {
      breaks: true,  // 允许换行
      gfm: true      // 启用GitHub风格Markdown
    }) as string;
  } catch (error) {
    console.error('Markdown渲染错误:', error);
    return `<div class="error">Markdown渲染失败: ${error}</div>`;
  }
}

/**
 * 安全渲染Markdown内容
 * @param markdown Markdown格式的文本内容
 * @returns 安全渲染后的HTML字符串
 */
export function renderMarkdownSafe(markdown: string): string {
  try {
    if (!markdown) return '';
    
    // 使用相同的配置保持一致性
    return marked.parse(markdown, {
      breaks: true,
      gfm: true
    }) as string;
  } catch (error) {
    console.error('安全Markdown渲染错误:', error);
    return `<div class="error">Markdown渲染失败</div>`;
  }
} 