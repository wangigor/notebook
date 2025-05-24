import React, { useEffect, useRef, useState } from 'react';
import { Spin, Typography } from '@douyinfe/semi-ui';
import { renderAsync } from 'docx-preview';
import { API_BASE_URL } from '../../../config';

interface WordPreviewProps {
  documentId: number;
  width?: number | string;
  height?: number | string;
}

/**
 * Word文档预览组件
 * 使用docx-preview库渲染Word文档内容
 * 通过文档ID从API获取二进制内容
 */
const WordPreview: React.FC<WordPreviewProps> = ({
  documentId,
  width = '100%',
  height = '600px'
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [documentBlob, setDocumentBlob] = useState<Blob | null>(null);

  // 文档渲染函数
  const renderWordDocument = async (blob: Blob) => {
    try {
      if (containerRef.current) {
        console.log('清空容器准备渲染...');
        containerRef.current.innerHTML = '';
        
        // 渲染Word文档
        console.log('开始渲染Word文档...');
        await renderAsync(blob, containerRef.current, containerRef.current, {
          className: 'docx-viewer',
          inWrapper: true
        });
        console.log('Word文档渲染成功');
      } else {
        console.error('容器引用为null，无法渲染文档');
        throw new Error('容器未准备就绪');
      }
    } catch (err) {
      console.error('渲染Word文档失败:', err);
      setError(`无法渲染Word文档: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  // 组件挂载时记录日志
  useEffect(() => {
    console.log('WordPreview组件挂载，documentId:', documentId);
    
    return () => {
      console.log('WordPreview组件卸载');
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    console.log('WordPreview开始获取文档数据，documentId:', documentId);
    
    const renderDocument = async () => {

      
      if (!documentId) {
        console.error('WordPreview缺少documentId');
        setError('无法加载Word文档：缺少文档ID');
        setLoading(false);
        return;
      }
      
      try {
        setLoading(true);
        
        // 构建请求URL
        const requestUrl = `${API_BASE_URL}/documents/${documentId}/binary`;
        console.log('WordPreview请求URL:', requestUrl);
        console.log('API_BASE_URL的值:', API_BASE_URL);
        
        // 直接从binary API获取二进制数据
        console.log('开始请求Word文档二进制数据...');
        const response = await fetch(requestUrl, {
          method: 'GET',
          credentials: 'include',
        });
        
        console.log('binary API响应状态:', response.status, response.statusText);
        
        if (!response.ok) {
          const errorMsg = `API请求失败: ${response.status} ${response.statusText}`;
          console.error(errorMsg);
          throw new Error(errorMsg);
        }
        
        // 获取blob数据
        console.log('开始获取Blob数据...');
        const blob = await response.blob();
        console.log('Blob数据获取成功，大小:', blob.size, '字节，类型:', blob.type);
        
        // 确保组件仍然挂载
        if (!isMounted) {
          console.log('组件已卸载，取消渲染');
          return;
        }
        
        
        // 数据获取成功，设置blob数据并停止loading
        if (isMounted) {
          setDocumentBlob(blob);
          setLoading(false);
        }
      } catch (err) {
        console.error('渲染Word文档失败:', err);
        if (isMounted) {
          setError(`无法加载或渲染Word文档: ${err instanceof Error ? err.message : String(err)}`);
          setLoading(false);
        }
      }
    };
    
    renderDocument();
    
    return () => {
      console.log('WordPreview文档获取useEffect清理');
      isMounted = false;
    };
  }, [documentId]);

  // 文档渲染useEffect - 在DOM就绪后渲染
  useEffect(() => {
    if (!loading && documentBlob && containerRef.current) {
      console.log('DOM就绪，开始渲染Word文档');
      renderWordDocument(documentBlob);
    }
  }, [loading, documentBlob]);

  return (
    <div style={{ width, height: 'auto' }}>
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      ) : error ? (
        <Typography.Text type="danger">{error}</Typography.Text>
      ) : (
        <div 
          ref={containerRef} 
          className="word-container" 
          style={{ 
            height, 
            overflow: 'auto',
            border: '1px solid #e0e0e0',
            borderRadius: '4px',
            padding: '16px'
          }}
        />
      )}
    </div>
  );
};

export default WordPreview; 