import React, { useState, useEffect } from 'react';
import { 
  Modal, 
  Upload, 
  Input, 
  Button, 
  Toast, 
  Typography, 
  Tabs, 
  Tooltip, 
  Banner, 
  Steps,
  TextArea
} from '@douyinfe/semi-ui';
import { 
  IconUpload, 
  IconFile, 
  IconGlobe, 
  IconEdit, 
  IconInfoCircle 
} from '@douyinfe/semi-icons';
import { documents } from '../api/api';
import WebDocumentForm from './WebDocumentForm';
import CustomDocumentForm from './CustomDocumentForm';
import { DocumentUploadProgress } from './DocumentUploadProgress';
import { TaskDetailModal } from './TaskDetailModal';

interface DocumentUploaderProps {
  visible: boolean;
  onClose: () => void;
  onSuccess?: (taskId?: string) => void;
}

const { Paragraph, Text } = Typography;
const { TabPane } = Tabs;

const DocumentUploader: React.FC<DocumentUploaderProps> = ({
  visible,
  onClose,
  onSuccess
}) => {
  const [uploadLoading, setUploadLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState('');
  const [metadata, setMetadata] = useState('');
  const [activeTab, setActiveTab] = useState('upload');
  const [uploadTaskId, setUploadTaskId] = useState<string | null>(null);
  const [showProgress, setShowProgress] = useState(false);
  const [taskModalVisible, setTaskModalVisible] = useState(false);

  // 添加useEffect跟踪file状态变化
  useEffect(() => {
    console.log('file状态已更新:', file ? `${file.name} (${file.size} bytes)` : 'null');
  }, [file]);

  // 验证JSON字符串
  const isValidJson = (jsonString: string): boolean => {
    if (!jsonString.trim()) return true;
    try {
      JSON.parse(jsonString);
      return true;
    } catch (e) {
      return false;
    }
  };

  // 验证表单是否有效
  const isFormValid = (): boolean => {
    return !!file && !!fileName.trim() && (metadata ? isValidJson(metadata) : true);
  };

  // 获取上传按钮的禁用提示
  const getUploadButtonTooltip = (): string => {
    if (!file) return '请选择要上传的文件';
    if (!fileName.trim()) return '请输入文档名称';
    if (metadata && !isValidJson(metadata)) return '元数据格式不正确，请输入有效的JSON';
    return '';
  };

  // 获取已完成步骤数
  const getCompletedSteps = (): number => {
    let steps = 0;
    if (file) steps++;
    if (fileName.trim()) steps++;
    if (!metadata || isValidJson(metadata)) steps++;
    return steps;
  };

  // 完全重写handleFileChange函数
  const handleFileChange = (options: any) => {
    console.log('Upload事件触发:', options);
    
    let fileObj = null;
    
    // Semi UI的Upload组件在onChange事件中传递不同的参数结构
    // 根据Semi UI的文档，我们可能收到以下几种情况：
    if (options) {
      if (options.currentFile && options.currentFile.fileInstance) {
        // Semi UI v2.x
        fileObj = options.currentFile.fileInstance;
      } else if (options.fileList && options.fileList.length > 0) {
        // 通过fileList获取
        const firstFile = options.fileList[0];
        fileObj = firstFile.fileInstance || firstFile.originFileObj || firstFile.file || firstFile;
      } else if (options.selectedFile) {
        // 某些版本可能直接提供selectedFile
        fileObj = options.selectedFile;
      } else if (options.file) {
        // 直接通过file属性
        fileObj = options.file;
      } else if (Array.isArray(options) && options.length > 0) {
        // 如果options本身是文件数组
        fileObj = options[0];
      }
    }
    
    if (fileObj && fileObj.name) {
      console.log('成功获取文件对象:', fileObj.name);
      setFile(fileObj);
      
      // 自动填充文件名（去除扩展名）
      const nameWithoutExt = fileObj.name.replace(/\.[^/.]+$/, "");
      setFileName(nameWithoutExt);
    } else {
      console.error('无法从事件中获取文件:', options);
      // 不要设置null，可能是已经有文件了
      // setFile(null);
    }
  };

  // 处理上传
  const handleUpload = async () => {
    if (!file) {
      Toast.error('请选择要上传的文件');
      return;
    }

    if (!fileName.trim()) {
      Toast.error('请输入文档名称');
      return;
    }

    // 解析元数据
    let parsedMetadata = {};
    if (metadata && metadata.trim()) {
      try {
        parsedMetadata = JSON.parse(metadata);
      } catch (error) {
        Toast.error('元数据格式不正确，请输入有效的JSON');
        return;
      }
    }

    setUploadLoading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('metadata', JSON.stringify({
        name: fileName,
        ...parsedMetadata
      }));
      
      console.log('开始上传文件，大小:', file.size);
      const response = await documents.uploadDocument(formData);

      console.log('上传响应:', response);
      if (response.success) {
        if (response.data && 'task_id' in response.data) {
          // 设置任务ID并显示进度
          const taskId = response.data.task_id as string;
          setUploadTaskId(taskId);
          setShowProgress(true);
          Toast.success('文件已上传，正在处理');
        } else {
          Toast.success('文件上传成功');
          resetForm();
          if (onSuccess) {
            onSuccess();
          }
          onClose();
        }
      } else {
        Toast.error(response.message || '上传文档失败');
      }
    } catch (error: any) {
      console.error('上传文档错误:', error);
      Toast.error('上传文档失败: ' + (error.message || '未知错误'));
    } finally {
      setUploadLoading(false);
    }
  };

  // 处理任务完成
  const handleTaskComplete = (success: boolean) => {
    if (success) {
      Toast.success('文件处理完成');
      
      // 刷新文档列表或其他后续操作
      if (onSuccess) {
        onSuccess(uploadTaskId || undefined);
      }
      
      // 延迟关闭组件
      setTimeout(() => {
        setShowProgress(false);
        onClose();
      }, 1000);
    } else {
      Toast.error('文件处理失败');
    }
  };

  // 重置表单
  const resetForm = () => {
    setFile(null);
    setFileName('');
    setMetadata('');
    setActiveTab('upload');
    setUploadTaskId(null);
    setShowProgress(false);
  };
  
  // 处理标签页变更
  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
  };
  
  // 处理关闭
  const handleClose = () => {
    resetForm();
    onClose();
  };
  
  // 处理其他方式添加文档成功
  const handleOtherSuccess = () => {
    if (onSuccess) {
      onSuccess();
    }
    onClose();
  };

  return (
    <Modal
      title="添加文档"
      visible={visible}
      onCancel={handleClose}
      footer={
        activeTab === 'upload' && !showProgress ? (
          <Tooltip
            content={getUploadButtonTooltip()}
            position="top"
            trigger="hover"
            visible={!isFormValid() ? undefined : false}
          >
            <Button 
              icon={<IconUpload />}
              type="primary"
              onClick={handleUpload}
              loading={uploadLoading}
              disabled={!isFormValid()}
            >
              上传
            </Button>
          </Tooltip>
        ) : null
      }
      closeOnEsc
      width={700}
    >
      <Tabs activeKey={activeTab} onChange={handleTabChange}>
        <TabPane 
          tab={<span><IconUpload style={{ marginRight: 4 }} />本地文件</span>} 
          itemKey="upload"
        >
          <div style={{ padding: '16px 0' }}>
            {/* 显示上传进度 */}
            {showProgress && uploadTaskId ? (
              <DocumentUploadProgress 
                taskId={uploadTaskId}
                fileName={fileName}
                onViewDetails={() => setTaskModalVisible(true)}
                onComplete={handleTaskComplete}
                onClose={() => setShowProgress(false)}
              />
            ) : (
              <div className="upload-form">
                {/* 添加表单完成进度指示器 */}
                <div style={{ marginBottom: 20 }}>
                  <Steps type="basic" current={getCompletedSteps()} size="small">
                    <Steps.Step title="选择文件" status={file ? 'finish' : 'wait'} />
                    <Steps.Step title="文档命名" status={fileName.trim() ? 'finish' : 'wait'} />
                    <Steps.Step 
                      title="添加元数据" 
                      status={metadata && !isValidJson(metadata) ? 'error' : metadata ? 'finish' : 'wait'} 
                    />
                  </Steps>
                </div>
              
                {/* 文件上传区域 */}
                <div className="form-item" style={{ marginBottom: 16, display: 'flex' }}>
                  <div className="form-label" style={{ width: 100, textAlign: 'right', paddingRight: 12, lineHeight: '32px' }}>选择文件</div>
                  <div className="form-control" style={{ flex: 1 }}>
                    <Upload
                      accept=".pdf,.doc,.docx,.txt,.md,.csv,.json"
                      draggable
                      limit={1}
                      onChange={handleFileChange}
                      action=""
                      customRequest={() => {}}
                      uploadTrigger="custom"
                      onRemove={() => setFile(null)}
                      listType="picture"
                      defaultFileList={file ? [{ 
                        uid: '1',
                        name: file.name, 
                        size: String(file.size),
                        status: 'success' 
                      }] : []}
                    >
                      <div style={{ textAlign: 'center', padding: '20px 0' }}>
                        <IconFile size="extra-large" style={{ color: 'var(--semi-color-text-2)' }} />
                        <Paragraph style={{ margin: '8px 0 4px' }}>
                          <Text>点击或拖拽文件到这里上传</Text>
                        </Paragraph>
                        <Paragraph style={{ marginTop: 0 }}>
                          <Text type="tertiary">支持 PDF, Word, TXT, CSV, JSON, Markdown 格式</Text>
                        </Paragraph>
                      </div>
                    </Upload>
                    
                    {/* 文件已选提示 */}
                    {file && (
                      <div style={{ marginTop: 8 }}>
                        <Text type="success">已选择文件: {file.name}</Text>
                      </div>
                    )}
                  </div>
                </div>
                
                {/* 文档名称 */}
                <div className="form-item" style={{ marginBottom: 16, display: 'flex' }}>
                  <div className="form-label" style={{ width: 100, textAlign: 'right', paddingRight: 12, lineHeight: '32px' }}>文档名称</div>
                  <div className="form-control" style={{ flex: 1 }}>
                    <Input
                      value={fileName}
                      onChange={setFileName}
                      placeholder="输入文档名称"
                      showClear
                    />
                  </div>
                </div>
                
                {/* 元数据（JSON） */}
                <div className="form-item" style={{ marginBottom: 16, display: 'flex' }}>
                  <div className="form-label" style={{ width: 100, textAlign: 'right', paddingRight: 12, alignItems: 'center', display: 'flex' }}>
                    <span>元数据</span>
                    <Tooltip content="JSON格式的元数据，如标签、描述等">
                      <IconInfoCircle size="small" style={{ marginLeft: 4 }} />
                    </Tooltip>
                  </div>
                  <div className="form-control" style={{ flex: 1 }}>
                    <TextArea
                      value={metadata}
                      onChange={setMetadata}
                      placeholder='{"tags": ["示例", "文档"], "description": "这是一个示例文档"}'
                      showClear
                      rows={4}
                    />
                    
                    {/* 提示信息 */}
                    {metadata && !isValidJson(metadata) && (
                      <Banner type="danger" description="元数据必须是有效的JSON格式" />
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </TabPane>
        <TabPane 
          tab={<span><IconGlobe style={{ marginRight: 4 }} />网页文档</span>} 
          itemKey="web"
        >
          <WebDocumentForm onSuccess={handleOtherSuccess} />
        </TabPane>
        <TabPane 
          tab={<span><IconEdit style={{ marginRight: 4 }} />自定义</span>} 
          itemKey="custom"
        >
          <CustomDocumentForm onSuccess={handleOtherSuccess} />
        </TabPane>
      </Tabs>
      
      {/* 添加任务详情对话框 */}
      {uploadTaskId && (
        <TaskDetailModal 
          taskId={uploadTaskId}
          visible={taskModalVisible}
          onCancel={() => setTaskModalVisible(false)}
          title="文件处理详情"
        />
      )}
    </Modal>
  );
};

export default DocumentUploader; 