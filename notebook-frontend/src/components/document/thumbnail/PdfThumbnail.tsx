import React, { useState, useEffect, useRef } from 'react';
import { Spin } from '@douyinfe/semi-ui';
// 解除注释，导入PDF.js库
import * as pdfjsLib from 'pdfjs-dist';

interface PdfThumbnailProps {
  url: string;
  documentId: number;
  width?: number;
  height?: number;
}

/**
 * PDF文档缩略图组件
 * 使用PDF.js渲染PDF文档的第一页作为缩略图
 */
const PdfThumbnail: React.FC<PdfThumbnailProps> = ({ 
  url, 
  width = 120, 
  height = 160 
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let isMounted = true;
    
    // 确保PDF.js worker已加载
    pdfjsLib.GlobalWorkerOptions.workerSrc = '//cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';
    
    const loadPdf = async () => {
      try {
        setLoading(true);
        
        // 加载PDF文档
        const loadingTask = pdfjsLib.getDocument(url);
        const pdf = await loadingTask.promise;
        
        // 获取第一页
        const page = await pdf.getPage(1);
        
        if (!isMounted || !canvasRef.current) return;
        
        // 设置缩放比例以适应指定宽高
        const viewport = page.getViewport({ scale: 1.0 });
        const scale = Math.min(width / viewport.width, height / viewport.height);
        const scaledViewport = page.getViewport({ scale });
        
        // 准备canvas
        const canvas = canvasRef.current;
        const context = canvas.getContext('2d');
        canvas.width = width;
        canvas.height = height;
        
        if (!context) {
          setError('无法获取canvas上下文');
          setLoading(false);
          return;
        }
        
        // 渲染PDF页面到canvas
        const renderContext = {
          canvasContext: context,
          viewport: scaledViewport
        };
        
        await page.render(renderContext).promise;
        setLoading(false);
        
      } catch (err) {
        if (isMounted) {
          console.error('加载PDF缩略图失败:', err);
          setError('加载失败');
          setLoading(false);
        }
      }
    };
    
    loadPdf();
    
    return () => {
      isMounted = false;
    };
  }, [url, width, height]);

  return (
    <div 
      className="pdf-thumbnail" 
      style={{ 
        width, 
        height, 
        position: 'relative',
        overflow: 'hidden',
        borderRadius: '4px',
        backgroundColor: '#f5f5f5',
        border: '1px solid #e0e0e0',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center'
      }}
    >
      {loading && (
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <Spin size="small" />
        </div>
      )}
      
      {error && (
        <div style={{ padding: '8px', textAlign: 'center', fontSize: '12px' }}>
          {error}
        </div>
      )}
      
      <canvas 
        ref={canvasRef} 
        style={{ 
          maxWidth: '100%', 
          maxHeight: '100%', 
          display: loading || error ? 'none' : 'block'
        }} 
      />
    </div>
  );
};

export default PdfThumbnail; 