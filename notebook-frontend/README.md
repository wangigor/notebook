# Notebook AI 前端

基于 Vite + React + TypeScript + Semi Design 构建的现代化知识库前端应用。

## 技术栈

- **Vite**: 快速的前端构建工具
- **React 19**: 用于构建用户界面的JavaScript库
- **TypeScript**: JavaScript的超集，添加了类型系统
- **Semi Design**: 字节跳动开源的企业级设计系统和UI组件库
- **TanStack Query**: 用于数据获取和缓存
- **Axios**: 基于Promise的HTTP客户端

## 快速开始

### 通过启动脚本运行

最简单的方式是使用提供的启动脚本:

```bash
./start.sh
```

这将检查您的环境、安装依赖并启动开发服务器。

### 手动运行

如果您想手动运行项目:

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 项目结构

```
notebook-frontend/
├── public/               # 静态资源
├── src/                  # 源代码
│   ├── api/              # API服务
│   ├── components/       # UI组件
│   ├── types/            # TypeScript类型定义
│   ├── App.tsx           # 主应用组件
│   ├── main.tsx          # 应用入口
│   └── index.css         # 全局样式
├── .gitignore            # Git忽略文件
├── package.json          # 项目依赖和脚本
├── tsconfig.json         # TypeScript配置
└── vite.config.ts        # Vite配置
```

## 模拟数据模式

项目默认启用了模拟数据模式，可以在没有后端API的情况下正常工作。此模式下：

- 会自动创建示例会话和初始消息
- 所有API调用将返回模拟数据
- 对话功能可以正常使用，但回复内容是预设的

如需禁用模拟数据模式，请编辑 `src/api/api.ts` 文件中的 `MOCK_DATA.enabled` 设置为 `false`。

## 已知问题

### React 19 相关警告

由于项目使用了React 19，可能会在控制台中看到如下警告：

```
Accessing element.ref was removed in React 19. ref is now a regular prop.
```

这是因为React 19对ref API进行了更改，这些警告来自于第三方库尚未完全适配React 19。这些警告不会影响应用功能，可以安全忽略。

## 连接后端

默认情况下，前端应用会尝试连接到 `http://localhost:8001/api`。如果您的后端在不同的地址运行，请修改 `vite.config.ts` 中的代理配置。

## 构建生产版本

要构建用于生产环境的优化版本:

```bash
npm run build
```

构建完成后，您可以在 `dist` 目录找到生成的文件。
