import React, { useEffect, useRef, useState } from 'react';
import { Spin, Typography, Button } from '@douyinfe/semi-ui';
import * as pdfjsLib from 'pdfjs-dist';
import { IconChevronLeft, IconChevronRight } from '@douyinfe/semi-icons';
import { API_BASE_URL } from '../../../config';
import { documents } from '../../../api/api';

interface PdfPreviewProps {
  documentId: number;
  width?: number | string;
  height?: number | string;
}

const PdfPreview: React.FC<PdfPreviewProps> = ({
  documentId,
  width = '100%',
  height = '500px'
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pdfDoc, setPdfDoc] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState(0);
  const [pageRendering, setPageRendering] = useState(false);
  
  // 初始化PDF.js
  useEffect(() => {
    pdfjsLib.GlobalWorkerOptions.workerSrc = '//cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';
    
    const loadPdf = async () => {
      if (!documentId) {
        setError('缺少文档ID');
        setLoading(false);
        return;
      }
      
      try {
        setLoading(true);
        console.log('获取PDF文档，ID:', documentId);
        
        // 使用preview API获取PDF数据
        const response = await documents.getDocumentPreview(documentId);
        console.log('Preview API响应:', response);
        
        if (!response.success) {
          throw new Error(`获取PDF内容失败: ${response.message}`);
        }
        
        let pdfSource;
        const contentData = response.data.content;
        const contentType = response.data.content_type;
        
        console.log('Preview返回的内容类型:', contentType);
        
        // 处理不同类型的返回数据
        if (contentType && contentType.includes('application/pdf') && contentData) {
          // 如果返回的是base64格式的PDF
          if (typeof contentData === 'string' && contentData.startsWith('data:application/pdf;base64,')) {
            console.log('接收到base64编码的PDF数据');
            pdfSource = contentData; // 直接使用Data URL
          } else {
            // 其他形式的PDF数据，可能需要转换
            console.log('接收到需要转换的PDF数据');
            const base64Data = contentData.replace(/^data:application\/pdf;base64,/, '');
            const binary = atob(base64Data);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
              bytes[i] = binary.charCodeAt(i);
            }
            const blob = new Blob([bytes], { type: 'application/pdf' });
            pdfSource = URL.createObjectURL(blob);
          }
        } else {
          // 如果preview返回了错误信息或普通文本
          console.log('Preview接口未返回PDF数据，尝试使用binary接口获取');
          
          // 回退到binary API
          const binaryResponse = await fetch(`${API_BASE_URL}/documents/${documentId}/binary`, {
            method: 'GET',
            credentials: 'include',
          });
          
          if (!binaryResponse.ok) {
            throw new Error(`获取PDF内容失败: ${binaryResponse.status} ${binaryResponse.statusText}`);
          }
          
          const pdfBlob = await binaryResponse.blob();
          pdfSource = URL.createObjectURL(pdfBlob);
          console.log('从binary API获取数据成功');
        }
        
        // 加载PDF文档
        console.log('开始加载PDF文档');
        const doc = await pdfjsLib.getDocument(pdfSource).promise;
        console.log('PDF文档加载成功，页数:', doc.numPages);
        setPdfDoc(doc);
        setNumPages(doc.numPages);
        setLoading(false);
        renderPage(1, doc);
        
        // 清理URL对象
        return () => {
          if (pdfSource && typeof pdfSource === 'string' && pdfSource.startsWith('blob:')) {
            URL.revokeObjectURL(pdfSource);
            console.log('释放Blob URL资源');
          }
        };
      } catch (err) {
        console.error('Error loading PDF:', err);
        setError('PDF加载失败: ' + (err instanceof Error ? err.message : String(err)));
        setLoading(false);
      }
    };
    
    loadPdf();
  }, [documentId]);
  
  // 渲染PDF页面
  const renderPage = async (pageNum: number, doc?: any) => {
    const pdfDocument = doc || pdfDoc;
    if (!pdfDocument) return;
    
    setPageRendering(true);
    
    try {
      const page = await pdfDocument.getPage(pageNum);
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d');
      
      const viewport = page.getViewport({ scale: 1.5 });
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      
      const renderContext = {
        canvasContext: context,
        viewport: viewport
      };
      
      await page.render(renderContext).promise;
      
      // 清除容器内容
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
        containerRef.current.appendChild(canvas);
      }
      
      setCurrentPage(pageNum);
      setPageRendering(false);
    } catch (error) {
      console.error('Error rendering page:', error);
      setError('页面渲染失败');
      setPageRendering(false);
    }
  };
  
  // 页面导航
  const changePage = (offset: number) => {
    const newPage = currentPage + offset;
    if (newPage < 1 || newPage > numPages) return;
    if (!pageRendering) {
      renderPage(newPage);
    }
  };
  
  return (
    <div style={{ width, height: 'auto', display: 'flex', flexDirection: 'column' }}>
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      ) : error ? (
        <Typography.Text type="danger">{error}</Typography.Text>
      ) : (
        <>
          <div className="pdf-container" ref={containerRef} style={{ flex: 1, overflow: 'auto', textAlign: 'center', marginBottom: '16px' }} />
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Button 
              icon={<IconChevronLeft />}
              onClick={() => changePage(-1)} 
              disabled={currentPage <= 1 || pageRendering}
              type="tertiary"
            >
              上一页
            </Button>
            
            <Typography.Text>{`${currentPage} / ${numPages}`}</Typography.Text>
            
            <Button 
              icon={<IconChevronRight />}
              onClick={() => changePage(1)} 
              disabled={currentPage >= numPages || pageRendering}
              type="tertiary"
              iconPosition="right"
            >
              下一页
            </Button>
          </div>
        </>
      )}
    </div>
  );
};

export default PdfPreview; 