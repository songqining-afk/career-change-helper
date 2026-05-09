# 转行帮 CareerChange Helper

Multi-Agent 转行助手 — 5 个 AI Agent 协作完成从能力画像到模拟面试的全流程。

## 技术栈

- **后端**: Python 3.10+ / FastAPI / Pydantic v2
- **LLM**: Anthropic Claude Opus 4.7 (primary) + DeepSeek (fallback)
- **前端**: React 19 + TypeScript + Vite + TailwindCSS 4
- **存储**: SQLite (记忆) + ChromaDB (知识库向量检索)
- **SDK**: anthropic (官方 SDK, async)

## 目录约定

```
src/                 后端源码
  agents/            5 个 Agent 实现（继承 BaseAgent）
  llm/              LLM 客户端（Claude + DeepSeek fallback）
  memory/           持久记忆系统（SQLite）
  knowledge/        知识库/RAG（ChromaDB）
  schemas/          Pydantic 数据模型（Agent 间契约）
  prompts/          System prompts（.md 文件，每个 Agent 一份）
  tools/            工具函数
  app.py            FastAPI 入口
  pipeline.py       流水线编排（Agent 1-4 顺序执行）
  cli_interview.py  CLI 交互入口
  interview_store.py 面试会话存储
web/                 前端源码（React + Vite）
  src/pages/        页面组件
  src/components/   通用组件
  src/lib/          API 客户端等工具
tests/               pytest 测试
config/              模型路由配置（models.yaml 不进 git）
scripts/             启动脚本
docs/                设计文档、流程说明、历史决策记录
data/                运行时数据（不进 git）
```

## 开发命令

```bash
# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 启动后端（开发模式）
uvicorn src.app:app --reload --port 8000

# 启动前端（开发模式）
cd web && npm run dev

# 一键启动（构建前端 + 启动后端）
bash scripts/start.sh

# CLI 交互模式
python -m src.cli_interview

# 运行测试
python -m pytest tests/ -x

# 语法检查
python -c "import ast; ast.parse(open('src/app.py').read())"
```

## 验证清单（改完代码必跑）

1. `python -c "from src.app import app; print('OK')"` — import 不报错
2. `python -m pytest tests/ -x` — 测试通过
3. 如果改了前端：`cd web && npm run build` — 构建不报错

## 代码风格

- Python: 类型注解、async/await、Pydantic BaseModel
- 导入路径统一用 `from src.xxx import ...`（绝对导入）
- Agent 新增：继承 `BaseAgent`，在 `src/prompts/` 放 system prompt
- Schema 变更：改 `src/schemas/models.py`，所有 Agent 共享
- 前端：TypeScript strict，组件放 pages/ 或 components/

## 环境变量（.env）

必填：
- `ANTHROPIC_API_KEY` — Claude API 密钥

可选：
- `CLAUDE_TIMEOUT` — Claude 超时秒数（默认 30）
- `DEEPSEEK_API_KEY` — DeepSeek fallback 密钥
- `DEEPSEEK_BASE_URL` — DeepSeek 端点
- `DEEPSEEK_MODEL` — DeepSeek 模型名

## 注意事项

- `config/models.yaml` 含 API 配置，不进 git（有 .example 模板）
- `data/` 目录运行时自动创建，不进 git
- `web/dist/` 是构建产物，不进 git
- Agent prompt 修改后无需重启，下次调用自动加载新文件
- 测试中 mock LLM 调用，不要在测试里打真实 API
