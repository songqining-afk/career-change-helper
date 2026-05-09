# Claude 超时自动切换 DeepSeek

## 问题

Claude Opus 4.7 响应时间有时很慢（30s+），导致用户等待时间过长。

## 解决方案

添加**激进超时机制**：如果 Claude 在 30 秒内没有响应，立即切换到 DeepSeek。

---

## 实现细节

### 1. 超时机制

使用 `asyncio.wait_for()` 包裹 Claude API 调用：

```python
try:
    return await asyncio.wait_for(
        self._call_claude(system, user),
        timeout=self.claude_timeout  # 默认 30s
    )
except asyncio.TimeoutError:
    logger.warning(f"Claude timeout after {self.claude_timeout}s")
    # 立即切换到 DeepSeek
    return await self._call_deepseek(system, user)
```

### 2. 配置参数

新增 `claude_timeout` 参数（默认 30 秒）：

```python
class LLMClient:
    def __init__(
        self,
        model: str | None = None,
        timeout: float = 120.0,        # SDK 级别超时（安全网）
        claude_timeout: float | None = None,  # Claude 专用超时
    ):
        self.claude_timeout = claude_timeout or float(os.getenv("CLAUDE_TIMEOUT", "30"))
```

### 3. 环境变量

```bash
# .env
CLAUDE_TIMEOUT=30  # Claude 超时时间（秒），默认 30

# DeepSeek fallback（如果配置了 DEEPSEEK_API_KEY 则自动启用）
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

### 4. 日志输出

CLI 模式下，超时切换会显示黄色警告：

```
⚠ Claude timeout after 30.0s
⚠ Switching to DeepSeek...
```

---

## 用户体验变化

### 改动前
```
Agent 1 正在分析...
[等待 60-120 秒]
✓ 分析完成
```

### 改动后
```
Agent 1 正在分析...
[等待 30 秒]
⚠ Claude timeout after 30.0s
⚠ Switching to DeepSeek...
[DeepSeek 响应，通常 5-10 秒]
✓ 分析完成
```

---

## Fallback 触发条件

DeepSeek fallback 会在以下情况触发：

1. **超时**（新增）：Claude 30 秒内未响应
2. **连接错误**：`APIConnectionError`
3. **SDK 超时**：`APITimeoutError`（120s 后）
4. **服务器错误**：`InternalServerError` (5xx)
5. **限流**：`RateLimitError`
6. **认证错误**：`AuthenticationError`, `PermissionDeniedError`

---

## 配置建议

### 场景 1：Claude 稳定，偶尔慢
```bash
CLAUDE_TIMEOUT=45  # 给 Claude 更多时间
```

### 场景 2：Claude 经常慢，追求速度
```bash
CLAUDE_TIMEOUT=20  # 更激进的超时
```

### 场景 3：只用 Claude，不要 fallback
```bash
CLAUDE_TIMEOUT=120  # 等同于 SDK 超时
# 不配置 DEEPSEEK_API_KEY
```

### 场景 4：优先 DeepSeek（快速但质量略低）
```bash
CLAUDE_TIMEOUT=10  # 极短超时，几乎总是切换到 DeepSeek
```

---

## 代码改动清单

### `src/llm/client.py`

1. **导入 asyncio**
   ```python
   import asyncio
   ```

2. **新增 `claude_timeout` 参数**
   ```python
   def __init__(self, ..., claude_timeout: float | None = None):
       self.claude_timeout = claude_timeout or float(os.getenv("CLAUDE_TIMEOUT", "30"))
   ```

3. **包裹 Claude 调用**
   ```python
   async def _call_with_fallback(self, system: str, user: str) -> str:
       try:
           return await asyncio.wait_for(
               self._call_claude(system, user),
               timeout=self.claude_timeout
           )
       except asyncio.TimeoutError:
           logger.warning(f"Claude timeout after {self.claude_timeout}s")
           if self._deepseek_enabled:
               logger.info("Switching to DeepSeek...")
               return await self._call_deepseek(system, user)
           raise
       except (...):  # 其他异常保持不变
           ...
   ```

4. **同样逻辑应用到 `_call_multi_with_fallback`**

### `src/cli_interview.py`

添加日志配置，显示 fallback 警告：

```python
async def main():
    import logging
    logging.basicConfig(
        level=logging.WARNING,
        format=f"{C.YELLOW}⚠ %(message)s{C.RESET}",
        force=True,
    )
    banner()
    ...
```

### `.env.example`

添加配置说明：

```bash
# Optional: Claude timeout (seconds) before switching to DeepSeek
# Default: 30s. Set lower if Claude is slow, higher if you want to wait longer.
# CLAUDE_TIMEOUT=30

# Optional: DeepSeek fallback (auto-enabled if DEEPSEEK_API_KEY is set)
# DEEPSEEK_API_KEY=your_deepseek_key_here
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
# DEEPSEEK_MODEL=deepseek-chat
```

### `README.md`

更新 LLM 章节：

```markdown
## LLM

All agents use **Anthropic Claude Opus 4.7** (official SDK, adaptive thinking).

**Automatic fallback**: If Claude doesn't respond within **30 seconds** (configurable via `CLAUDE_TIMEOUT`), the system automatically switches to **DeepSeek** for that request. This ensures fast response times even when Claude is slow.

To configure:
\`\`\`bash
# .env
CLAUDE_TIMEOUT=30  # seconds (default: 30)
DEEPSEEK_API_KEY=your_key_here  # enables fallback
\`\`\`
```

---

## 测试建议

### 1. 正常流程（Claude 快速响应）
```bash
python3 src/cli_interview.py
# 应该看到正常的 Agent 输出，无警告
```

### 2. 模拟 Claude 超时
临时设置极短超时：
```bash
export CLAUDE_TIMEOUT=1
python3 src/cli_interview.py
# 应该立即看到：
# ⚠ Claude timeout after 1.0s
# ⚠ Switching to DeepSeek...
```

### 3. 无 DeepSeek fallback
```bash
unset DEEPSEEK_API_KEY
export CLAUDE_TIMEOUT=5
python3 src/cli_interview.py
# 如果 Claude 超时，应该抛出异常（因为没有 fallback）
```

### 4. 验证 DeepSeek 输出质量
```bash
export CLAUDE_TIMEOUT=1  # 强制使用 DeepSeek
python3 src/cli_interview.py
# 对比输出质量，确保 DeepSeek 结果可接受
```

---

## 性能对比

| 场景 | Claude 响应时间 | DeepSeek 响应时间 | 总等待时间（改动前） | 总等待时间（改动后） |
|------|----------------|------------------|---------------------|---------------------|
| Claude 正常 | 10s | - | 10s | 10s |
| Claude 慢 | 60s | - | 60s | 60s |
| Claude 超时 | 超时 | 8s | 120s（SDK 超时） | 38s（30s 超时 + 8s DeepSeek） |
| Claude 宕机 | 失败 | 8s | 失败 | 38s |

**结论**：最坏情况下，等待时间从 120s 降低到 38s（**68% 改善**）。

---

## 向后兼容性

✅ 完全兼容现有代码（默认行为：30s 超时）
✅ 不影响 REST API 模式
✅ 不影响已有的 DeepSeek fallback 逻辑（连接错误、5xx 等）
✅ 可通过环境变量禁用（设置 `CLAUDE_TIMEOUT=120` 或不配置 `DEEPSEEK_API_KEY`）

---

## 未来优化方向

1. **自适应超时**：根据历史响应时间动态调整超时阈值
2. **并行调用**：同时调用 Claude 和 DeepSeek，取最快的结果
3. **质量评分**：对比 Claude 和 DeepSeek 的输出质量，自动选择更好的
4. **成本优化**：优先使用 DeepSeek（更便宜），只在质量不足时才用 Claude
5. **用户选择**：CLI 提示"Claude 响应慢，是否切换到 DeepSeek？"
