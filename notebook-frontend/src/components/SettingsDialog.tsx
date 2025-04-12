import { FC, useState, useEffect } from 'react';
import { Modal, Form, InputNumber, Toggle, Spin, Toast } from '@douyinfe/semi-ui';
import { settings } from '../api/api';

interface SettingsDialogProps {
  visible: boolean;
  onClose: () => void;
}

const SettingsDialog: FC<SettingsDialogProps> = ({ visible, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<any>({
    memory_config: {
      max_token_limit: 2000,
      return_messages: true,
      return_source_documents: true,
      k: 5
    }
  });

  // 加载设置
  useEffect(() => {
    if (visible) {
      loadSettings();
    }
  }, [visible]);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await settings.getConfig();
      if (response.success) {
        setConfig(response.data);
      } else {
        Toast.error('加载配置失败: ' + response.message);
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
      Toast.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await settings.updateConfig(config);
      if (response.success) {
        Toast.success('配置已更新');
        onClose();
      } else {
        Toast.error('更新配置失败: ' + response.message);
      }
    } catch (error) {
      console.error('Failed to update settings:', error);
      Toast.error('更新配置失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title="系统设置"
      visible={visible}
      onOk={handleSave}
      onCancel={onClose}
      okText="保存"
      cancelText="取消"
      okButtonProps={{ loading: saving }}
      cancelButtonProps={{ disabled: saving }}
      width={600}
    >
      {loading ? (
        <div className="flex justify-center p-8">
          <Spin size="large" />
        </div>
      ) : (
        <Form labelPosition="left" labelWidth={180}>
          <Form.Section text="记忆设置">
            <Form.InputNumber
              field="max_token_limit"
              label="最大Token数量"
              initValue={config.memory_config?.max_token_limit || 2000}
              onChange={(value) => 
                setConfig({
                  ...config,
                  memory_config: {
                    ...config.memory_config,
                    max_token_limit: value
                  }
                })
              }
              min={100}
              max={10000}
              step={100}
              style={{ width: '100%' }}
            />
            
            <Form.InputNumber
              field="k"
              label="返回相似文档数"
              initValue={config.memory_config?.k || 5}
              onChange={(value) => 
                setConfig({
                  ...config,
                  memory_config: {
                    ...config.memory_config,
                    k: value
                  }
                })
              }
              min={1}
              max={20}
              step={1}
              style={{ width: '100%' }}
            />
            
            <Form.Switch
              field="return_source_documents"
              label="返回源文档"
              initValue={config.memory_config?.return_source_documents || true}
              onChange={(checked) => 
                setConfig({
                  ...config,
                  memory_config: {
                    ...config.memory_config,
                    return_source_documents: checked
                  }
                })
              }
            />
          </Form.Section>
        </Form>
      )}
    </Modal>
  );
};

export default SettingsDialog; 