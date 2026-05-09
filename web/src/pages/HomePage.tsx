import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Compass, Sparkles, RotateCcw } from 'lucide-react'
import { getActiveSession, abandonSession } from '../lib/api'
import type { UserInput, SavedSession } from '../lib/api'

const STEPS = [
  { icon: '🔍', label: '画像师', desc: '发现你的隐藏潜力' },
  { icon: '🧭', label: '探路者', desc: '找到最佳切入点' },
  { icon: '🗺️', label: '规划局', desc: '制定行动路线图' },
  { icon: '✨', label: '磨刀石', desc: '重塑职业叙事' },
  { icon: '🎯', label: '面试官', desc: '实战压力测试' },
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
      <header className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-accent/5 via-transparent to-transparent" />
        <div className="relative max-w-4xl mx-auto px-6 pt-20 pb-12 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-2 border border-border-subtle text-xs text-text-secondary mb-6">
            <Compass className="w-3.5 h-3.5 text-accent" />
            专业 AI 顾问协作分析
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-4">
            <span className="text-gradient">转行帮</span>
          </h1>
          <p className="text-text-secondary text-lg max-w-md mx-auto leading-relaxed">
            AI全程助力转行，开启职业新篇章。
          </p>
        </div>
      </header>

      {/* Pipeline visualization */}
      <div className="max-w-4xl mx-auto px-6 mb-10">
        <div className="flex items-center justify-between gap-1 overflow-x-auto py-2">
          {STEPS.map((step, i) => (
            <div key={i} className="flex items-center gap-1 flex-shrink-0">
              <div className="flex flex-col items-center gap-1.5 px-3 py-2 rounded-xl bg-surface-1 border border-border-subtle min-w-[80px]">
                <span className="text-lg">{step.icon}</span>
                <span className="text-xs font-medium text-text-secondary whitespace-nowrap">{step.label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <ArrowRight className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Recovery prompt */}
      {recoveredSession && (
        <div className="max-w-3xl mx-auto w-full px-6 mb-6">
          <div className="rounded-2xl border border-warning/30 bg-warning/5 p-5 space-y-4">
            <div className="flex items-center gap-3">
              <RotateCcw className="w-5 h-5 text-warning" />
              <div>
                <p className="font-medium text-warning text-sm">检测到未完成的分析</p>
                <p className="text-xs text-text-muted mt-0.5">
                  上次进行到第 {Math.max(...Object.keys(recoveredSession.results).map(Number))} 步
                </p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleResume}
                className="flex-1 bg-accent hover:bg-accent-soft text-white font-medium py-2.5 rounded-xl transition-all text-sm flex items-center justify-center gap-2"
              >
                <RotateCcw className="w-4 h-4" />
                继续上次分析
              </button>
              <button
                onClick={handleDiscard}
                className="px-4 py-2.5 bg-surface-3 hover:bg-surface-2 text-text-muted font-medium rounded-xl transition-all text-sm"
              >
                放弃
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Input form */}
      <main className="flex-1 max-w-3xl mx-auto w-full px-6 pb-16">
        <div className={`rounded-2xl border transition-all duration-300 ${
          focused ? 'border-accent/40 glow-accent' : 'border-border'
        } bg-surface-1 p-6 sm:p-8 space-y-5`}>
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
              className="w-full h-44 bg-surface-0 border border-border-subtle rounded-xl p-4 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent/40 resize-none transition-colors text-sm leading-relaxed"
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
              className="w-full h-20 bg-surface-0 border border-border-subtle rounded-xl p-4 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent/40 resize-none transition-colors text-sm"
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
                className="w-full bg-surface-0 border border-border-subtle rounded-xl px-4 py-3 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent/40 transition-colors text-sm"
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
                className="w-full bg-surface-0 border border-border-subtle rounded-xl px-4 py-3 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent/40 transition-colors text-sm"
              />
            </div>
          </div>

          <button
            onClick={handleStart}
            disabled={!input.resume_text.trim()}
            className="w-full mt-2 bg-accent hover:bg-accent-soft disabled:opacity-30 disabled:cursor-not-allowed text-white font-medium py-3.5 rounded-xl transition-all duration-200 flex items-center justify-center gap-2 text-sm"
          >
            <Sparkles className="w-4 h-4" />
            开始分析
          </button>
        </div>
      </main>
    </div>
  )
}
