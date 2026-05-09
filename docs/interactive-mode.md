# 交互式流程说明

## 核心改动

### 原来的设计
- 4 个 Agent 同时并行执行（非交互式）
- 用户只能在最后看到所有结果
- Agent 之间没有用户反馈传递

### 新的设计
- **顺序执行**：Agent 1 → 用户确认 → Agent 2 → 用户确认 → ... → Agent 5
- **记忆传承**：每个 Agent 都能看到：
  - 前面所有 Agent 的分析结果
  - 用户对每个 Agent 的反馈
  - 3 层持久记忆（用户档案 + 事件时间线 + 偏好）

## 使用方式

### 1. CLI 交互式模式（推荐）

```bash
cd ~/career-change-helper
source .venv/bin/activate
python -m src.cli_interview
```

**流程**：
1. 输入简历 + 背景信息
2. Agent 1 (能力画像) 分析 → 显示结果 → 用户确认/反馈
3. Agent 2 (市场匹配) 分析 → 显示推荐方向列表 → **用户选择数字或自定义输入**
4. Agent 3 (路径规划) 基于用户选择的方向规划 → 显示结果 → 用户确认/反馈
5. Agent 4 (简历润色) 分析 → 显示结果 → **进入多轮简历内容改写对话**

**Agent 2 交互示例**：
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  请选择你想走的转行方向
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. 金融科技 · 数据分析师 — 匹配度 85%
     你的量化背景和 Python 技能高度匹配
     需补: SQL, Tableau, 业务理解

  2. 互联网 · 产品经理 — 匹配度 72%
     你的用户研究经验可迁移
     需补: PRD撰写, 原型设计, 敏捷开发

  3. 咨询 · 战略分析师 — 匹配度 68%
     ...

输入数字选择，或直接输入你想要的方向（如'产品经理'）
直接回车 = 选择第 1 个推荐
> 2

✓ 已选择: 互联网 · 产品经理
```

或自定义输入：
```
> AI 工程师

✓ 自定义方向: AI 工程师
Agent 3 会基于你的选择进行路径规划
```

**Agent 4 多轮改写示例**：
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  💡 简历内容改写助手
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
你可以粘贴任何简历相关内容（工作经历、项目经历、教育背景、
技能描述、自我评价等），我会帮你改写成适合目标岗位的版本。
输入 'q' 或 '退出' 结束对话。

📋 粘贴你想改写的简历内容（多行输入，空行结束）:
> 2020-2023 在某互联网公司做运营，负责用户增长
> 通过各种活动提升了用户活跃度
> 

正在改写...

──────────────────────────────────────────────────
  ✏️  改写结果
──────────────────────────────────────────────────

**用户增长运营 | 某互联网公司 | 2020.01 - 2023.12**

- **用户增长策略设计与执行**：主导 3 个季度增长活动，通过数据分析识别高价值用户群体，设计精准触达方案，实现新增用户 +35%（月均 12K → 16.2K）
- **活跃度提升项目**：搭建用户分层运营体系，针对沉默用户设计召回策略（EDM + Push + 社群），7 日留存率从 28% 提升至 41%
- **数据驱动决策**：使用 SQL + Python 分析用户行为漏斗，识别关键流失节点，优化产品体验，转化率提升 18%

──────────────────────────────────────────────────

你可以:
  • 粘贴下一段简历内容（工作经历、教育、技能等）
  • 输入修改意见（如'更突出领导力'、'语气再专业一些'）
  • 输入 'q' 退出

📋 继续粘贴新内容，或输入修改意见:
> 再加一些产品思维相关的内容

正在改写...

──────────────────────────────────────────────────
  ✏️  改写结果
──────────────────────────────────────────────────

**用户增长运营 | 某互联网公司 | 2020.01 - 2023.12**

- **用户增长策略设计与执行**：主导 3 个季度增长活动，通过数据分析识别高价值用户群体，设计精准触达方案，实现新增用户 +35%（月均 12K → 16.2K）
- **产品优化与用户体验提升**：深度参与产品迭代，基于用户反馈和行为数据提出 15+ 功能优化建议，其中 8 项被采纳上线，核心功能使用率提升 22%
- **活跃度提升项目**：搭建用户分层运营体系，针对沉默用户设计召回策略（EDM + Push + 社群），7 日留存率从 28% 提升至 41%
- **数据驱动决策**：使用 SQL + Python 分析用户行为漏斗，识别关键流失节点，协同产品团队优化注册流程，转化率提升 18%

──────────────────────────────────────────────────

你可以:
  • 粘贴下一段简历内容（工作经历、教育、技能等）
  • 输入修改意见（如'更突出领导力'、'语气再专业一些'）
  • 输入 'q' 退出

📋 继续粘贴新内容，或输入修改意见:
> q

简历改写结束。祝你转行顺利！🚀
```

**断点续跑**：
- 每个 Agent 完成后自动保存状态到 `~/.career-helper/sessions/<session_id>.json`
- 中途退出（Ctrl+C 或连接断开）后，重新运行会提示：
  ```
  检测到 1 个未完成的分析会话：
    1. Session abc12345... — 已完成 Agent [1, 2] — 2026-05-08T03:52:10
  
  是否从最近的会话继续？(y/n)
  ```
- 选择 `y` 会从 Agent 3 继续，跳过已完成的 Agent 1-2
- 所有 Agent 完成后自动删除 checkpoint 文件

**用户反馈示例**：
- Agent 1 后："我更擅长数据分析，不太喜欢纯技术岗"
- Agent 3 后："6 个月太长了，能不能压缩到 3 个月"
- Agent 4 后："简历太学术了，能不能更接地气"

### 2. API 交互式模式

#### 初始化会话
```bash
curl -X POST http://localhost:8000/api/analyze/interactive/start \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": {
      "resume_text": "...",
      "background": "...",
      "constraints": "...",
      "target_direction": "..."
    }
  }'
```

返回：
```json
{
  "session_id": "abc123def456",
  "message": "Interactive pipeline initialized..."
}
```

#### 执行单步
```bash
curl -X POST http://localhost:8000/api/analyze/interactive/step \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc123def456",
    "step": 1,
    "user_feedback": ""
  }'
```

返回：
```json
{
  "success": true,
  "step": 1,
  "agent_name": "能力画像专家",
  "result": { ... },
  "duration_s": 3.2
}
```

#### 带反馈执行下一步
```bash
curl -X POST http://localhost:8000/api/analyze/interactive/step \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc123def456",
    "step": 2,
    "user_feedback": "我更擅长数据分析，不太喜欢纯技术岗"
  }'
```

#### 完成并保存
```bash
curl -X POST http://localhost:8000/api/analyze/interactive/finalize?session_id=abc123def456
```

### 3. 非交互式模式（原有 API，保持兼容）

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "resume_text": "...",
    "background": "...",
    "constraints": "...",
    "target_direction": "..."
  }'
```

一次性跑完 4 个 Agent，无用户交互。

## 技术实现

### 核心函数（`src/pipeline.py`）

1. **`init_interactive_pipeline(user_input)`**
   - 初始化交互式 pipeline 状态
   - 加载 3 层记忆（用户档案 + 事件 + 偏好）
   - 返回 `InteractivePipelineState` 对象

2. **`run_interactive_step(state, step, user_feedback)`**
   - 执行单个 Agent（1-4）
   - 将 `user_feedback` 追加到 `feedback_history`
   - 返回 `(success, result, error)`

3. **`finalize_interactive_pipeline(state)`**
   - 组装最终结果
   - 保存到数据库（3 层记忆 + 分析记录）
   - 返回 `PipelineRun` 对象

### 记忆传承机制

每个 Agent 收到的 `memory_context` 包含：

```
【用户档案】
姓名: 张三
年龄: 28
当前职位: 产品经理
核心优势: 数据分析, 用户研究
...

【转行时间线】
- [2026-05-01] 完成第 1 次分析 → 洞察: 适合数据产品方向
- [2026-04-20] 模拟面试准备度 75/100 → 洞察: 需加强技术深度

【用户偏好】
- [明确] industry: 金融科技
- [推断] workstyle: 远程优先

【用户在本次分析中的反馈记录】
- 能力画像专家阶段，用户反馈: 我更擅长数据分析，不太喜欢纯技术岗
- 市场匹配引擎阶段，用户反馈: 我对金融科技方向更感兴趣
```

## 修复记录

### 2026-05-08 修复 CLI 字段映射错误

**问题**：Agent 1 完成后程序崩溃退出到 shell

**原因**：`print_result_summary()` 访问了不存在的字段名

**修复**：
- `TalentProfile`: `core_competencies` → `hard_skills`, `personality_tags` → `personality`, `gaps` → `constraints`
- `IndustryMatch`: `market_insights` → `market_insight`, `reason` → `rationale`
- `TransitionPlan`: `risks` → `risk_factors`, `phase.name` → `phase.title`
- `PolishedResume`: `headline` → `target_role`, `summary` → `overall_narrative`, `key_changes` → `sections[].changes_made`, `ats_keywords` → `keywords_added`

## 测试

```bash
cd ~/career-change-helper
source .venv/bin/activate

# 测试 CLI
python -m src.cli_interview

# 测试 API
uvicorn src.app:app --reload --port 8000
```

## 注意事项

1. **API 会话存储**：当前使用内存字典 `_interactive_sessions`，生产环境建议用 Redis
2. **会话过期**：建议添加 TTL（如 30 分钟无操作自动清理）
3. **并发安全**：如果多用户同时使用，需要加锁或用分布式存储
4. **Agent 5（面试）**：目前只在 CLI 中实现，API 端点可以复用原有的 `/api/interview/*`

## 兼容性

- ✅ 原有 API `/api/analyze` 保持不变（非交互式）
- ✅ 原有 CLI `cli_interview.py` 已更新为交互式
- ✅ 3 层记忆系统完全兼容
- ✅ 数据库结构无变化
