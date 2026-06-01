import { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Loader2, Send, Check, ArrowRight, MessageSquare, FileDown } from 'lucide-react'
import { startInteractive, runStep, getActiveSession, finalizeSession } from '../lib/api'
import type { UserInput, InteractiveStepResponse, SavedSession } from '../lib/api'
import StepResult from '../components/StepResult'
import { downloadAnalysisReportPdf } from '../lib/analysisReportPdf'

const AGENTS = [
  { step: 1, name: '画像师', desc: '能力画像' },
  { step: 2, name: '探路者', desc: '市场匹配' },
  { step: 3, name: '规划局', desc: '路径规划' },
  { step: 4, name: '磨刀石', desc: '简历润色' },
  { step: 5, name: '面试官', desc: '模拟面试' },
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
  const [saving, setSaving] = useState(false)
  const [pdfExporting, setPdfExporting] = useState(false)
  /** Filled when resuming from DB (HomePage only passes recovery: true). */
  const [recoveredUserInput, setRecoveredUserInput] = useState<UserInput | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const effectiveUserInput = userInput ?? recoveredUserInput ?? undefined

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

  function restoreSession(session: SavedSession): number {
    setSessionId(session.session_id)
    setRecoveredUserInput(session.user_input)
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
    setCurrentStep(maxStep === 0 ? 1 : maxStep >= 4 ? 4 : maxStep)
    // Stay on feedback until finalize succeeds (caller may auto-finalize when 4 steps exist)
    setPhase('feedback')
    return maxStep
  }

  async function initSession() {
    const input = userInput
    if (!input) return
    try {
      setPhase('running')
      const { session_id } = await startInteractive(input)
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

  async function handleConfirm() {
    if (currentStep === 2 && !chosenDirection) return

    if (currentStep >= 4) {
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
    if (!effectiveUserInput) return
    navigate('/interview', {
      state: { userInput: effectiveUserInput, pipelineResult: buildPipelineResult() },
    })
  }

  async function handleSaveAnalysis() {
    if (!sessionId) return
    setSaving(true)
    setError('')
    try {
      await finalizeSession(sessionId)
      setPhase('done')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '保存分析结果失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  async function handleDownloadPdf() {
    setPdfExporting(true)
    setError('')
    try {
      await downloadAnalysisReportPdf(buildPipelineResult())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '生成 PDF 失败，请重试')
    } finally {
      setPdfExporting(false)
    }
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
      <div className="sticky top-14 z-10 border-b border-border-subtle bg-surface-0/80 backdrop-blur-xl backdrop-saturate-150 px-6 py-3">
        <div className="max-w-4xl mx-auto flex items-center gap-1">
          {AGENTS.map((agent) => (
            <div key={agent.step} className="flex items-center gap-1 flex-1">
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium transition-colors duration-200 ${
                  agent.step === 5
                    ? results[4]?.success && (phase === 'feedback' || phase === 'done')
                      ? 'bg-accent/8 text-accent ring-1 ring-accent/20'
                      : 'bg-surface-2 text-text-muted ring-1 ring-black/[0.04]'
                    : agent.step < currentStep
                    ? 'bg-success/10 text-success ring-1 ring-success/15'
                    : agent.step === currentStep && !(agent.step === 4 && results[4]?.success)
                    ? 'bg-accent/8 text-accent ring-1 ring-accent/20'
                    : results[agent.step]?.success && agent.step === 4
                    ? 'bg-success/10 text-success ring-1 ring-success/15'
                    : 'bg-surface-2 text-text-muted ring-1 ring-black/[0.04]'
                }`}
              >
                {agent.step < currentStep || (agent.step === 4 && results[4]?.success) ? (
                  <Check className="w-3.5 h-3.5" strokeWidth={2} />
                ) : (
                  <span className="text-[10px] font-semibold tabular-nums w-5 h-5 rounded-full bg-accent/12 text-accent flex items-center justify-center shrink-0">
                    {agent.step}
                  </span>
                )}
                <span className="hidden sm:inline">{agent.name}</span>
              </div>
              {agent.step < 5 && (
                <ArrowRight className="w-3 h-3 text-text-muted hidden sm:block shrink-0" />
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
              <span className="text-[11px] font-semibold tabular-nums w-6 h-6 rounded-full bg-accent/10 text-accent flex items-center justify-center shrink-0">
                {Number(step)}
              </span>
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
                「{AGENTS[currentStep - 1].name}」正在分析
              </p>
              <p className="text-xs text-text-muted mt-0.5">通常需要 15-30 秒</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {phase === 'error' && (
          <div className="rounded-xl ring-1 ring-danger/20 bg-red-50/80 p-5 space-y-3">
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
          <div className="rounded-2xl ring-1 ring-border bg-surface-1 p-6 space-y-4 shadow-sm">
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
                className="flex-1 bg-surface-0 border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted/80 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent/35 transition-shadow"
              />
              <button
                onClick={handleRevise}
                disabled={!feedback.trim()}
                className="p-2.5 bg-surface-1 hover:bg-surface-2 disabled:opacity-30 rounded-xl transition-colors ring-1 ring-border"
                title="提交修改意见"
              >
                <Send className="w-4 h-4 text-text-secondary" />
              </button>
            </div>

            {currentStep === 4 && results[4]?.success ? (
              <div className="space-y-3 pt-1">
                {error ? <p className="text-xs text-danger">{error}</p> : null}
                <p className="text-xs text-text-muted leading-relaxed">
                  第 5 步「面试官」为模拟面试，可直接开始。可下载 PDF 报告留档；「保存分析结果」写入记忆与历史（可选）。
                </p>
                <button
                  type="button"
                  onClick={handleGoInterview}
                  disabled={!effectiveUserInput}
                  className="w-full bg-accent hover:bg-accent-soft disabled:opacity-35 text-white font-medium py-3 rounded-xl transition-colors text-sm flex items-center justify-center gap-2 shadow-sm"
                >
                  <MessageSquare className="w-4 h-4" />
                  进入模拟面试
                </button>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => void handleSaveAnalysis()}
                    disabled={saving || pdfExporting}
                    className="w-full bg-surface-1 hover:bg-surface-2 disabled:opacity-50 text-text-primary font-medium py-3 rounded-xl transition-colors text-sm flex items-center justify-center gap-2 ring-1 ring-border"
                  >
                    {saving ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin text-accent" />
                        正在保存…
                      </>
                    ) : (
                      <>
                        <Check className="w-4 h-4 text-accent" />
                        保存分析结果
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDownloadPdf()}
                    disabled={pdfExporting || saving}
                    className="w-full bg-surface-1 hover:bg-surface-2 disabled:opacity-50 text-text-primary font-medium py-3 rounded-xl transition-colors text-sm flex items-center justify-center gap-2 ring-1 ring-border"
                  >
                    {pdfExporting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin text-accent" />
                        正在生成 PDF…
                      </>
                    ) : (
                      <>
                        <FileDown className="w-4 h-4 text-accent" />
                        下载 PDF 报告
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => void handleConfirm()}
                disabled={currentStep === 2 && !chosenDirection}
                className="w-full bg-accent hover:bg-accent-soft disabled:opacity-35 text-white font-medium py-3 rounded-xl transition-colors text-sm flex items-center justify-center gap-2 shadow-sm"
              >
                <Check className="w-4 h-4" />
                满意，下一步
              </button>
            )}
          </div>
        )}

        {/* Done state */}
        {phase === 'done' && (
          <div className="rounded-2xl ring-1 ring-success/25 bg-emerald-50/70 p-8 text-center space-y-5 glow-success">
            <div className="w-14 h-14 rounded-full bg-white ring-1 ring-success/20 flex items-center justify-center mx-auto shadow-sm">
              <Check className="w-7 h-7 text-success" strokeWidth={1.75} />
            </div>
            <div>
              <p className="text-lg font-semibold text-success tracking-tight">全部分析完成</p>
              <p className="text-sm text-text-muted mt-1">前四步已完成；第 5 步「面试官」可随时进入。</p>
            </div>
            <div className="flex flex-wrap gap-3 justify-center">
              <button
                onClick={handleGoInterview}
                className="px-5 py-2.5 bg-accent hover:bg-accent-soft rounded-xl font-medium text-sm text-white flex items-center gap-2 transition-colors shadow-sm"
              >
                <MessageSquare className="w-4 h-4" />
                进入模拟面试
              </button>
              <button
                type="button"
                onClick={() => void handleDownloadPdf()}
                disabled={pdfExporting}
                className="px-5 py-2.5 bg-surface-1 hover:bg-surface-2 rounded-xl text-sm text-text-secondary flex items-center gap-2 transition-colors ring-1 ring-border print-hidden disabled:opacity-50"
              >
                {pdfExporting ? (
                  <Loader2 className="w-4 h-4 animate-spin text-accent" />
                ) : (
                  <FileDown className="w-4 h-4" />
                )}
                下载 PDF
              </button>
              <button
                onClick={() => navigate('/')}
                className="px-5 py-2.5 bg-surface-1 hover:bg-surface-2 rounded-xl text-sm text-text-secondary transition-colors ring-1 ring-border"
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
              className={`text-left p-3.5 rounded-xl transition-colors duration-200 ring-1 ${
                isChosen
                  ? 'ring-accent/40 bg-accent/[0.06] shadow-sm'
                  : 'ring-black/[0.06] bg-surface-1 hover:ring-border hover:bg-surface-0'
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
