# 持久记忆 + 知识库/RAG + Web UI 实施计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 为转行帮增加三大能力：持久记忆（记住用户转行进度和偏好）、知识库/RAG（上传行业报告和岗位JD辅助分析）、Web UI（降低使用门槛）。

**Architecture:**
- 记忆系统：SQLite 存储用户画像 + 转行进度 + 偏好，每次 pipeline 运行自动更新，Agent 可读取历史上下文
- 知识库/RAG：用户上传 PDF/TXT/MD → 文本切片 → 嵌入向量 → ChromaDB 本地向量库 → Agent 2/3 自动检索相关行业数据
- Web UI：React + Vite 单页应用，通过现有 FastAPI 后端通信，支持简历输入、文件上传、实时进度、面试对话

**Tech Stack:**
- 后端：FastAPI (已有) + SQLite (aiosqlite) + ChromaDB + sentence-transformers (嵌入)
- 前端：React 18 + Vite + TailwindCSS + shadcn/ui

**依赖新增：**
```
aiosqlite>=0.20.0
chromadb>=0.5.0
sentence-transformers>=3.0.0
python-multipart>=0.0.9
```

---

## Phase 1: 持久记忆系统

### Task 1: 创建 SQLite 数据库层

**Objective:** 建立用户记忆的存储基础

**Files:**
- Create: `src/memory/__init__.py`
- Create: `src/memory/database.py`
- Create: `src/memory/models.py`

**src/memory/models.py** — Pydantic 模型：
```python
from pydantic import BaseModel, Field
from datetime import datetime

class UserMemory(BaseModel):
    """用户持久记忆 — 跨会话保留。"""
    user_id: str
    resume_text: str = ""
    background: str = ""
    constraints: str = ""
    preferred_directions: list[str] = Field(default_factory=list)
    # 最近一次分析结果摘要
    last_profile_summary: str = ""
    last_matched_industries: list[str] = Field(default_factory=list)
    last_plan_target: str = ""
    # 面试历史
    interview_count: int = 0
    avg_readiness_score: float = 0.0
    recurring_gaps: list[str] = Field(default_factory=list)
    # 元数据
    created_at: str = ""
    updated_at: str = ""

class AnalysisRecord(BaseModel):
    """单次分析的完整记录。"""
    record_id: str
    user_id: str
    timestamp: str
    user_input_json: str
    pipeline_result_json: str
    interview_report_json: str = ""
```

**src/memory/database.py** — 异步 SQLite 操作：
- `init_db()` — 建表
- `save_memory(user_id, memory)` — upsert 用户记忆
- `load_memory(user_id)` → UserMemory | None
- `save_analysis(record)` — 保存分析记录
- `list_analyses(user_id, limit=10)` → list[AnalysisRecord]

### Task 2: Pipeline 集成记忆

**Objective:** pipeline 运行前读取记忆、运行后更新记忆

**Files:**
- Modify: `src/pipeline.py` — 增加 memory 参数
- Modify: `src/app.py` — API 增加 user_id 参数，调用记忆

**改动要点：**
- `UserInput` 增加 `user_id: str = "default"`
- `run_pipeline()` 开头调用 `load_memory()`，将历史上下文注入 Agent 1 的 user_message
- pipeline 结束后调用 `save_memory()` 更新摘要
- API `/api/analyze` 自动关联 user_id

### Task 3: Agent 感知记忆

**Objective:** Agent 1 和 Agent 3 能利用历史数据做更精准的分析

**Files:**
- Modify: `src/agents/profile_analyzer.py` — 注入历史画像对比
- Modify: `src/agents/strategy_architect.py` — 注入历史进度

**改动要点：**
- ProfileAnalyzer.analyze() 接受可选 `previous_profile: str` 参数
- StrategyArchitect.analyze() 接受可选 `history_context: str` 参数
- 在 user_message 中追加 `## 历史记录` 段落

---

## Phase 2: 知识库/RAG

### Task 4: ChromaDB 知识库管理

**Objective:** 用户可上传文档，系统自动切片、嵌入、存储

**Files:**
- Create: `src/knowledge/__init__.py`
- Create: `src/knowledge/store.py`
- Create: `src/knowledge/chunker.py`

**src/knowledge/chunker.py:**
- `extract_text(file_path)` — 支持 .pdf (PyPDF2), .txt, .md
- `chunk_text(text, chunk_size=500, overlap=50)` → list[str]

**src/knowledge/store.py:**
- `KnowledgeStore` 类，封装 ChromaDB
- `add_document(user_id, filename, chunks)` — 嵌入并存储
- `search(user_id, query, top_k=5)` → list[dict] (text + score)
- `list_documents(user_id)` → list[str]
- `delete_document(user_id, filename)`

### Task 5: RAG 集成到 Agent

**Objective:** Agent 2 (市场匹配) 和 Agent 3 (路径规划) 自动检索知识库

**Files:**
- Modify: `src/agents/market_matcher.py`
- Modify: `src/agents/strategy_architect.py`
- Modify: `src/pipeline.py`

**改动要点：**
- pipeline 在调用 Agent 2 前，用 profile.summary + 各 industry 关键词检索知识库
- 检索结果作为 `## 参考资料（来自用户上传的行业报告/JD）` 注入 user_message
- Agent 3 同理，用 chosen_target 检索

### Task 6: 文档上传 API

**Objective:** 提供文件上传和知识库管理的 REST API

**Files:**
- Modify: `src/app.py`

**新增端点：**
```
POST /api/knowledge/upload     — 上传文件 (multipart/form-data)
GET  /api/knowledge/documents  — 列出用户文档
DELETE /api/knowledge/{filename} — 删除文档
POST /api/knowledge/search     — 手动搜索知识库
```

---

## Phase 3: Web UI

### Task 7: 前端项目初始化

**Objective:** 搭建 React + Vite + TailwindCSS 项目骨架

**Files:**
- Create: `web/` 目录 (Vite 项目)

**命令：**
```bash
cd ~/career-change-helper
npm create vite@latest web -- --template react
cd web
npm install tailwindcss @tailwindcss/vite
npm install lucide-react
```

### Task 8: API 客户端层

**Objective:** 封装所有后端 API 调用

**Files:**
- Create: `web/src/api/client.js`

**封装：**
- `analyzeResume(data)` → POST /api/analyze
- `uploadDocument(file, userId)` → POST /api/knowledge/upload
- `listDocuments(userId)` → GET /api/knowledge/documents
- `startInterview(sessionId)` → POST /api/interview/start
- `replyInterview(sessionId, answer)` → POST /api/interview/reply
- `getUserMemory(userId)` → GET /api/memory/{user_id}

### Task 9: 核心页面 — 简历分析

**Objective:** 主页面：输入简历 → 4-agent 分析 → 展示结果

**Files:**
- Create: `web/src/pages/AnalyzePage.jsx`
- Create: `web/src/components/ResumeInput.jsx`
- Create: `web/src/components/PipelineResult.jsx`
- Create: `web/src/components/StepProgress.jsx`

**UI 结构：**
- 左侧：简历输入 textarea + 背景/约束/方向输入
- 右侧：分析结果卡片（4 个 Agent 的输出，折叠展开）
- 顶部：进度条（Agent 1 → 2 → 3 → 4）

### Task 10: 知识库管理页面

**Objective:** 上传/管理文档的界面

**Files:**
- Create: `web/src/pages/KnowledgePage.jsx`
- Create: `web/src/components/FileUpload.jsx`
- Create: `web/src/components/DocumentList.jsx`

### Task 11: 模拟面试页面

**Objective:** 聊天式面试界面

**Files:**
- Create: `web/src/pages/InterviewPage.jsx`
- Create: `web/src/components/ChatBubble.jsx`

**UI：** 类似聊天界面，面试官问题在左，用户回答在右，实时反馈卡片

### Task 12: 用户记忆/进度页面

**Objective:** 展示用户的转行进度和历史

**Files:**
- Create: `web/src/pages/ProfilePage.jsx`

**UI：** 用户画像摘要 + 历史分析列表 + 面试统计 + 常见缺口

### Task 13: 路由和布局

**Objective:** 整合所有页面

**Files:**
- Modify: `web/src/App.jsx`
- Create: `web/src/components/Layout.jsx`
- Create: `web/src/components/Sidebar.jsx`

**路由：**
- `/` — 简历分析（主页）
- `/knowledge` — 知识库
- `/interview` — 模拟面试
- `/profile` — 我的进度

### Task 14: 后端静态文件服务 + 启动脚本

**Objective:** FastAPI 同时服务 API 和前端构建产物

**Files:**
- Modify: `src/app.py` — 添加 StaticFiles mount
- Create: `scripts/start.sh` — 一键启动（build前端 + 启动后端）

---

## 执行顺序

Phase 1 (Task 1-3) → Phase 2 (Task 4-6) → Phase 3 (Task 7-14)

每个 Phase 完成后可独立验证：
- Phase 1 完成后：CLI 和 API 已有记忆能力
- Phase 2 完成后：上传文档后分析结果更精准
- Phase 3 完成后：完整 Web 体验
