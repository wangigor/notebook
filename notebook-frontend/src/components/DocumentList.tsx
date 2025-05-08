import React, { useState, useEffect } from 'react';
import { Table, Button, Typography, Popconfirm, Tag, Empty, Space, Progress } from '@douyinfe/semi-ui';
import { IconDelete, IconEdit, IconEyeOpened, IconRefresh } from '@douyinfe/semi-icons';
import { documents } from '../api/api';
import { Document } from '../types';
import DocumentPreviewModal from './DocumentPreviewModal';
import DocumentEditModal from './DocumentEditModal';
import { TaskStatusBadge } from './shared/TaskStatusBadge';
import { TaskDetailModal } from './TaskDetailModal';

interface DocumentListProps {
  onOpenUploader: () => void;
}

const { Text } = Typography;

const DocumentList: React.FC<DocumentListProps> = ({ onOpenUploader }) => {
  const [loading, setLoading] = useState(false);
  const [documentList, setDocumentList] = useState<Document[]>([]);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [editDoc, setEditDoc] = useState<Document | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState('');
  const [taskModalVisible, setTaskModalVisible] = useState(false);
  
  // 获取文档列表
  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await documents.getDocuments();
      if (response.success) {
        setDocumentList(response.data?.items || []);
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
  const handleDelete = async (docId: number) => {
    try {
      const response = await documents.deleteDocument(docId);
      if (response.success) {
        // 从列表中移除
        setDocumentList(docs => docs.filter(doc => doc.id !== docId));
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
          <Tag key={index} color="white" style={{ marginRight: 4 }}>
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
      width: '25%',
      render: (text: string, record: Document) => (
        <div>
          <Text strong>{text}</Text>
          {renderTags(record)}
        </div>
      )
    },
    {
      title: '文件',
      dataIndex: 'file_type',
      width: '15%',
      render: (text: string) => text ? (
        <Tag color={getFileTypeColor(text)}>
          {text}
        </Tag>
      ) : <Tag color="light-blue">未知</Tag>
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      width: '15%',
      render: (time: string) => {
        const date = new Date(time);
        return date.toLocaleString('zh-CN');
      }
    },
    {
      title: '处理状态',
      dataIndex: 'latest_task',
      width: '20%',
      render: (latestTask: any, record: Document) => {
        if (!latestTask) return <Text type="tertiary">无任务</Text>;
        
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TaskStatusBadge status={latestTask.status} />
            <Progress 
              percent={latestTask.progress || 0} 
              size="small" 
              style={{ width: '80px' }} 
            />
            <Button 
              type="tertiary" 
              icon={<IconEyeOpened />} 
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedTaskId(latestTask.id);
                setTaskModalVisible(true);
              }}
            >
              详情
            </Button>
          </div>
        );
      }
    },
    {
      title: '操作',
      dataIndex: 'operations',
      width: '25%',
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
        dataSource={documentList}
        loading={loading}
        pagination={{
          pageSize: 10
        }}
        empty={
          <Empty
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
            setDocumentList(docs => 
              docs.map(doc => doc.id === updatedDoc.id ? updatedDoc : doc)
            );
            setEditDoc(null);
          }}
        />
      )}
      
      {/* 任务详情对话框 */}
      {selectedTaskId && (
        <TaskDetailModal 
          taskId={selectedTaskId}
          visible={taskModalVisible}
          onCancel={() => setTaskModalVisible(false)}
        />
      )}
    </div>
  );
};

export default DocumentList; 