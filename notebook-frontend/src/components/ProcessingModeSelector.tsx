import React from 'react';
import { RadioGroup, Radio, Typography, Card, Space, Icon } from '@douyinfe/semi-ui';
import { IconSearch, IconTree } from '@douyinfe/semi-icons';

interface ProcessingModeSelectorProps {
  value: 'rag' | 'graph';
  onChange: (value: 'rag' | 'graph') => void;
  disabled?: boolean;
}

const { Title, Text } = Typography;

const ProcessingModeSelector: React.FC<ProcessingModeSelectorProps> = ({
  value,
  onChange,
  disabled = false
}) => {
  return (
    <Card 
      title="处理模式选择" 
      style={{ marginBottom: 16 }}
      bodyStyle={{ padding: '16px' }}
    >
      <RadioGroup 
        value={value} 
        onChange={(e) => onChange(e.target.value)}
        direction="vertical"
        disabled={disabled}
      >
        <div style={{ marginBottom: 16 }}>
          <Radio value="rag">
            <Space align="center">
              <IconSearch style={{ fontSize: 18, color: '#3b82f6' }} />
              <div>
                <Title heading={5} style={{ margin: 0, color: '#1f2937' }}>
                  RAG 向量检索模式
                </Title>
                <Text type="tertiary" size="small">
                  将文档分块并生成向量嵌入，支持语义相似度搜索和问答
                </Text>
              </div>
            </Space>
          </Radio>
        </div>
        
        <div>
          <Radio value="graph">
            <Space align="center">
              <IconTree style={{ fontSize: 18, color: '#10b981' }} />
              <div>
                <Title heading={5} style={{ margin: 0, color: '#1f2937' }}>
                  Graph 知识图谱模式
                </Title>
                <Text type="tertiary" size="small">
                  从文档中抽取实体和关系，构建结构化知识图谱
                </Text>
              </div>
            </Space>
          </Radio>
        </div>
      </RadioGroup>
      
      <div style={{ marginTop: 12, padding: '8px 12px', backgroundColor: '#f8fafc', borderRadius: 6 }}>
        <Text size="small" type="tertiary">
          💡 提示：RAG模式适合问答和检索，Graph模式适合关系分析和知识发现
        </Text>
      </div>
    </Card>
  );
};

export default ProcessingModeSelector; 