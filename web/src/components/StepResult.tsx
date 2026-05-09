/**
 * Renders structured output from each agent step.
 */

interface StepResultProps {
  step: number
  result: Record<string, any> | null
  onChooseDirection?: (dir: string) => void
}

export default function StepResult({ step, result }: StepResultProps) {
  if (!result) return null

  return (
    <div className="rounded-2xl border border-border bg-surface-1 p-6 space-y-5">
      {step === 1 && <ProfileResult data={result} />}
      {step === 2 && <MatchResult data={result} />}
      {step === 3 && <PlanResult data={result} />}
      {step === 4 && <ResumeResult data={result} />}
    </div>
  )
}

// ── Agent 1: 能力画像 ──

function ProfileResult({ data }: { data: Record<string, any> }) {
  const hardSkills = (data.hard_skills as Array<Record<string, any>>) || []
  const transferable = (data.transferable_skills as Array<Record<string, any>>) || []
  const personality = (data.personality as Array<Record<string, any>>) || []
  const constraints = (data.constraints as Array<Record<string, any>>) || []

  return (
    <div className="space-y-5">
      {data.summary && (
        <p className="text-accent font-medium leading-relaxed">{String(data.summary)}</p>
      )}

      {hardSkills.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">硬技能</h4>
          <div className="flex flex-wrap gap-2">
            {hardSkills.map((s, i) => (
              <SkillBadge key={i} name={String(s.name)} level={s.proficiency as number} />
            ))}
          </div>
        </div>
      )}

      {transferable.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">可迁移技能</h4>
          <div className="flex flex-wrap gap-2">
            {transferable.map((s, i) => (
              <SkillBadge key={i} name={String(s.name)} level={s.proficiency as number} variant="success" />
            ))}
          </div>
        </div>
      )}

      {personality.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">性格特征</h4>
          <div className="space-y-2">
            {personality.map((p, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span className="text-accent font-medium">{String(p.trait)}</span>
                <span className="text-text-muted">— {String(p.signal)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {constraints.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">约束条件</h4>
          <div className="space-y-2">
            {constraints.map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="text-base">{(c.flexibility as string) === 'hard' ? '🔒' : '🔓'}</span>
                <span className="text-warning font-medium">{String(c.dimension)}:</span>
                <span className="text-text-secondary">{String(c.detail)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Agent 2: 市场匹配 ──

function MatchResult({ data }: { data: Record<string, any> }) {
  const matches = (data.top_matches as Array<Record<string, any>>) || []
  const antiRecs = (data.anti_recommendations as string[]) || []

  return (
    <div className="space-y-4">
      {matches.length > 0 && (
        <div className="space-y-3">
          {matches.map((m, i) => (
            <div key={i} className="rounded-xl bg-surface-0 border border-border-subtle p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium text-text-primary text-sm">
                  {String(m.industry)} · {String(m.role)}
                </span>
                <ScoreBadge score={m.fit_score as number} />
              </div>
              {m.rationale && (
                <p className="text-xs text-text-muted leading-relaxed">{String(m.rationale)}</p>
              )}
              {(m.skill_gaps as string[])?.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {(m.skill_gaps as string[]).map((gap, j) => (
                    <span key={j} className="text-xs px-2 py-0.5 bg-warning/10 text-warning rounded">
                      {gap}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {data.market_insight && (
        <div className="rounded-xl border border-accent/20 bg-accent/5 p-4">
          <p className="text-xs text-accent leading-relaxed">💡 {String(data.market_insight)}</p>
        </div>
      )}

      {antiRecs.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-danger mb-2">不推荐方向</h4>
          {antiRecs.map((r, i) => (
            <p key={i} className="text-xs text-text-muted">✗ {r}</p>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Agent 3: 路径规划 ──

function PlanResult({ data }: { data: Record<string, any> }) {
  const phases = (data.phases as Array<Record<string, any>>) || []
  const risks = (data.risk_factors as string[]) || []
  const target = data.chosen_target as Record<string, any> | undefined

  return (
    <div className="space-y-5">
      {target && (
        <div className="flex items-center gap-4 text-xs">
          <span className="text-text-muted">目标:</span>
          <span className="text-accent font-medium">
            {String(target.industry)} · {String(target.role)}
          </span>
          <span className="text-border">|</span>
          <span className="text-text-muted">周期: {String(data.total_timeline)}</span>
        </div>
      )}

      {phases.length > 0 && (
        <div className="space-y-3">
          {phases.map((p, i) => (
            <div key={i} className="border-l-2 border-accent/30 pl-4 py-2 space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-accent font-medium text-sm">
                  阶段{p.phase_number as number}: {String(p.title)}
                </span>
                <span className="text-xs text-text-muted">({String(p.duration)})</span>
              </div>
              <p className="text-xs text-text-secondary">🎯 {String(p.milestone)}</p>
              {(p.actions as string[])?.length > 0 && (
                <div className="space-y-0.5 pt-1">
                  {(p.actions as string[]).slice(0, 3).map((a, j) => (
                    <p key={j} className="text-xs text-text-muted">→ {a}</p>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {risks.length > 0 && (
        <div className="rounded-xl border border-warning/20 bg-warning/5 p-4 space-y-2">
          <h4 className="text-xs font-semibold text-warning">风险提示</h4>
          {risks.map((r, i) => (
            <p key={i} className="text-xs text-text-muted">⚠ {r}</p>
          ))}
        </div>
      )}

      {data.plan_b && (
        <p className="text-xs text-text-muted">备选方案: {String(data.plan_b)}</p>
      )}
    </div>
  )
}

// ── Agent 4: 简历润色 ──

function ResumeResult({ data }: { data: Record<string, any> }) {
  const sections = (data.sections as Array<Record<string, any>>) || []
  const keywords = (data.keywords_added as string[]) || []
  const atsTips = (data.ats_tips as string[]) || []

  return (
    <div className="space-y-5">
      {data.overall_narrative && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">核心叙事线</h4>
          <p className="text-text-primary text-sm leading-relaxed">{String(data.overall_narrative)}</p>
        </div>
      )}

      {sections.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">修改段落</h4>
          <div className="space-y-2">
            {sections.map((s, i) => (
              <div key={i} className="rounded-xl bg-surface-0 border border-border-subtle p-3.5 space-y-2">
                <span className="text-accent font-medium text-xs">{String(s.section)}</span>
                <div className="flex flex-wrap gap-1.5">
                  {((s.changes_made as string[]) || []).map((c, j) => (
                    <span key={j} className="text-xs px-2 py-0.5 bg-surface-3 text-text-secondary rounded">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {keywords.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">补充关键词</h4>
          <div className="flex flex-wrap gap-1.5">
            {keywords.map((k, i) => (
              <span key={i} className="text-xs px-2 py-0.5 bg-success/10 text-success rounded">
                {k}
              </span>
            ))}
          </div>
        </div>
      )}

      {atsTips.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">ATS 优化建议</h4>
          {atsTips.map((t, i) => (
            <p key={i} className="text-xs text-text-muted">💡 {t}</p>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Shared components ──

function SkillBadge({ name, level, variant = 'accent' }: { name: string; level: number; variant?: string }) {
  const colors = variant === 'success'
    ? 'bg-success/10 text-success border-success/20'
    : 'bg-accent/10 text-accent border-accent/20'

  return (
    <span className={`text-xs px-2.5 py-1 rounded-lg border ${colors} font-medium`}>
      {name}
      <span className="ml-1.5 opacity-50">{'●'.repeat(level)}{'○'.repeat(5 - level)}</span>
    </span>
  )
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? 'text-success' : score >= 60 ? 'text-warning' : 'text-text-muted'
  return <span className={`text-xs font-mono font-bold ${color}`}>{score}%</span>
}
