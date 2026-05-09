# 转行帮 Web UI 使用指南

## 快速启动

### 方式一：一键启动（推荐）

```bash
./scripts/start.sh
```

这个脚本会自动：
1. 构建前端（`npm run build`）
2. 启动后端（FastAPI 在 8000 端口）

启动后访问：**http://localhost:8000**

### 方式二：分别启动（开发模式）

**终端 1 — 后端：**
```bash
source .venv/bin/activate
uvicorn src.app:app --reload --port 8000
```

**终端 2 — 前端：**
```bash
cd web
npm run dev
```

开发模式下访问：**http://localhost:3000**（Vite 会自动代理 API 请求到 8000 端口）

---

## 功能说明

### 1. 首页（简历分析）

- 输入简历内容（必填）
- 可选：补充背景、约束条件、期望方向
- 点击「开始分析」进入 4-agent 流水线

### 2. 分析页面（交互式）

4 个 AI 顾问逐步分析：
1. **画像师** — 提取能力画像（硬技能、可迁移技能、性格特征）
2. **探路者** — 市场匹配（推荐 3 个转行方向 + 匹配度）
3. **规划局** — 路径规划（分阶段行动计划 + 风险提示）
4. **磨刀石** — 简历润色（针对目标岗位优化简历）

每一步完成后：
- 可以输入修改意见，AI 会重新生成
- 或直接确认进入下一步

### 3. 模拟面试

完成分析后可进入模拟面试：
- 3 轮问答
- 每轮回答后实时反馈（评分 + 优缺点 + 建议）
- 最终生成面试报告（总体评分 + 优势 + 待提升 + 下一步建议）

### 4. 知识库

上传行业报告、岗位 JD 等文档（支持 PDF/TXT/Markdown）：
- AI 会在分析时自动检索相关内容
- 可以手动搜索知识库
- 支持删除文档

### 5. 我的进度

查看：
- 用户画像（年龄、城市、学历、当前职位、目标方向等）
- 偏好记录（明确偏好 vs 推断偏好）
- 历史事件（分析、面试、方向选择等）

---

## 技术栈

**后端：**
- FastAPI（API + 静态文件服务）
- SQLite（持久记忆）
- ChromaDB（知识库向量检索）
- OpenRouter/Claude（LLM）

**前端：**
- React 19 + TypeScript
- Vite（构建工具）
- TailwindCSS 4（样式）
- React Router（路由）

---

## 目录结构

```
career-change-helper/
├── src/                    # 后端代码
│   ├── app.py             # FastAPI 主应用（含静态文件服务）
│   ├── pipeline.py        # 4-agent 流水线
│   ├── agents/            # 5 个 Agent
│   ├── memory/            # 持久记忆（SQLite）
│   └── knowledge/         # 知识库（ChromaDB）
├── web/                   # 前端代码
│   ├── src/
│   │   ├── pages/         # 5 个页面
│   │   ├── components/    # 组件
│   │   └── lib/api.ts     # API 客户端
│   └── dist/              # 构建产物（由 FastAPI 服务）
├── data/                  # 数据目录
│   ├── memory.db          # SQLite 数据库
│   ├── uploads/           # 上传的文档
│   └── chroma/            # ChromaDB 向量库
└── scripts/
    └── start.sh           # 一键启动脚本
```

---

## 常见问题

**Q: 启动后访问 8000 端口显示 404？**

A: 确保前端已构建（`cd web && npm run build`），或使用 `./scripts/start.sh` 自动构建。

**Q: 上传文档失败？**

A: 检查文件格式（仅支持 .pdf/.txt/.md），确保文件不为空。

**Q: 分析过程中断？**

A: 检查 `.env` 中的 LLM API 配置（OpenRouter/Claude API Key）。

**Q: 如何清空历史记录？**

A: 删除 `data/memory.db` 和 `data/chroma/` 目录。

---

## 下一步优化

- [ ] 用户认证（多用户支持）
- [ ] 导出分析报告（PDF/Markdown）
- [ ] 知识库文档预览
- [ ] 面试录音转文字
- [ ] 移动端适配
