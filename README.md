# 转行帮 CareerChange Helper

Multi-Agent 转行助手后端 — 从职场资产评估到简历精修的全流程 AI 工作流。

## Architecture

```
用户输入 (简历 + 背景)
        │
        ▼
┌───────────────────────────────────┐
│  Agent 1: 能力画像专家             │  Anthropic Claude
│  Profile Analyzer                 │  (硬技能 + 可迁移能力 + 性格 + 约束)
└──────────────┬────────────────────┘
               ▼
┌───────────────────────────────────┐
│  Agent 2: 市场匹配引擎             │  Anthropic Claude
│  Market Matcher                   │  (3-5个方向 + 缺口 + 壁垒 + 薪资)
└──────────────┬────────────────────┘
               ▼
┌───────────────────────────────────┐
│  Agent 3: 路径规划架构师            │  Anthropic Claude
│  Strategy Architect               │  (分阶段行动 + 资源 + 里程碑)
└──────────────┬────────────────────┘
               ▼
┌───────────────────────────────────┐
│  Agent 4: 简历润色助手             │  Anthropic Claude
│  CV Optimizer                     │  (逐段对比 + ATS优化 + 叙事重构)
└──────────────┬────────────────────┘
               ▼
┌───────────────────────────────────┐
│  Agent 5: 模拟面试专家             │  Anthropic Claude
│  Interview Simulator              │  (3轮追问 + 专业度缺口 + 备面优先级)
└───────────────────────────────────┘
```

## Quick Start

```bash
git clone https://github.com/songqining-afk/career-change-helper.git
cd career-change-helper

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API key (ANTHROPIC_API_KEY)

cp config/models.yaml.example config/models.yaml
# (Optional) Edit config/models.yaml to customize model routing
```

### Web UI（推荐）

**一键启动：**
```bash
bash scripts/start.sh
```

访问 `http://localhost:8000`，通过 Web 界面完成全流程分析 + 模拟面试。

**开发模式（前后端分离）：**
```bash
# Terminal 1: 启动后端
uvicorn src.app:app --reload --port 8000

# Terminal 2: 启动前端开发服务器
cd web
npm install
npm run dev  # 访问 http://localhost:3000
```

### CLI 交互式分析

```bash
python3 src/cli_interview.py
```

交互式终端分析：输入简历 → 4-agent 逐步分析 → 每个 Agent 支持无限轮次修改 → 简历改写对话。

**特性：**
- 每个 Agent 输出后，可以无限轮次提供修改意见，直到满意为止
- 回车确认后进入下一个 Agent
- 断点续跑：中途退出后可从上次位置继续

### REST API

```bash
uvicorn src.app:app --reload --port 8000
```

## API

```
POST /api/analyze              — 4-agent 分析 pipeline
POST /api/analyze/step/{1-4}   — 单个 agent 调试
POST /api/interview/start      — 开始模拟面试
POST /api/interview/reply      — 提交回答
GET  /api/interview/{id}       — 面试状态
GET  /health                   — Health check
```

Request body:
```json
{
  "resume_text": "简历内容...",
  "background": "补充背景（可选）",
  "constraints": "约束条件（可选）",
  "target_direction": "期望方向（可选）"
}
```

## Project Structure

```
src/
  agents/
    profile_analyzer.py     Agent 1: 能力画像专家
    market_matcher.py       Agent 2: 市场匹配引擎
    strategy_architect.py   Agent 3: 路径规划架构师
    cv_optimizer.py         Agent 4: 简历润色助手
    interview_simulator.py  Agent 5: 模拟面试专家
    base.py                 Agent 基类
  schemas/models.py         Pydantic 数据模型（Agent 间的契约）
  prompts/                  System prompts（每个 Agent 的指令）
  llm/client.py             LLM 客户端（Anthropic SDK）
  pipeline.py               流水线编排器（Agent 1-4）
  cli_interview.py          CLI 文字面试入口（Agent 5 交互）
  app.py                    FastAPI REST API 入口
config/                     模型路由配置
tests/                      测试套件
```

## LLM

All agents use **Anthropic Claude Opus 4.7** (official SDK, adaptive thinking).

**Automatic fallback**: If Claude doesn't respond within **30 seconds** (configurable via `CLAUDE_TIMEOUT`), the system automatically switches to **DeepSeek** for that request. This ensures fast response times even when Claude is slow.

To configure:
```bash
# .env
CLAUDE_TIMEOUT=30  # seconds (default: 30)
DEEPSEEK_API_KEY=your_key_here  # enables fallback
```

## License

MIT
