## 五、前端实现

### 1. 文档上传组件（增强版）
```tsx
import React, { useState, useRef } from 'react';
import { Upload, message, Button, Progress, Card, Alert } from 'antd';
import { UploadOutlined, InboxOutlined } from '@ant-design/icons';
import { uploadDocument } from '../api/documents';

const { Dragger } = Upload;

const EnhancedDocumentUploader = ({ onSuccess, metadata = {} }) => {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [taskId, setTaskId] = useState(null);
  const [processingStep, setProcessingStep] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState(null);
  
  // WebSocket连接
  const wsRef = useRef(null);

  // 处理文件上传
  const handleUpload = async file => {
    setUploading(true);
    setProgress(0);
    setError(null);
    
    try {
      // 上传文件
      const response = await uploadDocument(file, metadata);
      
      if (response.success) {
        message.success(`${file.name} 上传成功，正在处理...`);
        setTaskId(response.task_id);
        
        // 建立WebSocket连接监听任务进度
        connectToTaskWebSocket(response.task_id);
        
        if (onSuccess) {
          onSuccess(response);
        }
      } else {
        setError(response.message || '上传失败');
        message.error(`${file.name} 上传失败: ${response.message}`);
      }
    } catch (error) {
      setError(error.message || '上传过程中出错');
      message.error(`${file.name} 上传失败: ${error.message || '未知错误'}`);
    } finally {
      setUploading(false);
    }
  };

  // 建立WebSocket连接
  const connectToTaskWebSocket = (task_id) => {
    const token = localStorage.getItem('authToken'); // 获取认证令牌
    const ws = new WebSocket(`${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/tasks/${task_id}?token=${token}`);
    
    ws.onopen = () => {
      console.log('WebSocket连接已建立');
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'task_update') {
          const taskInfo = data.data;
          const stepInfo = taskInfo.steps && taskInfo.steps.find(s => s.status === 'RUNNING');
          
          setProgress(taskInfo.overall_progress || 0);
          setProcessingStep(stepInfo ? stepInfo.step_name : '');
          setStatusMessage(getStatusMessage(taskInfo));
          
          if (taskInfo.status === 'COMPLETED') {
            message.success('文档处理已完成！');
            ws.close();
          } else if (taskInfo.status === 'FAILED') {
            setError(taskInfo.error_message || '处理失败');
            message.error(`处理失败: ${taskInfo.error_message || '未知错误'}`);
            ws.close();
          }
        }
      } catch (error) {
        console.error('解析WebSocket消息出错:', error);
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket错误:', error);
      message.warning('任务状态更新连接出错');
    };
    
    ws.onclose = () => {
      console.log('WebSocket连接已关闭');
    };
    
    wsRef.current = ws;
    return ws;
  };
  
  // 根据任务状态生成用户友好的消息
  const getStatusMessage = (taskInfo) => {
    const stepMap = {
      'VALIDATE': '验证文件',
      'UPLOAD_TO_STORAGE': '上传到安全存储',
      'EXTRACT_TEXT': '提取文本内容',
      'PREPROCESS': '预处理文本',
      'VECTORIZE': '向量化文本',
      'STORE': '存储向量索引'
    };
    
    const runningStep = taskInfo.steps && taskInfo.steps.find(s => s.status === 'RUNNING');
    if (runningStep) {
      return `正在${stepMap[runningStep.step_name] || runningStep.step_name}...`;
    }
    
    switch (taskInfo.status) {
      case 'PENDING': return '等待处理...';
      case 'RUNNING': return '处理中...';
      case 'COMPLETED': return '处理完成！';
      case 'FAILED': return `处理失败: ${taskInfo.error_message || '未知错误'}`;
      default: return '正在处理...';
    }
  };
  
  // 组件卸载时关闭WebSocket连接
  React.useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Dragger配置
  const draggerProps = {
    name: 'file',
    multiple: false,
    beforeUpload: file => {
      // 文件类型验证
      const allowedTypes = ['.pdf', '.docx', '.doc', '.txt'];
      const isAllowedType = allowedTypes.some(type => 
        file.name.toLowerCase().endsWith(type)
      );
      
      if (!isAllowedType) {
        message.error(`${file.name} 不是支持的文件类型`);
        return Upload.LIST_IGNORE;
      }
      
      // 文件大小验证
      const maxSize = 50 * 1024 * 1024; // 50MB
      if (file.size > maxSize) {
        message.error(`${file.name} 超过最大文件大小限制 (50MB)`);
        return Upload.LIST_IGNORE;
      }
      
      // 手动处理上传
      handleUpload(file);
      return false;
    },
    showUploadList: false,
  };

  return (
    <Card title="上传文档" bordered={true}>
      <Dragger {...draggerProps} disabled={uploading}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">
          支持单个文件上传，格式包括PDF、Word和TXT文档
        </p>
      </Dragger>
      
      {(uploading || progress > 0) && (
        <div style={{ marginTop: 16 }}>
          <Progress 
            percent={progress} 
            status={error ? 'exception' : 'active'} 
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
          />
          <div style={{ marginTop: 8, textAlign: 'center' }}>
            {statusMessage || '处理中...'}
          </div>
          {processingStep && (
            <div style={{ fontSize: '12px', color: '#888', textAlign: 'center' }}>
              当前步骤: {processingStep}
            </div>
          )}
        </div>
      )}
      
      {error && (
        <Alert
          message="上传或处理出错"
          description={error}
          type="error"
          showIcon
          style={{ marginTop: 16 }}
        />
      )}
    </Card>
  );
};

export default EnhancedDocumentUploader;
```

### 2. 文档下载组件
// ... 保持现有代码不变 ...

### 3. 文档详情页面
// ... 保持现有代码不变 ...

### 4. API客户端扩展
```tsx
// api/documents.js
import axios from 'axios';

export const uploadDocument = async (file, metadata = {}) => {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    // 将元数据转换为JSON字符串
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }
    
    const response = await axios.post('/api/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || '上传文档失败');
  }
};

export const downloadDocument = async (documentId) => {
  try {
    const response = await axios.get(`/api/documents/${documentId}/download`);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || '获取下载链接失败');
  }
};

// 基础搜索API
export const searchDocuments = async (query, options = {}) => {
  try {
    const response = await axios.post('/api/search', {
      query,
      limit: options.limit || 10,
      threshold: options.threshold || 0.7
    });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || '搜索文档失败');
  }
};

// 新增：混合搜索API
export const hybridSearchDocuments = async (params) => {
  try {
    const response = await axios.post('/api/search/hybrid', params);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || '混合搜索文档失败');
  }
};

// ... 其他API方法 ...
```

### 5. 高级搜索组件（增强）
```tsx
import React, { useState } from 'react';
import { 
  Input, Button, List, Spin, Empty, Card, Select, 
  Tag, Slider, Collapse, Radio, Space, Tooltip, Switch,
  Typography
} from 'antd';
import { 
  SearchOutlined, FilterOutlined, FileTextOutlined,
  FilePdfOutlined, FileWordOutlined, 
  SortAscendingOutlined, FullscreenOutlined
} from '@ant-design/icons';
import { hybridSearchDocuments } from '../api/documents';

const { Search } = Input;
const { Option } = Select;
const { Panel } = Collapse;
const { Text, Paragraph } = Typography;

const AdvancedDocumentSearch = () => {
  // 搜索状态
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [searchPerformed, setSearchPerformed] = useState(false);
  const [totalResults, setTotalResults] = useState(0);
  
  // 搜索参数
  const [query, setQuery] = useState('');
  const [keywords, setKeywords] = useState('');
  const [fileTypes, setFileTypes] = useState([]);
  const [granularity, setGranularity] = useState('paragraph');
  const [relevanceThreshold, setRelevanceThreshold] = useState(0.7);
  const [includeContext, setIncludeContext] = useState(true);
  const [contextSize, setContextSize] = useState(2);
  const [resultsLimit, setResultsLimit] = useState(10);
  
  // 高级筛选器可见性
  const [filtersVisible, setFiltersVisible] = useState(false);
  
  // 结果视图模式
  const [viewMode, setViewMode] = useState('compact');
  
  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setSearchPerformed(true);
    
    try {
      // 构建搜索参数
      const searchParams = {
        query,
        keywords: keywords.trim() || undefined,
        file_types: fileTypes.length > 0 ? fileTypes : undefined,
        granularity,
        threshold: relevanceThreshold,
        include_context: includeContext,
        context_size: contextSize,
        limit: resultsLimit
      };
      
      const response = await hybridSearchDocuments(searchParams);
      setResults(response.results || []);
      setTotalResults(response.total || 0);
    } catch (error) {
      console.error('搜索失败:', error);
    } finally {
      setLoading(false);
    }
  };
  
  // 清空所有筛选条件
  const clearFilters = () => {
    setKeywords('');
    setFileTypes([]);
    setGranularity('paragraph');
    setRelevanceThreshold(0.7);
    setIncludeContext(true);
    setContextSize(2);
    setResultsLimit(10);
  };
  
  // 渲染文件类型图标
  const renderFileTypeIcon = (fileType) => {
    if (!fileType) return <FileTextOutlined />;
    
    fileType = fileType.toLowerCase();
    if (fileType.includes('pdf')) return <FilePdfOutlined style={{ color: '#f5222d' }} />;
    if (fileType.includes('doc')) return <FileWordOutlined style={{ color: '#1890ff' }} />;
    return <FileTextOutlined style={{ color: '#52c41a' }} />;
  };
  
  // 高亮显示匹配文本
  const highlightText = (text, query) => {
    if (!query || !text) return text;
    
    // 已有Markdown风格的高亮
    if (text.includes('**')) return text;
    
    try {
      const regex = new RegExp(`(${query})`, 'gi');
      return text.replace(regex, '**$1**');
    } catch (e) {
      return text;
    }
  };
  
  // 渲染Markdown格式文本
  const renderMarkdown = (text) => {
    if (!text) return null;
    
    return text.split('\n').map((line, i) => {
      // 替换Markdown式的加粗
      const parts = line.split(/(\*\*.*?\*\*)/g);
      return (
        <div key={i}>
          {parts.map((part, j) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return <Text key={j} strong mark>{part.slice(2, -2)}</Text>;
            }
            return <span key={j}>{part}</span>;
          })}
        </div>
      );
    });
  };

  return (
    <div className="advanced-document-search">
      <Card title="智能文档搜索" extra={
        <Space>
          <Tooltip title="切换视图模式">
            <Button
              icon={<FullscreenOutlined />}
              onClick={() => setViewMode(viewMode === 'compact' ? 'expanded' : 'compact')}
            />
          </Tooltip>
          <Tooltip title="高级筛选">
            <Button 
              type={filtersVisible ? "primary" : "default"}
              icon={<FilterOutlined />} 
              onClick={() => setFiltersVisible(!filtersVisible)}
            >
              筛选
            </Button>
          </Tooltip>
        </Space>
      }>
        <Search
          placeholder="输入搜索问题或关键词..."
          enterButton={<Button type="primary" icon={<SearchOutlined />}>搜索</Button>}
          size="large"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onSearch={handleSearch}
          loading={loading}
          allowClear
        />
        
        {filtersVisible && (
          <Collapse ghost className="filter-collapse" style={{ marginTop: 16 }}>
            <Panel header="高级搜索选项" key="1">
              <div className="filter-section">
                <div className="filter-row">
                  <div className="filter-label">精确关键词:</div>
                  <div className="filter-control">
                    <Input 
                      placeholder="输入精确匹配的关键词" 
                      value={keywords}
                      onChange={(e) => setKeywords(e.target.value)}
                      allowClear
                    />
                  </div>
                </div>
                
                <div className="filter-row">
                  <div className="filter-label">文件类型:</div>
                  <div className="filter-control">
                    <Select
                      mode="multiple"
                      placeholder="选择文件类型"
                      value={fileTypes}
                      onChange={setFileTypes}
                      style={{ width: '100%' }}
                      allowClear
                    >
                      <Option value=".pdf">PDF</Option>
                      <Option value=".docx">Word (DOCX)</Option>
                      <Option value=".doc">Word (DOC)</Option>
                      <Option value=".txt">文本文档</Option>
                    </Select>
                  </div>
                </div>
                
                <div className="filter-row">
                  <div className="filter-label">搜索粒度:</div>
                  <div className="filter-control">
                    <Radio.Group value={granularity} onChange={(e) => setGranularity(e.target.value)}>
                      <Radio.Button value="document">整篇文档</Radio.Button>
                      <Radio.Button value="paragraph">段落</Radio.Button>
                      <Radio.Button value="sentence">句子</Radio.Button>
                    </Radio.Group>
                  </div>
                </div>
                
                <div className="filter-row">
                  <div className="filter-label">相关度阈值:</div>
                  <div className="filter-control">
                    <Slider
                      min={0.1}
                      max={0.9}
                      step={0.05}
                      value={relevanceThreshold}
                      onChange={setRelevanceThreshold}
                      marks={{
                        0.1: '低',
                        0.5: '中',
                        0.9: '高'
                      }}
                    />
                  </div>
                </div>
                
                <div className="filter-row">
                  <div className="filter-label">显示上下文:</div>
                  <div className="filter-control">
                    <Switch checked={includeContext} onChange={setIncludeContext} />
                    {includeContext && (
                      <Slider
                        min={1}
                        max={5}
                        value={contextSize}
                        onChange={setContextSize}
                        marks={{
                          1: '小',
                          3: '中',
                          5: '大'
                        }}
                        style={{ marginTop: 8 }}
                      />
                    )}
                  </div>
                </div>
                
                <div className="filter-row">
                  <div className="filter-label">结果数量:</div>
                  <div className="filter-control">
                    <Select
                      value={resultsLimit}
                      onChange={setResultsLimit}
                      style={{ width: 120 }}
                    >
                      <Option value={5}>5个</Option>
                      <Option value={10}>10个</Option>
                      <Option value={20}>20个</Option>
                      <Option value={50}>50个</Option>
                    </Select>
                  </div>
                </div>
                
                <div className="filter-actions" style={{ marginTop: 16, textAlign: 'right' }}>
                  <Button onClick={clearFilters}>重置筛选</Button>
                  <Button type="primary" onClick={handleSearch} style={{ marginLeft: 8 }}>
                    应用筛选
                  </Button>
                </div>
              </div>
            </Panel>
          </Collapse>
        )}
        
        <div className="search-results" style={{ marginTop: 20 }}>
          {loading ? (
            <div className="loading-container" style={{ textAlign: 'center', padding: 20 }}>
              <Spin tip="搜索中..." />
            </div>
          ) : (
            searchPerformed && (
              <>
                {results.length > 0 ? (
                  <>
                    <div className="results-summary" style={{ marginBottom: 16 }}>
                      找到 <Text strong>{totalResults}</Text> 个结果
                    </div>
                    <List
                      itemLayout={viewMode === 'expanded' ? "vertical" : "horizontal"}
                      size="large"
                      dataSource={results}
                      renderItem={item => (
                        <List.Item
                          key={`${item.document_id}-${item.chunk_index}`}
                          extra={viewMode === 'expanded' ? null : (
                            <Tag color={item.score > 0.8 ? 'green' : item.score > 0.6 ? 'blue' : 'orange'}>
                              相关度: {(item.score * 100).toFixed(1)}%
                            </Tag>
                          )}
                        >
                          <List.Item.Meta
                            avatar={renderFileTypeIcon(item.document?.file_type)}
                            title={
                              <Space>
                                <a href={`/documents/${item.document_id}`}>{item.document_name}</a>
                                {viewMode === 'expanded' && (
                                  <Tag color={item.score > 0.8 ? 'green' : item.score > 0.6 ? 'blue' : 'orange'}>
                                    相关度: {(item.score * 100).toFixed(1)}%
                                  </Tag>
                                )}
                                <Tag>{item.granularity === 'document' ? '文档' : 
                                      item.granularity === 'paragraph' ? '段落' : '句子'}</Tag>
                              </Space>
                            }
                            description={
                              <Space direction="vertical">
                                <Text type="secondary">文档ID: {item.document_id}</Text>
                                {item.metadata && Object.keys(item.metadata).length > 0 && (
                                  <div className="metadata-tags">
                                    {Object.entries(item.metadata).map(([key, value]) => 
                                      typeof value === 'string' && (
                                        <Tag key={key} color="cyan">{key}: {value}</Tag>
                                      )
                                    )}
                                  </div>
                                )}
                              </Space>
                            }
                          />
                          <div className="search-result-text">
                            <Paragraph 
                              ellipsis={viewMode === 'compact' ? { rows: 3, expandable: true } : false}
                            >
                              {renderMarkdown(highlightText(item.text, query))}
                            </Paragraph>
                            
                            {includeContext && item.context && (
                              <div className="context-preview" style={{ 
                                marginTop: 8, 
                                padding: 8, 
                                background: '#f5f5f5', 
                                borderRadius: 4,
                                fontSize: '0.9em',
                                borderLeft: '3px solid #1890ff'
                              }}>
                                <Paragraph 
                                  ellipsis={viewMode === 'compact' ? { rows: 3, expandable: true } : false}
                                >
                                  {renderMarkdown(item.context)}
                                </Paragraph>
                              </div>
                            )}
                          </div>
                        </List.Item>
                      )}
                    />
                  </>
                ) : (
                  <Empty description="没有找到相关文档" />
                )}
              </>
            )
          )}
        </div>
      </Card>
    </div>
  );
};

export default AdvancedDocumentSearch;