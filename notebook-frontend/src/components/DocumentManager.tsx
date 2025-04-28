import React, { useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import { 
  Table, 
  Button, 
  Toast, 
  Typography, 
  Space, 
  Input, 
  Dropdown, 
  Empty, 
  Pagination, 
  Modal, 
  Form, 
  Tag
} from '@douyinfe/semi-ui';
import {
  IconDelete,
  IconEdit,
  IconEyeOpened,
  IconFile,
  IconMore,
  IconPlus,
  IconRefresh,
  IconSearch
} from '@douyinfe/semi-icons';
import { Document, DocumentPreview } from '../types';
import { documents } from '../api/api';
import DocumentUploader from './DocumentUploader';
import DocumentPreviewModal from './DocumentPreviewModal';
import DocumentEditModal from './DocumentEditModal';

const { Title, Text } = Typography;

const PAGE_SIZE = 10;

// 定义组件Props和Ref类型
export interface DocumentManagerProps {
  onUploadSuccess?: () => void;
}

export interface DocumentManagerRef {
  showUploader: () => void;
}

const DocumentManager = forwardRef<DocumentManagerRef, DocumentManagerProps>((props, ref) => {
  const { onUploadSuccess } = props;
  
  const [documentList, setDocumentList] = useState<DocumentPreview[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchText, setSearchText] = useState('');
  
  // 模态框状态
  const [showUploader, setShowUploader] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  
  // 当前操作的文档
  const [selectedDocument, setSelectedDocument] = useState<DocumentPreview | null>(null);
  
  // 暴露方法给父组件
  useImperativeHandle(ref, () => ({
    showUploader: () => setShowUploader(true)
  }));
  
  // 加载文档列表
  const fetchDocuments = async (page: number = 1, search: string = searchText) => {
    setLoading(true);
    try {
      const skip = (page - 1) * PAGE_SIZE;
      const response = await documents.getDocuments({
        skip,
        limit: PAGE_SIZE,
        search
      });
      
      if (response.success) {
        setDocumentList(response.data.documents);
        setTotalCount(response.data.total);
      } else {
        Toast.error(response.message || '获取文档列表失败');
      }
    } catch (error: any) {
      console.error('获取文档列表失败:', error);
      Toast.error('获取文档列表失败: ' + (error.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  };
  
  // 初始加载
  useEffect(() => {
    fetchDocuments();
  }, []);
  
  // 处理页码变化
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    fetchDocuments(page);
  };
  
  // 处理搜索
  const handleSearch = () => {
    setCurrentPage(1);
    fetchDocuments(1, searchText);
  };
  
  // 处理搜索框键盘事件
  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };
  
  // 处理删除文档
  const handleDeleteDocument = async () => {
    if (!selectedDocument) return;
    
    try {
      const response = await documents.deleteDocument(selectedDocument.id);
      
      if (response.success) {
        Toast.success('文档删除成功');
        // 刷新列表
        fetchDocuments(currentPage);
        // 通知父组件上传成功
        if (onUploadSuccess) {
          onUploadSuccess();
        }
      } else {
        Toast.error(response.message || '删除文档失败');
      }
    } catch (error: any) {
      console.error('删除文档失败:', error);
      Toast.error('删除文档失败: ' + (error.message || '未知错误'));
    }
    
    setShowDeleteConfirm(false);
  };
  
  // 显示删除确认
  const showDeleteConfirmModal = (document: DocumentPreview) => {
    setSelectedDocument(document);
    setShowDeleteConfirm(true);
  };
  
  // 显示预览模态框
  const showPreviewModal = (document: DocumentPreview) => {
    setSelectedDocument(document);
    setShowPreview(true);
  };
  
  // 显示编辑模态框
  const showEditModal = (document: DocumentPreview) => {
    setSelectedDocument(document);
    setShowEdit(true);
  };
  
  // 处理文档上传成功
  const handleUploadSuccess = () => {
    // 刷新列表
    fetchDocuments(1);
    setCurrentPage(1);
    // 通知父组件上传成功
    if (onUploadSuccess) {
      onUploadSuccess();
    }
  };
  
  // 处理编辑成功
  const handleEditSuccess = () => {
    // 刷新列表
    fetchDocuments(currentPage);
    // 通知父组件上传成功
    if (onUploadSuccess) {
      onUploadSuccess();
    }
  };
  
  // 获取文件类型图标
  const getFileTypeIcon = (fileType: string) => {
    const iconStyle = { marginRight: 8 };
    
    switch(fileType.toLowerCase()) {
      case 'pdf':
        return <IconFile style={{ ...iconStyle, color: '#e74c3c' }} />;
      case 'doc':
      case 'docx':
        return <IconFile style={{ ...iconStyle, color: '#3498db' }} />;
      case 'xls':
      case 'xlsx':
        return <IconFile style={{ ...iconStyle, color: '#2ecc71' }} />;
      case 'txt':
        return <IconFile style={{ ...iconStyle, color: '#95a5a6' }} />;
      case 'json':
        return <IconFile style={{ ...iconStyle, color: '#f39c12' }} />;
      case 'md':
        return <IconFile style={{ ...iconStyle, color: '#9b59b6' }} />;
      default:
        return <IconFile style={iconStyle} />;
    }
  };
  
  // 表格列定义
  const columns = [
    {
      title: '文档名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: DocumentPreview) => (
        <div style={{ display: 'flex', alignItems: 'center' }}>
          {getFileTypeIcon(record.file_type)}
          <Typography.Text 
            ellipsis={{ showTooltip: true }}
            style={{ maxWidth: 400 }}
          >
            {text}
          </Typography.Text>
        </div>
      )
    },
    {
      title: '类型',
      dataIndex: 'file_type',
      key: 'file_type',
      render: (text: string) => <Tag color="blue">{text.toUpperCase()}</Tag>
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text: string) => new Date(text).toLocaleString()
    },
    {
      title: '操作',
      key: 'action',
      render: (_: string, record: DocumentPreview) => (
        <Space>
          <Button 
            icon={<IconEyeOpened />}
            theme="borderless" 
            size="small"
            onClick={() => showPreviewModal(record)}
          />
          <Button
            icon={<IconEdit />}
            theme="borderless"
            size="small"
            onClick={() => showEditModal(record)}
          />
          <Dropdown
            trigger="click"
            position="bottomRight"
            render={
              <Dropdown.Menu>
                <Dropdown.Item 
                  icon={<IconDelete />}
                  type="danger"
                  onClick={() => showDeleteConfirmModal(record)}
                >
                  删除
                </Dropdown.Item>
              </Dropdown.Menu>
            }
          >
            <Button 
              icon={<IconMore />} 
              theme="borderless" 
              size="small" 
            />
          </Dropdown>
        </Space>
      )
    }
  ];
  
  return (
    <div className="document-manager">
      <div className="document-manager-header" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Title heading={3}>文档管理</Title>
        <Space>
          <Input
            placeholder="搜索文档名称或内容"
            value={searchText}
            onChange={setSearchText}
            onKeyDown={handleSearchKeyDown}
            prefix={<IconSearch />}
            showClear
            style={{ width: 250 }}
          />
          <Button 
            icon={<IconSearch />} 
            onClick={handleSearch}
          >
            搜索
          </Button>
          <Button 
            icon={<IconRefresh />} 
            onClick={() => fetchDocuments(currentPage)}
          >
            刷新
          </Button>
          <Button 
            type="primary" 
            icon={<IconPlus />}
            onClick={() => setShowUploader(true)}
          >
            上传文档
          </Button>
        </Space>
      </div>
      
      <Table
        columns={columns}
        dataSource={documentList}
        loading={loading}
        pagination={false}
        empty={
          <Empty
            image={<IconFile size="large" />}
            title="暂无文档"
            description="上传文档以便AI助手能够回答相关问题"
          />
        }
      />
      
      {totalCount > 0 && (
        <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination
            currentPage={currentPage}
            pageSize={PAGE_SIZE}
            total={totalCount}
            onPageChange={handlePageChange}
          />
        </div>
      )}
      
      {/* 文档上传对话框 */}
      <DocumentUploader
        visible={showUploader}
        onClose={() => setShowUploader(false)}
        onSuccess={handleUploadSuccess}
      />
      
      {/* 文档预览对话框 */}
      {selectedDocument && (
        <DocumentPreviewModal
          visible={showPreview}
          onClose={() => setShowPreview(false)}
          document={selectedDocument}
        />
      )}
      
      {/* 文档编辑对话框 */}
      {selectedDocument && (
        <DocumentEditModal
          visible={showEdit}
          onClose={() => setShowEdit(false)}
          document={selectedDocument}
          onSuccess={handleEditSuccess}
        />
      )}
      
      {/* 删除确认对话框 */}
      <Modal
        title="删除确认"
        visible={showDeleteConfirm}
        onOk={handleDeleteDocument}
        onCancel={() => setShowDeleteConfirm(false)}
        maskClosable={false}
        closeOnEsc={true}
      >
        <p>确认要删除文档 "{selectedDocument?.name}" 吗？删除后将无法恢复，且AI助手将不再能访问此文档内容。</p>
      </Modal>
    </div>
  );
});

export default DocumentManager; 