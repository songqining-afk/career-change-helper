import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Sparkles, RotateCcw } from 'lucide-react'
import { getActiveSession, abandonSession } from '../lib/api'
import type { UserInput, SavedSession } from '../lib/api'

const STEPS = [
  { label: '画像师', desc: '发现你的隐藏潜力' },
  { label: '探路者', desc: '找到最佳切入点' },
  { label: '规划局', desc: '制定行动路线图' },
  { label: '磨刀石', desc: '重塑职业叙事' },
  { label: '面试官', desc: '实战压力测试' },
]

export default function HomePage() {
  const navigate = useNavigate()
  const [input, setInput] = useState<UserInput>({
    resume_text: '',
    background: '',
    constraints: '',
    target_direction: '',
  })
  const [focused, setFocused] = useState(false)
  const [recoveredSession, setRecoveredSession] = useState<SavedSession | null>(null)

  useEffect(() => {
    getActiveSession()
      .then(({ exists, session }) => {
        if (exists && session) setRecoveredSession(session)
      })
      .catch(() => {})
  }, [])

  const handleStart = () => {
    if (!input.resume_text.trim()) return
    navigate('/analyze', { state: { userInput: input } })
  }

  const handleResume = () => {
    if (!recoveredSession) return
    navigate('/analyze', { state: { recovery: true } })
  }

  const handleDiscard = async () => {
    if (!recoveredSession) return
    await abandonSession(recoveredSession.session_id).catch(() => {})
    setRecoveredSession(null)
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero */}
      <header className="relative overflow-hidden border-b border-border-subtle/80">
        <div className="absolute inset-0 bg-gradient-to-b from-white via-surface-0 to-surface-0 pointer-events-none" />
        <div className="relative max-w-3xl mx-auto px-6 pt-16 sm:pt-20 pb-10 text-center">
          <h1 className="text-4xl sm:text-[2.75rem] font-semibold tracking-tight text-text-primary mb-3">
            <span className="text-gradient">转 行 帮</span>
          </h1>
          <p className="text-text-secondary text-[15px] sm:text-base max-w-md mx-auto leading-relaxed font-normal">
            从能力画像到模拟面试，把转行路径说清楚、做到位。
          </p>
        </div>
      </header>

      {/* Pipeline visualization */}
      <div className="max-w-3xl mx-auto px-6 mb-10">
        <div className="flex items-center justify-between gap-1 overflow-x-auto py-1">
          {STEPS.map((step, i) => (
            <div key={i} className="flex items-center gap-1 flex-shrink-0">
              <div className="flex flex-col items-center gap-1.5 px-3 py-2.5 rounded-2xl bg-surface-1 ring-1 ring-black/[0.05] shadow-sm min-w-[5.25rem]">
                <span className="text-[11px] font-semibold tabular-nums w-6 h-6 rounded-full bg-accent/10 text-accent flex items-center justify-center">
                  {i + 1}
                </span>
                <span className="text-[11px] font-medium text-text-secondary whitespace-nowrap">{step.label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <ArrowRight className="w-3 h-3 text-text-muted/70 flex-shrink-0" strokeWidth={1.5} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Recovery prompt */}
      {recoveredSession && (
        <div className="max-w-3xl mx-auto w-full px-6 mb-6">
          <div className="rounded-2xl ring-1 ring-warning/25 bg-amber-50/90 p-5 space-y-4">
            <div className="flex items-center gap-3">
              <RotateCcw className="w-5 h-5 text-warning shrink-0" strokeWidth={1.75} />
              <div>
                <p className="font-medium text-text-primary text-sm">未完成的分析</p>
                <p className="text-xs text-text-muted mt-0.5">
                  上次进行到第 {Math.max(...Object.keys(recoveredSession.results).map(Number))} 步
                </p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleResume}
                className="flex-1 bg-accent hover:bg-accent-soft text-white font-medium py-2.5 rounded-xl transition-colors text-sm flex items-center justify-center gap-2 shadow-sm"
              >
                <RotateCcw className="w-4 h-4" strokeWidth={1.75} />
                继续上次分析
              </button>
              <button
                onClick={handleDiscard}
                className="px-4 py-2.5 bg-surface-1 hover:bg-surface-2 text-text-secondary font-medium rounded-xl transition-colors text-sm ring-1 ring-border"
              >
                放弃
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Input form */}
      <main className="flex-1 max-w-3xl mx-auto w-full px-6 pb-20">
        <div
          className={`card-surface p-6 sm:p-8 space-y-5 transition-shadow duration-300 ${
            focused ? 'ring-1 ring-accent/35 glow-accent' : ''
          }`}
        >
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              简历内容
            </label>
            <textarea
              value={input.resume_text}
              onChange={(e) => setInput({ ...input, resume_text: e.target.value })}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="粘贴你的简历内容，或简要描述你的工作经历..."
              className="w-full h-44 bg-surface-0 border border-border-subtle rounded-xl p-4 text-text-primary placeholder:text-text-muted/80 focus:outline-none focus:ring-2 focus:ring-accent/25 focus:border-accent/40 resize-none transition-shadow text-sm leading-relaxed"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              补充背景
              <span className="text-text-muted font-normal ml-1">可选</span>
            </label>
            <textarea
              value={input.background}
              onChange={(e) => setInput({ ...input, background: e.target.value })}
              placeholder="补充经历、性格、偏好等..."
              className="w-full h-20 bg-surface-0 border border-border-subtle rounded-xl p-4 text-text-primary placeholder:text-text-muted/80 focus:outline-none focus:ring-2 focus:ring-accent/25 focus:border-accent/40 resize-none transition-shadow text-sm"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                约束条件
                <span className="text-text-muted font-normal ml-1">可选</span>
              </label>
              <input
                type="text"
                value={input.constraints}
                onChange={(e) => setInput({ ...input, constraints: e.target.value })}
                placeholder="地域、薪资、家庭等"
                className="w-full bg-surface-0 border border-border-subtle rounded-xl px-4 py-3 text-text-primary placeholder:text-text-muted/80 focus:outline-none focus:ring-2 focus:ring-accent/25 focus:border-accent/40 transition-shadow text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                期望方向
                <span className="text-text-muted font-normal ml-1">可选</span>
              </label>
              <input
                type="text"
                value={input.target_direction}
                onChange={(e) => setInput({ ...input, target_direction: e.target.value })}
                placeholder="如：产品经理、数据分析"
                className="w-full bg-surface-0 border border-border-subtle rounded-xl px-4 py-3 text-text-primary placeholder:text-text-muted/80 focus:outline-none focus:ring-2 focus:ring-accent/25 focus:border-accent/40 transition-shadow text-sm"
              />
            </div>
          </div>

          <button
            onClick={handleStart}
            disabled={!input.resume_text.trim()}
            className="w-full mt-2 bg-accent hover:bg-accent-soft disabled:opacity-35 disabled:cursor-not-allowed text-white font-medium py-3.5 rounded-xl transition-colors duration-200 flex items-center justify-center gap-2 text-sm shadow-sm"
          >
            <Sparkles className="w-4 h-4" />
            开始分析
          </button>
        </div>
      </main>
    </div>
  )
}
