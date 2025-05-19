import React, { useRef, useEffect } from 'react';
import { Button, Typography, Space, SideSheet } from '@douyinfe/semi-ui';
import { IconFile, IconClose } from '@douyinfe/semi-icons';
import DocumentManager from './DocumentManager';

const { Title } = Typography;

interface DocumentDrawerProps {
  visible: boolean;
  width: number;
  onClose: () => void;
  onWidthChange?: (width: number) => void;
  onUploadSuccess?: () => void;
}

const DocumentDrawer: React.FC<DocumentDrawerProps> = ({
  visible,
  width,
  onClose,
  onWidthChange,
  onUploadSuccess
}) => {
  // 文档管理器引用
  const documentManagerRef = useRef<any>(null);

  // 处理宽度变化
  const handleResize = (e: MouseEvent) => {
    if (onWidthChange) {
      const windowWidth = window.innerWidth;
      // 计算新宽度，并确保至少占窗口宽度的20%，最多占90%
      const newWidth = windowWidth - e.clientX;
      const minWidth = Math.round(windowWidth * 0.2);
      const maxWidth = Math.round(windowWidth * 0.9);
      
      // 限制宽度在合理范围内
      const limitedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
      onWidthChange(limitedWidth);
    }
  };

  // 拖动开始时添加事件监听
  const startResize = () => {
    document.addEventListener('mousemove', handleResize);
    document.addEventListener('mouseup', stopResize);
    document.body.style.userSelect = 'none';
  };

  // 拖动结束时移除事件监听
  const stopResize = () => {
    document.removeEventListener('mousemove', handleResize);
    document.removeEventListener('mouseup', stopResize);
    document.body.style.userSelect = '';
  };

  // 组件卸载时确保事件监听器被移除
  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleResize);
      document.removeEventListener('mouseup', stopResize);
    };
  }, []);

  return (
    <SideSheet
      visible={visible}
      width={width}
      onCancel={onClose}
      maskClosable={true}
      motion={true}
      placement="right"
      style={{ 
        padding: 0,
        position: 'fixed',
        right: 0,
        top: 0,
        height: '100vh',
        zIndex: 1000 
      }}
      headerStyle={{ padding: '12px 16px' }}
      bodyStyle={{ padding: 0 }}
      title={
        <div className="document-drawer-header">
          <Space>
            <IconFile size="large" />
            <Title heading={5} style={{ margin: 0 }}>文档管理</Title>
          </Space>
        </div>
      }
      closeIcon={<IconClose onClick={onClose} />}
    >
      <div className="document-drawer-resize-handle" onMouseDown={startResize} />
      <div className="document-drawer-content">
        <DocumentManager 
          ref={documentManagerRef}
          onUploadSuccess={onUploadSuccess}
        />
      </div>
    </SideSheet>
  );
};

export default DocumentDrawer; 