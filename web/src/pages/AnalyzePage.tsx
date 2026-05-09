import { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Loader2, Send, Check, ArrowRight, MessageSquare, Download } from 'lucide-react'
import { startInteractive, runStep, getActiveSession } from '../lib/api'
import type { UserInput, InteractiveStepResponse, SavedSession } from '../lib/api'
import StepResult from '../components/StepResult'

const AGENTS = [
  { step: 1, name: '画像师', icon: '🔍', desc: '能力画像' },
  { step: 2, name: '探路者', icon: '🧭', desc: '市场匹配' },
  { step: 3, name: '规划局', icon: '🗺️', desc: '路径规划' },
  { step: 4, name: '磨刀石', icon: '✨', desc: '简历润色' },
]

type Phase = 'init' | 'running' | 'feedback' | 'done' | 'error'

export default function AnalyzePage() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as { userInput?: UserInput; recovery?: boolean } | null
  const userInput = state?.userInput
  const isRecovery = state?.recovery

  const [sessionId, setSessionId] = useState('')
  const [currentStep, setCurrentStep] = useState(1)
  const [phase, setPhase] = useState<Phase>('init')
  const [results, setResults] = useState<Record<number, InteractiveStepResponse>>({})
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')
  const [chosenDirection, setChosenDirection] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    checkForRecovery()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [phase, results, currentStep])

  async function checkForRecovery() {
    // If navigated with recovery flag, directly restore session
    if (isRecovery) {
      try {
        const { exists, session } = await getActiveSession()
        if (exists && session) {
          restoreSession(session)
          return
        }
      } catch {
        // fall through
      }
    }

    if (!userInput) {
      navigate('/')
      return
    }
    initSession()
  }

  function restoreSession(session: SavedSession) {
    setSessionId(session.session_id)
    const savedResults: Record<number, InteractiveStepResponse> = {}
    let maxStep = 0
    for (const [stepStr, data] of Object.entries(session.results)) {
      const step = Number(stepStr)
      savedResults[step] = {
        success: true,
        step,
        agent_name: data.agent_name,
        result: data.result,
        error: '',
        duration_s: data.duration_s,
      }
      if (step > maxStep) maxStep = step
    }
    setResults(savedResults)
    setCurrentStep(maxStep)
    setPhase(maxStep >= 4 ? 'done' : 'feedback')
  }

  async function initSession() {
    try {
      setPhase('running')
      const { session_id } = await startInteractive(userInput!)
      setSessionId(session_id)
      await executeStep(session_id, 1, '')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '初始化失败')
      setPhase('error')
    }
  }

  async function executeStep(sid: string, step: number, fb: string) {
    setPhase('running')
    try {
      const res = await runStep(sid, step, fb)
      if (res.success) {
        setResults((prev) => ({ ...prev, [step]: res }))
        setPhase('feedback')
      } else {
        setError(res.error || `Agent ${step} 分析失败`)
        setPhase('error')
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '请求失败'
      if (msg.includes('404')) {
        setError('会话已过期，请重新开始分析')
      } else {
        setError(msg)
      }
      setPhase('error')
    }
  }

  function handleConfirm() {
    if (currentStep === 2 && !chosenDirection) return

    if (currentStep >= 4) {
      setPhase('done')
      return
    }

    const nextStep = currentStep + 1
    setCurrentStep(nextStep)
    setFeedback('')

    const fb = currentStep === 2 ? `用户选择的转行方向: ${chosenDirection}` : ''
    executeStep(sessionId, nextStep, fb)
  }

  function handleRevise() {
    if (!feedback.trim()) return
    executeStep(sessionId, currentStep, feedback)
    setFeedback('')
  }

  function handleGoInterview() {
    navigate('/interview', { state: { userInput, pipelineResult: buildPipelineResult() } })
  }

  function buildPipelineResult() {
    return {
      talent_profile: results[1]?.result,
      industry_match: results[2]?.result,
      transition_plan: results[3]?.result,
      polished_resume: results[4]?.result,
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Progress stepper */}
      <div className="sticky top-14 z-10 bg-surface-0/80 backdrop-blur-xl border-b border-border-subtle px-6 py-3">
        <div className="max-w-4xl mx-auto flex items-center gap-1">
          {AGENTS.map((agent) => (
            <div key={agent.step} className="flex items-center gap-1 flex-1">
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-300 ${
                  agent.step < currentStep
                    ? 'bg-success/10 text-success'
                    : agent.step === currentStep
                    ? 'bg-accent/10 text-accent border border-accent/30'
                    : 'bg-surface-2 text-text-muted'
                }`}
              >
                {agent.step < currentStep ? (
                  <Check className="w-3.5 h-3.5" />
                ) : (
                  <span>{agent.icon}</span>
                )}
                <span className="hidden sm:inline">{agent.name}</span>
              </div>
              {agent.step < 4 && (
                <ArrowRight className="w-3 h-3 text-text-muted hidden sm:block" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 max-w-4xl mx-auto w-full p-6 space-y-6">

        {/* Rendered results */}
        {Object.entries(results).map(([step, res]) => (
          <div key={step} className="space-y-3 animate-in fade-in">
            <div className="flex items-center gap-2 text-text-secondary">
              <span className="text-base">{AGENTS[Number(step) - 1].icon}</span>
              <span className="text-sm font-medium">{AGENTS[Number(step) - 1].name}</span>
              <span className="text-xs text-text-muted ml-auto">
                {res.duration_s.toFixed(1)}s
              </span>
            </div>
            <StepResult step={Number(step)} result={res.result} onChooseDirection={setChosenDirection} />
          </div>
        ))}

        {/* Loading state */}
        {phase === 'running' && (
          <div className="flex items-center gap-3 py-10 justify-center">
            <div className="relative">
              <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-accent animate-spin" />
              </div>
            </div>
            <div>
              <p className="text-sm font-medium text-text-primary">
                {AGENTS[currentStep - 1].icon} 「{AGENTS[currentStep - 1].name}」正在分析
              </p>
              <p className="text-xs text-text-muted mt-0.5">通常需要 15-30 秒</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {phase === 'error' && (
          <div className="rounded-xl border border-danger/30 bg-danger/5 p-5 space-y-3">
            <p className="text-sm font-medium text-danger">分析出错</p>
            <p className="text-xs text-text-secondary">{error}</p>
            <button
              onClick={() => executeStep(sessionId, currentStep, '')}
              className="px-4 py-2 bg-danger/10 hover:bg-danger/20 text-danger rounded-lg text-xs font-medium transition-colors"
            >
              重试
            </button>
          </div>
        )}

        {/* Feedback area */}
        {phase === 'feedback' && (
          <div className="rounded-2xl border border-border bg-surface-1 p-6 space-y-4">
            {/* Direction chooser for step 2 */}
            {currentStep === 2 && results[2]?.result && (
              <DirectionChooser
                matches={(results[2].result as Record<string, any>).top_matches as Array<Record<string, any>>}
                chosen={chosenDirection}
                onChoose={setChosenDirection}
              />
            )}

            <div className="flex items-center gap-3">
              <input
                type="text"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleRevise()
                  }
                }}
                placeholder="输入修改意见，或直接确认进入下一步..."
                className="flex-1 bg-surface-0 border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent/40 transition-colors"
              />
              <button
                onClick={handleRevise}
                disabled={!feedback.trim()}
                className="p-2.5 bg-surface-3 hover:bg-surface-2 disabled:opacity-30 rounded-xl transition-colors"
                title="提交修改意见"
              >
                <Send className="w-4 h-4 text-text-secondary" />
              </button>
            </div>

            <button
              onClick={handleConfirm}
              disabled={currentStep === 2 && !chosenDirection}
              className="w-full bg-accent hover:bg-accent-soft disabled:opacity-30 text-white font-medium py-3 rounded-xl transition-all text-sm flex items-center justify-center gap-2"
            >
              <Check className="w-4 h-4" />
              {currentStep >= 4 ? '完成分析' : '满意，下一步'}
            </button>
          </div>
        )}

        {/* Done state */}
        {phase === 'done' && (
          <div className="rounded-2xl border border-success/30 bg-success/5 p-8 text-center space-y-5 glow-success">
            <div className="w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mx-auto">
              <Check className="w-7 h-7 text-success" />
            </div>
            <div>
              <p className="text-lg font-semibold text-success">全部分析完成</p>
              <p className="text-sm text-text-muted mt-1">4 位顾问已完成评估</p>
            </div>
            <div className="flex gap-3 justify-center">
              <button
                onClick={handleGoInterview}
                className="px-5 py-2.5 bg-accent hover:bg-accent-soft rounded-xl font-medium text-sm text-white flex items-center gap-2 transition-colors"
              >
                <MessageSquare className="w-4 h-4" />
                进入模拟面试
              </button>
              <button
                onClick={() => window.print()}
                className="px-5 py-2.5 bg-surface-3 hover:bg-surface-2 rounded-xl text-sm text-text-secondary flex items-center gap-2 transition-colors print:hidden"
              >
                <Download className="w-4 h-4" />
                导出报告
              </button>
              <button
                onClick={() => navigate('/')}
                className="px-5 py-2.5 bg-surface-3 hover:bg-surface-2 rounded-xl text-sm text-text-secondary transition-colors"
              >
                返回首页
              </button>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── Direction Chooser (Step 2) ──

function DirectionChooser({
  matches,
  chosen,
  onChoose,
}: {
  matches: Array<Record<string, any>>
  chosen: string
  onChoose: (dir: string) => void
}) {
  if (!matches?.length) return null

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-text-secondary">选择你想走的方向：</p>
      <div className="grid gap-2">
        {matches.map((m, i) => {
          const label = `${m.industry} · ${m.role}`
          const isChosen = chosen === label
          return (
            <button
              key={i}
              onClick={() => onChoose(label)}
              className={`text-left p-3.5 rounded-xl border transition-all duration-200 ${
                isChosen
                  ? 'border-accent/50 bg-accent/5'
                  : 'border-border-subtle bg-surface-0 hover:border-border'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`text-sm font-medium ${isChosen ? 'text-accent' : 'text-text-primary'}`}>
                  {label}
                </span>
                <span className="text-xs text-text-muted">{m.fit_score as number}%</span>
              </div>
              {m.rationale && (
                <p className="text-xs text-text-muted mt-1.5">{String(m.rationale)}</p>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
