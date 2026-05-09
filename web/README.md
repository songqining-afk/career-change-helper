# 转行帮 Web UI

React + Vite + Tailwind CSS 前端界面。

## 功能

- **首页输入**: 简历 + 背景 + 约束条件 + 期望方向
- **交互式分析流程**: 4 步逐步分析，每步支持无限轮次修改
  - 画像师 (能力画像)
  - 探路者 (市场匹配 + 方向选择)
  - 规划局 (路径规划)
  - 磨刀石 (简历润色)
- **模拟面试**: 3 轮对话式面试 + 实时反馈 + 最终报告

## 开发

```bash
cd web
npm install
npm run dev
```

前端默认运行在 `http://localhost:3000`，API 请求会自动代理到 `http://localhost:8000`。

## 部署

```bash
npm run build
```

构建产物在 `dist/` 目录，可以用任何静态服务器托管（Nginx / Vercel / Netlify）。

## 技术栈

- React 19 + TypeScript
- Vite 8
- Tailwind CSS 4
- React Router 7
- Lucide Icons
