import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Typography, Button, Space, Empty, Divider } from '@douyinfe/semi-ui';
import { IconArrowLeft, IconUpload } from '@douyinfe/semi-icons';
import DocumentUploader from '../components/DocumentUploader';
import { TaskMonitor } from '../components/TaskMonitor';

const { Title, Paragraph } = Typography;

const DocumentUploadPage: React.FC = () => {
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [uploadedTaskId, setUploadedTaskId] = useState<string | null>(null);
  const navigate = useNavigate();
  
  const handleUploadSuccess = (taskId?: string) => {
    if (taskId) {
      setUploadedTaskId(taskId);
      setUploadModalVisible(false);
    }
  };
  
  const handleViewDocuments = () => {
    navigate('/documents');
  };
  
  return (
    <div className="document-upload-container">
      <div style={{ marginBottom: 16 }}>
        <Button icon={<IconArrowLeft />} theme="borderless" onClick={handleViewDocuments}>
          返回文档列表
        </Button>
      </div>
      
      <Title heading={3}>上传文档</Title>
      <Paragraph>
        上传文档后系统将自动处理并索引文档内容，便于后续查询和分析。
      </Paragraph>
      
      <Card style={{ marginTop: 24 }}>
        {!uploadedTaskId ? (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <Empty
              image={<IconUpload size="large" />}
              title="上传文档"
              description="点击下方按钮上传文档文件"
            />
            <div style={{ marginTop: 16 }}>
              <Button type="primary" onClick={() => setUploadModalVisible(true)}>
                选择文件上传
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <Title heading={5}>文档处理进度</Title>
            <Divider margin="12px" />
            <TaskMonitor taskId={uploadedTaskId} />
            <div style={{ marginTop: 16, textAlign: 'center' }}>
              <Space>
                <Button onClick={() => setUploadedTaskId(null)}>
                  上传新文档
                </Button>
                <Button type="primary" onClick={handleViewDocuments}>
                  查看文档列表
                </Button>
              </Space>
            </div>
          </div>
        )}
      </Card>
      
      <DocumentUploader
        visible={uploadModalVisible}
        onClose={() => setUploadModalVisible(false)}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
};

export default DocumentUploadPage; 