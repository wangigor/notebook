import React, { useState, useEffect } from 'react';
import { Table, Button, Typography, Popconfirm, Tag, Empty, Space } from '@douyinfe/semi-ui';
import { IconDelete, IconEdit, IconEyeOpened, IconRefresh } from '@douyinfe/semi-icons';
import { documents } from '../api/api';
import { Document } from '../types';
import DocumentPreviewModal from './DocumentPreviewModal';
import DocumentEditModal from './DocumentEditModal';

interface DocumentListProps {
  onOpenUploader: () => void;
}

const { Text } = Typography;

const DocumentList: React.FC<DocumentListProps> = ({ onOpenUploader }) => {
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [editDoc, setEditDoc] = useState<Document | null>(null);
  
  // 获取文档列表
  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await documents.getDocuments();
      if (response.success) {
        setDocuments(response.data || []);
      } else {
        console.error('获取文档列表失败:', response.message);
      }
    } catch (error) {
      console.error('获取文档列表出错:', error);
    } finally {
      setLoading(false);
    }
  };

  // 删除文档
  const handleDelete = async (docId: string) => {
    try {
      const response = await documents.deleteDocument(docId);
      if (response.success) {
        // 从列表中移除
        setDocuments(docs => docs.filter(doc => doc.id !== docId));
      }
    } catch (error) {
      console.error('删除文档失败:', error);
    }
  };

  // 组件挂载时获取文档列表
  useEffect(() => {
    fetchDocuments();
  }, []);

  // 获取文件类型的标签颜色
  const getFileTypeColor = (fileName: string) => {
    const extension = fileName.split('.').pop()?.toLowerCase() || '';
    
    switch(extension) {
      case 'pdf': return 'red';
      case 'doc': 
      case 'docx': return 'blue';
      case 'xls':
      case 'xlsx': return 'green';
      case 'csv': return 'teal';
      case 'txt': return 'grey';
      case 'md': return 'purple';
      case 'json': return 'orange';
      default: return 'light-blue';
    }
  };

  // 渲染额外的标签（从元数据中）
  const renderTags = (doc: Document) => {
    if (!doc.metadata || typeof doc.metadata !== 'object') return null;
    
    const tags = doc.metadata.tags;
    if (!tags || !Array.isArray(tags) || tags.length === 0) return null;
    
    return (
      <div style={{ marginTop: 8 }}>
        {tags.map((tag: string, index: number) => (
          <Tag key={index} color="white" type="border" style={{ marginRight: 4 }}>
            {tag}
          </Tag>
        ))}
      </div>
    );
  };

  const columns = [
    {
      title: '文档名称',
      dataIndex: 'name',
      width: '30%',
      render: (text: string, record: Document) => (
        <div>
          <Text strong>{text}</Text>
          {renderTags(record)}
        </div>
      )
    },
    {
      title: '文件',
      dataIndex: 'filename',
      width: '20%',
      render: (text: string) => (
        <Tag color={getFileTypeColor(text)}>
          {text}
        </Tag>
      )
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      width: '20%',
      render: (time: string) => {
        const date = new Date(time);
        return date.toLocaleString('zh-CN');
      }
    },
    {
      title: '操作',
      dataIndex: 'operations',
      width: '30%',
      render: (_: any, record: Document) => (
        <Space>
          <Button 
            icon={<IconEyeOpened />} 
            onClick={() => setPreviewDoc(record)}
            type="tertiary"
            theme="borderless"
          >
            预览
          </Button>
          <Button 
            icon={<IconEdit />} 
            onClick={() => setEditDoc(record)}
            type="tertiary"
            theme="borderless"
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个文档吗？"
            content="删除后将无法恢复此文档数据"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button 
              icon={<IconDelete />} 
              type="danger"
              theme="borderless"
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <div className="document-list">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Button 
            icon={<IconRefresh />}
            onClick={fetchDocuments}
            loading={loading}
            style={{ marginRight: 8 }}
          >
            刷新
          </Button>
        </div>
        <Button type="primary" onClick={onOpenUploader}>上传新文档</Button>
      </div>

      <Table
        columns={columns}
        dataSource={documents}
        loading={loading}
        pagination={{
          pageSize: 10
        }}
        empty={
          <Empty
            image={<Empty.Image />}
            title="暂无文档"
            description="您还没有上传任何文档到知识库"
          >
            <Button type="primary" onClick={onOpenUploader}>
              上传文档
            </Button>
          </Empty>
        }
      />

      {/* 文档预览模态框 */}
      {previewDoc && (
        <DocumentPreviewModal
          visible={!!previewDoc}
          document={previewDoc}
          onClose={() => setPreviewDoc(null)}
        />
      )}

      {/* 文档编辑模态框 */}
      {editDoc && (
        <DocumentEditModal
          visible={!!editDoc}
          document={editDoc}
          onClose={() => setEditDoc(null)}
          onSuccess={(updatedDoc) => {
            // 更新列表中的文档
            setDocuments(docs => 
              docs.map(doc => doc.id === updatedDoc.id ? updatedDoc : doc)
            );
            setEditDoc(null);
          }}
        />
      )}
    </div>
  );
};

export default DocumentList; 