import { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Loader2, Send, MessageSquare, Home, Check, RotateCcw, Briefcase, User } from 'lucide-react'
import { startInterview, replyInterview } from '../lib/api'
import type { UserInput, InterviewReplyResponse } from '../lib/api'
import { useToast } from '../components/Toast'

interface Turn {
  question: string
  answer: string
  feedback: {
    professionalism_score: number
    strengths: string[]
    weaknesses: string[]
    follow_up: string
  }
}

export default function InterviewPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { toast } = useToast()
  const { userInput, pipelineResult } = (location.state as {
    userInput?: UserInput
    pipelineResult?: Record<string, any>
  }) || {}

  const [sessionId, setSessionId] = useState('')
  const [persona, setPersona] = useState('')
  const [currentQuestion, setCurrentQuestion] = useState('')
  const [currentRound, setCurrentRound] = useState(0)
  const [turns, setTurns] = useState<Turn[]>([])
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)
  const [isDone, setIsDone] = useState(false)
  const [report, setReport] = useState<Record<string, any> | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!userInput && !pipelineResult) {
      navigate('/')
      return
    }
    initInterview()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns, currentQuestion, isDone])

  async function initInterview() {
    setLoading(true)
    try {
      const input = userInput || { resume_text: '' }
      const res = await startInterview(input, pipelineResult)
      setSessionId(res.session_id)
      setPersona(res.interviewer_persona || '资深面试官')
      setCurrentQuestion(res.question.question)
      setCurrentRound(res.round)
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : '面试启动失败', 'error')
      navigate('/')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit() {
    if (!answer.trim() || loading) return

    setLoading(true)
    const userAnswer = answer
    setAnswer('')

    try {
      const res: InterviewReplyResponse = await replyInterview(sessionId, userAnswer)

      setTurns((prev) => [
        ...prev,
        {
          question: currentQuestion,
          answer: userAnswer,
          feedback: res.feedback,
        },
      ])

      if (res.is_final) {
        setIsDone(true)
        setReport(res.report)
      } else {
        setCurrentQuestion(res.next_question?.question || '')
        setCurrentRound(res.round)
      }
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : '提交失败', 'error')
    } finally {
      setLoading(false)
    }
  }

  if (!sessionId && loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 pt-14 text-text-secondary text-sm">
        <Loader2 className="w-7 h-7 animate-spin text-accent" strokeWidth={1.75} />
        正在准备面试…
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <div className="sticky top-14 z-10 border-b border-border-subtle bg-surface-0/80 backdrop-blur-xl backdrop-saturate-150 px-6 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-surface-1 flex items-center justify-center ring-1 ring-black/[0.06] shadow-sm">
              <MessageSquare className="w-4 h-4 text-accent" strokeWidth={1.75} />
            </div>
            <div>
              <h1 className="font-medium text-sm">模拟面试</h1>
              {persona && <p className="text-xs text-text-muted">{persona}</p>}
            </div>
          </div>
          {!isDone && currentRound > 0 && (
            <div className="flex items-center gap-1.5">
              {[1, 2, 3].map((r) => (
                <div
                  key={r}
                  className={`w-2 h-2 rounded-full transition-colors ${
                    r <= currentRound ? 'bg-accent' : 'bg-surface-3'
                  }`}
                />
              ))}
              <span className="text-xs text-text-muted ml-2">第 {currentRound}/3 轮</span>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 max-w-4xl mx-auto w-full p-6 space-y-5">
        {/* Past turns */}
        {turns.map((turn, i) => (
          <div key={i} className="space-y-3">
            {/* Question */}
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-surface-1 flex items-center justify-center text-sm flex-shrink-0 ring-1 ring-black/[0.06] shadow-sm">
                <Briefcase className="w-4 h-4 text-accent" strokeWidth={1.75} />
              </div>
              <div className="flex-1 rounded-2xl rounded-tl-md bg-surface-1 ring-1 ring-black/[0.06] shadow-sm p-4">
                <p className="text-sm text-text-primary leading-relaxed">{turn.question}</p>
              </div>
            </div>

            {/* Answer */}
            <div className="flex gap-3 justify-end">
              <div className="flex-1 max-w-[80%] rounded-2xl rounded-tr-md bg-accent/[0.08] ring-1 ring-accent/18 p-4">
                <p className="text-sm text-text-primary leading-relaxed">{turn.answer}</p>
              </div>
              <div className="w-8 h-8 rounded-full bg-surface-1 flex items-center justify-center text-sm flex-shrink-0 ring-1 ring-accent/15 shadow-sm">
                <User className="w-4 h-4 text-accent" strokeWidth={1.75} />
              </div>
            </div>

            {/* Feedback */}
            <div className="ml-11 rounded-xl bg-surface-1 ring-1 ring-border-subtle p-4 space-y-3 shadow-sm">
              <div className="flex items-center gap-3">
                <ScoreBadge score={turn.feedback.professionalism_score} />
              </div>
              {turn.feedback.strengths.length > 0 && (
                <div className="space-y-1">
                  <span className="text-xs font-medium text-success">优点</span>
                  <ul className="space-y-0.5">
                    {turn.feedback.strengths.map((s, j) => (
                      <li key={j} className="text-xs text-text-secondary pl-3 relative before:content-[''] before:absolute before:left-0 before:top-2 before:w-1.5 before:h-1.5 before:rounded-full before:bg-success/40">
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {turn.feedback.weaknesses.length > 0 && (
                <div className="space-y-1">
                  <span className="text-xs font-medium text-warning">待改进</span>
                  <ul className="space-y-0.5">
                    {turn.feedback.weaknesses.map((w, j) => (
                      <li key={j} className="text-xs text-text-secondary pl-3 relative before:content-[''] before:absolute before:left-0 before:top-2 before:w-1.5 before:h-1.5 before:rounded-full before:bg-warning/40">
                        {w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {turn.feedback.follow_up && (
                <p className="text-xs text-text-muted italic border-t border-border-subtle pt-2">
                  {turn.feedback.follow_up}
                </p>
              )}
            </div>
          </div>
        ))}

        {/* Current question */}
        {!isDone && currentQuestion && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-surface-1 flex items-center justify-center text-sm flex-shrink-0 ring-1 ring-black/[0.06] shadow-sm">
              <Briefcase className="w-4 h-4 text-accent" strokeWidth={1.75} />
            </div>
            <div className="flex-1 rounded-2xl rounded-tl-md bg-surface-1 ring-1 ring-black/[0.06] shadow-sm p-4">
              <p className="text-sm text-text-primary leading-relaxed">{currentQuestion}</p>
            </div>
          </div>
        )}

        {/* Input area */}
        {!isDone && currentQuestion && (
          <div className="sticky bottom-4 rounded-2xl bg-surface-1 ring-1 ring-black/[0.08] shadow-md p-4 space-y-3">
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && e.ctrlKey) {
                  e.preventDefault()
                  handleSubmit()
                }
              }}
              placeholder="输入你的回答... (Ctrl+Enter 提交)"
              className="w-full h-28 bg-surface-0 border border-border-subtle rounded-xl p-3.5 text-sm text-text-primary placeholder:text-text-muted/80 focus:outline-none focus:ring-2 focus:ring-accent/25 focus:border-accent/40 resize-none transition-shadow leading-relaxed"
              disabled={loading}
            />
            <div className="flex justify-end">
              <button
                onClick={handleSubmit}
                disabled={!answer.trim() || loading}
                className="px-5 py-2 bg-accent hover:bg-accent-soft disabled:opacity-35 text-white font-medium rounded-xl transition-colors text-sm flex items-center gap-2 shadow-sm"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    提交中...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    提交回答
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Final report */}
        {isDone && report && (
          <div className="rounded-2xl ring-1 ring-success/25 bg-emerald-50/80 p-8 space-y-6 glow-success">
            <div className="text-center space-y-2">
              <div className="w-14 h-14 rounded-full bg-white ring-1 ring-success/20 flex items-center justify-center mx-auto shadow-sm">
                <Check className="w-7 h-7 text-success" strokeWidth={1.75} />
              </div>
              <h2 className="text-xl font-semibold text-success tracking-tight">面试完成</h2>
            </div>

            <div className="space-y-5">
              <div className="text-center">
                <ScoreBadge score={(report.overall_score as number) || 0} large />
                <span className="text-text-muted text-sm ml-2">/100</span>
              </div>

              {report.summary && (
                <div className="rounded-xl bg-surface-0 ring-1 ring-border-subtle p-4">
                  <p className="text-sm text-text-secondary leading-relaxed">{String(report.summary)}</p>
                </div>
              )}

              {(report.strengths as string[])?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-success uppercase tracking-wider mb-2">优势</h3>
                  <ul className="space-y-1.5">
                    {(report.strengths as string[]).map((s, i) => (
                      <li key={i} className="text-sm text-text-secondary pl-3 relative before:content-[''] before:absolute before:left-0 before:top-2.5 before:w-1 before:h-1 before:rounded-full before:bg-success/50">
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {(report.improvement_areas as string[])?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-warning uppercase tracking-wider mb-2">待提升</h3>
                  <ul className="space-y-1.5">
                    {(report.improvement_areas as string[]).map((a, i) => (
                      <li key={i} className="text-sm text-text-secondary pl-3 relative before:content-[''] before:absolute before:left-0 before:top-2.5 before:w-1 before:h-1 before:rounded-full before:bg-warning/50">
                        {a}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {(report.next_steps as string[])?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-accent uppercase tracking-wider mb-2">下一步建议</h3>
                  <ul className="space-y-1.5">
                    {(report.next_steps as string[]).map((n, i) => (
                      <li key={i} className="text-sm text-text-secondary pl-3 relative before:content-[''] before:absolute before:left-0 before:top-2.5 before:w-1 before:h-1 before:rounded-full before:bg-accent/40">
                        {n}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <p className="text-center text-sm text-text-secondary leading-relaxed border-t border-border-subtle pt-5">
              转行本身就需要勇气，你已经迈出了最难的一步。每一次练习都在缩短你和目标的距离，继续加油。
            </p>

            <div className="flex justify-center gap-3 pt-2">
              <button
                onClick={() => {
                  setTurns([])
                  setCurrentQuestion('')
                  setCurrentRound(0)
                  setIsDone(false)
                  setReport(null)
                  initInterview()
                }}
                className="px-5 py-2.5 bg-accent hover:bg-accent-soft rounded-xl text-sm text-white font-medium flex items-center gap-2 transition-colors shadow-sm"
              >
                <RotateCcw className="w-4 h-4" />
                再来一次
              </button>
              <button
                onClick={() => navigate('/')}
                className="px-5 py-2.5 bg-surface-1 hover:bg-surface-2 rounded-xl text-sm text-text-secondary flex items-center gap-2 transition-colors ring-1 ring-border"
              >
                <Home className="w-4 h-4" />
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

function ScoreBadge({ score, large }: { score: number; large?: boolean }) {
  const color = score >= 80 ? 'text-success' : score >= 60 ? 'text-warning' : 'text-danger'
  const size = large ? 'text-3xl' : 'text-sm'
  return <span className={`font-mono font-bold ${color} ${size}`}>{score}</span>
}
