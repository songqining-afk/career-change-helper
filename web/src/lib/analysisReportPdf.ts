/**
 * Client-side PDF export for the 4-step analysis pipeline (html2canvas + jsPDF).
 * Uses off-screen HTML with inline styles so Chinese renders correctly as raster.
 */

import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'

export type PipelineLike = {
  talent_profile?: Record<string, unknown> | null
  industry_match?: Record<string, unknown> | null
  transition_plan?: Record<string, unknown> | null
  polished_resume?: Record<string, unknown> | null
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function asStr(v: unknown): string {
  if (v == null) return ''
  if (typeof v === 'string') return v
  if (typeof v === 'number' || typeof v === 'boolean') return String(v)
  return ''
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s
  return s.slice(0, max) + '…'
}

function section(title: string, bodyHtml: string): string {
  return `
    <section style="margin-bottom:22px;page-break-inside:avoid;">
      <h2 style="margin:0 0 10px;font-size:15px;font-weight:600;color:#1d1d1f;border-bottom:2px solid #455e7a;padding-bottom:6px;">
        ${escapeHtml(title)}
      </h2>
      ${bodyHtml}
    </section>`
}

function p(text: string, muted = false): string {
  const c = muted ? '#6e6e73' : '#424245'
  return `<p style="margin:0 0 8px;font-size:12px;line-height:1.65;color:${c};white-space:pre-wrap;">${escapeHtml(truncate(text, 8000))}</p>`
}

function ul(items: string[]): string {
  if (!items.length) return ''
  const lis = items.map((t) => `<li style="margin:0 0 4px;font-size:12px;line-height:1.55;color:#424245;">${escapeHtml(truncate(t, 2000))}</li>`).join('')
  return `<ul style="margin:6px 0 0;padding-left:18px;">${lis}</ul>`
}

function formatProfile(data: Record<string, unknown> | null | undefined): string {
  if (!data) return p('（暂无能力画像数据）', true)
  const parts: string[] = []
  const summary = asStr(data.summary)
  if (summary) parts.push(p(summary))

  const hard = (data.hard_skills as Array<Record<string, unknown>>) || []
  if (hard.length) {
    parts.push(`<p style="margin:12px 0 4px;font-size:11px;font-weight:600;color:#455e7a;">硬技能</p>`)
    parts.push(ul(hard.map((s) => `${asStr(s.name)}（熟练度 ${asStr(s.proficiency)}/5）${asStr(s.evidence) ? ' — ' + asStr(s.evidence) : ''}`)))
  }
  const trans = (data.transferable_skills as Array<Record<string, unknown>>) || []
  if (trans.length) {
    parts.push(`<p style="margin:12px 0 4px;font-size:11px;font-weight:600;color:#455e7a;">可迁移技能</p>`)
    parts.push(ul(trans.map((s) => `${asStr(s.name)}（${asStr(s.proficiency)}/5）`)))
  }
  const pers = (data.personality as Array<Record<string, unknown>>) || []
  if (pers.length) {
    parts.push(`<p style="margin:12px 0 4px;font-size:11px;font-weight:600;color:#455e7a;">性格特质</p>`)
    parts.push(ul(pers.map((x) => `${asStr(x.trait)}：${asStr(x.signal)}`)))
  }
  const cons = (data.constraints as Array<Record<string, unknown>>) || []
  if (cons.length) {
    parts.push(`<p style="margin:12px 0 4px;font-size:11px;font-weight:600;color:#455e7a;">约束条件</p>`)
    parts.push(
      ul(
        cons.map(
          (c) =>
            `${asStr(c.dimension)}（${asStr(c.flexibility) === 'hard' ? '不可协商' : '可协商'}）：${asStr(c.detail)}`,
        ),
      ),
    )
  }
  const meta: string[] = []
  if (data.years_of_experience != null) meta.push(`工作年限：${asStr(data.years_of_experience)} 年`)
  if (asStr(data.current_role)) meta.push(`当前职位：${asStr(data.current_role)}`)
  const ind = data.industries_touched as string[] | undefined
  if (ind?.length) meta.push(`涉及行业：${ind.join('、')}`)
  if (meta.length) parts.push(`<p style="margin-top:10px;font-size:11px;color:#6e6e73;">${escapeHtml(meta.join(' ｜ '))}</p>`)

  return parts.join('') || p('（画像内容为空）', true)
}

function formatIndustry(data: Record<string, unknown> | null | undefined): string {
  if (!data) return p('（暂无市场匹配数据）', true)
  const parts: string[] = []
  const matches = (data.top_matches as Array<Record<string, unknown>>) || []
  if (matches.length) {
    matches.forEach((m, i) => {
      parts.push(
        `<div style="margin-bottom:12px;padding:10px 12px;background:#f5f5f7;border-radius:8px;border:1px solid #e5e5ea;">
          <div style="font-size:12px;font-weight:600;color:#1d1d1f;margin-bottom:4px;">${i + 1}. ${escapeHtml(asStr(m.industry))} · ${escapeHtml(asStr(m.role))}</div>
          <div style="font-size:11px;color:#248a3d;margin-bottom:4px;">匹配度 ${asStr(m.fit_score)}%</div>
          ${m.rationale ? `<p style="margin:0;font-size:11px;line-height:1.55;color:#424245;">${escapeHtml(truncate(asStr(m.rationale), 1500))}</p>` : ''}
        </div>`,
      )
    })
  }
  if (asStr(data.market_insight)) {
    parts.push(`<p style="margin:10px 0 4px;font-size:11px;font-weight:600;color:#455e7a;">市场洞察</p>`)
    parts.push(p(asStr(data.market_insight)))
  }
  const anti = (data.anti_recommendations as string[]) || []
  if (anti.length) {
    parts.push(`<p style="margin:10px 0 4px;font-size:11px;font-weight:600;color:#c41e3a;">不推荐方向</p>`)
    parts.push(ul(anti))
  }
  return parts.join('') || p('（匹配内容为空）', true)
}

function formatPlan(data: Record<string, unknown> | null | undefined): string {
  if (!data) return p('（暂无路径规划数据）', true)
  const parts: string[] = []
  const target = data.chosen_target as Record<string, unknown> | undefined
  if (target) {
    parts.push(
      `<p style="margin:0 0 8px;font-size:12px;color:#1d1d1f;"><strong>目标方向：</strong>${escapeHtml(asStr(target.industry))} · ${escapeHtml(asStr(target.role))}</p>`,
    )
  }
  if (asStr(data.total_timeline)) {
    parts.push(`<p style="margin:0 0 12px;font-size:11px;color:#6e6e73;">预计总周期：${escapeHtml(asStr(data.total_timeline))}</p>`)
  }
  const phases = (data.phases as Array<Record<string, unknown>>) || []
  phases.forEach((ph) => {
    const actions = ((ph.actions as string[]) || []).slice(0, 8)
    parts.push(
      `<div style="margin-bottom:12px;padding-left:10px;border-left:3px solid #455e7a;">
        <div style="font-size:12px;font-weight:600;color:#1d1d1f;">阶段 ${asStr(ph.phase_number)}：${escapeHtml(asStr(ph.title))}</div>
        <div style="font-size:11px;color:#6e6e73;margin:2px 0 4px;">${escapeHtml(asStr(ph.duration))}</div>
        <p style="margin:0 0 4px;font-size:11px;color:#424245;">里程碑：${escapeHtml(asStr(ph.milestone))}</p>
        ${actions.length ? ul(actions) : ''}
      </div>`,
    )
  })
  const risks = (data.risk_factors as string[]) || []
  if (risks.length) {
    parts.push(`<p style="margin:10px 0 4px;font-size:11px;font-weight:600;color:#b45309;">风险提示</p>`)
    parts.push(ul(risks))
  }
  if (asStr(data.plan_b)) parts.push(p(`备选方案：${asStr(data.plan_b)}`))
  return parts.join('') || p('（规划内容为空）', true)
}

function formatResume(data: Record<string, unknown> | null | undefined): string {
  if (!data) return p('（暂无简历润色数据）', true)
  const parts: string[] = []
  parts.push(
    `<p style="margin:0 0 10px;font-size:12px;color:#1d1d1f;"><strong>目标岗位：</strong>${escapeHtml(asStr(data.target_role))} ／ ${escapeHtml(asStr(data.target_industry))}</p>`,
  )
  if (asStr(data.overall_narrative)) {
    parts.push(`<p style="margin:0 0 8px;font-size:11px;font-weight:600;color:#455e7a;">核心叙事</p>`)
    parts.push(p(asStr(data.overall_narrative)))
  }
  const sections = (data.sections as Array<Record<string, unknown>>) || []
  sections.forEach((s) => {
    const changes = ((s.changes_made as string[]) || []).join('；')
    parts.push(
      `<div style="margin-bottom:12px;padding:10px;background:#fafafa;border-radius:8px;border:1px solid #ececec;">
        <div style="font-size:12px;font-weight:600;color:#455e7a;margin-bottom:6px;">${escapeHtml(asStr(s.section))}</div>
        ${changes ? `<p style="margin:0 0 6px;font-size:10px;color:#6e6e73;">修改要点：${escapeHtml(truncate(changes, 800))}</p>` : ''}
        <p style="margin:0;font-size:11px;line-height:1.6;color:#1d1d1f;white-space:pre-wrap;">${escapeHtml(truncate(asStr(s.polished), 4000))}</p>
      </div>`,
    )
  })
  const kw = (data.keywords_added as string[]) || []
  if (kw.length) {
    parts.push(`<p style="margin:10px 0 4px;font-size:11px;font-weight:600;color:#248a3d;">补充关键词</p>`)
    parts.push(`<p style="margin:0;font-size:11px;color:#424245;">${escapeHtml(kw.join('、'))}</p>`)
  }
  const tips = (data.ats_tips as string[]) || []
  if (tips.length) {
    parts.push(`<p style="margin:10px 0 4px;font-size:11px;font-weight:600;color:#455e7a;">ATS 建议</p>`)
    parts.push(ul(tips))
  }
  return parts.join('') || p('（简历内容为空）', true)
}

function buildReportHtml(pipeline: PipelineLike): string {
  const now = new Date()
  const dateStr = now.toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' })

  const body = [
    section('一、能力画像', formatProfile(pipeline.talent_profile as Record<string, unknown> | undefined)),
    section('二、市场匹配', formatIndustry(pipeline.industry_match as Record<string, unknown> | undefined)),
    section('三、转行路径规划', formatPlan(pipeline.transition_plan as Record<string, unknown> | undefined)),
    section('四、简历润色', formatResume(pipeline.polished_resume as Record<string, unknown> | undefined)),
  ].join('')

  return `
    <div id="analysis-pdf-root-inner" style="box-sizing:border-box;width:720px;padding:36px 40px;background:#ffffff;color:#1d1d1f;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Segoe UI',sans-serif;">
      <header style="margin-bottom:28px;padding-bottom:16px;border-bottom:1px solid #d2d2d7;">
        <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#455e7a;font-weight:600;">CareerChange Report</div>
        <h1 style="margin:8px 0 4px;font-size:22px;font-weight:600;letter-spacing:0.2em;color:#1d1d1f;">转 行 帮 · 分析报告</h1>
        <p style="margin:0;font-size:12px;color:#6e6e73;">生成时间：${escapeHtml(dateStr)}</p>
      </header>
      ${body}
      <footer style="margin-top:32px;padding-top:14px;border-top:1px solid #e5e5ea;font-size:10px;color:#8e8e93;line-height:1.5;">
        本报告由「转 行 帮」AI 分析流程自动生成，仅供个人职业规划参考；请结合自身情况谨慎决策。
      </footer>
    </div>`
}

function addCanvasToPdf(canvas: HTMLCanvasElement, fileName: string): void {
  const imgData = canvas.toDataURL('image/png', 1.0)
  const pdf = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' })
  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = pdf.internal.pageSize.getHeight()
  const imgWidth = pageWidth
  const imgHeight = (canvas.height * imgWidth) / canvas.width
  let heightLeft = imgHeight
  let position = 0

  pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight, undefined, 'FAST')
  heightLeft -= pageHeight

  while (heightLeft > 0) {
    position = heightLeft - imgHeight
    pdf.addPage()
    pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight, undefined, 'FAST')
    heightLeft -= pageHeight
  }

  pdf.save(fileName)
}

/**
 * Renders pipeline JSON to a styled HTML node, rasterizes with html2canvas, exports multi-page A4 PDF.
 */
export async function downloadAnalysisReportPdf(
  pipeline: PipelineLike,
  options?: { fileName?: string },
): Promise<void> {
  const wrap = document.createElement('div')
  wrap.setAttribute('data-analysis-pdf-export', '1')
  wrap.style.cssText =
    'position:absolute;left:-9999px;top:0;width:720px;overflow:visible;pointer-events:none;'
  wrap.innerHTML = buildReportHtml(pipeline)
  document.body.appendChild(wrap)

  const inner = wrap.querySelector('#analysis-pdf-root-inner') as HTMLElement
  if (!inner) {
    document.body.removeChild(wrap)
    throw new Error('PDF template failed')
  }

  try {
    const canvas = await html2canvas(inner, {
      scale: 2,
      useCORS: true,
      logging: false,
      backgroundColor: '#ffffff',
      windowWidth: 720,
    })

    const d = new Date()
    const stamp = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    const fileName = options?.fileName?.trim() || `转行分析报告-${stamp}.pdf`
    addCanvasToPdf(canvas, fileName.endsWith('.pdf') ? fileName : `${fileName}.pdf`)
  } finally {
    document.body.removeChild(wrap)
  }
}
