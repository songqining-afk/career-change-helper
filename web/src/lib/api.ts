/**
 * API client for 转 行 帮 backend
 */

const BASE = ''  // proxied via vite

export interface UserInput {
  user_id?: string
  resume_text: string
  background?: string
  constraints?: string
  target_direction?: string
}

export interface InteractiveStartResponse {
  session_id: string
  message: string
}

export interface InteractiveStepResponse {
  success: boolean
  step: number
  agent_name: string
  result: Record<string, unknown> | null
  error: string
  duration_s: number
}

export interface InterviewStartResponse {
  session_id: string
  interviewer_persona: string
  question: { round_number: number; question: string; intent: string }
  round: number
  total_rounds: number
}

export interface InterviewReplyResponse {
  feedback: {
    professionalism_score: number
    strengths: string[]
    weaknesses: string[]
    follow_up: string
  }
  next_question: { round_number: number; question: string; intent: string } | null
  round: number
  is_final: boolean
  report: Record<string, unknown> | null
}

// ── Interactive Pipeline ──

export async function startInteractive(userInput: UserInput): Promise<InteractiveStartResponse> {
  const res = await fetch(`${BASE}/api/analyze/interactive/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_input: userInput }),
  })
  if (!res.ok) throw new Error(`Start failed: ${res.status}`)
  return res.json()
}

export async function runStep(
  sessionId: string,
  step: number,
  userFeedback: string = ''
): Promise<InteractiveStepResponse> {
  const res = await fetch(`${BASE}/api/analyze/interactive/step`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, step, user_feedback: userFeedback }),
  })
  if (!res.ok) throw new Error(`Step ${step} failed: ${res.status}`)
  return res.json()
}

export async function finalizeSession(sessionId: string) {
  const res = await fetch(
    `${BASE}/api/analyze/interactive/finalize?session_id=${encodeURIComponent(sessionId)}`,
    { method: 'POST' }
  )
  if (!res.ok) throw new Error(`Finalize failed: ${res.status}`)
  return res.json()
}

// ── Interview ──

export async function startInterview(
  userInput: UserInput,
  pipelineResult?: Record<string, unknown>
): Promise<InterviewStartResponse> {
  const res = await fetch(`${BASE}/api/interview/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_input: userInput, pipeline_result: pipelineResult || null }),
  })
  if (!res.ok) throw new Error(`Interview start failed: ${res.status}`)
  return res.json()
}

export async function replyInterview(
  sessionId: string,
  answer: string
): Promise<InterviewReplyResponse> {
  const res = await fetch(`${BASE}/api/interview/reply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, answer }),
  })
  if (!res.ok) throw new Error(`Interview reply failed: ${res.status}`)
  return res.json()
}

// ── Health ──

export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/health`)
    return res.ok
  } catch {
    return false
  }
}

// ── Knowledge Base ──

export async function uploadDocument(file: File, userId: string = 'default', docType: string = 'industry') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('user_id', userId)
  formData.append('doc_type', docType)

  const res = await fetch(`${BASE}/api/knowledge/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
  return res.json()
}

export async function listDocuments(userId: string = 'default') {
  const res = await fetch(`${BASE}/api/knowledge/documents?user_id=${userId}`)
  if (!res.ok) throw new Error(`List failed: ${res.status}`)
  return res.json()
}

export async function deleteDocument(filename: string, userId: string = 'default') {
  const res = await fetch(`${BASE}/api/knowledge/${encodeURIComponent(filename)}?user_id=${userId}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`)
  return res.json()
}

export async function searchKnowledge(query: string, userId: string = 'default', topK: number = 5) {
  const res = await fetch(`${BASE}/api/knowledge/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, query, top_k: topK }),
  })
  if (!res.ok) throw new Error(`Search failed: ${res.status}`)
  return res.json()
}

// ── Memory ──

export async function getUserMemory(userId: string = 'default') {
  const res = await fetch(`${BASE}/api/memory/${userId}`)
  if (!res.ok) throw new Error(`Memory fetch failed: ${res.status}`)
  return res.json()
}

// ── Session Recovery ──

export interface SavedSession {
  session_id: string
  user_id: string
  user_input: UserInput
  current_step: number
  results: Record<string, { agent_name: string; result: Record<string, unknown>; duration_s: number }>
  status: string
  created_at: string
  updated_at: string
}

export async function getActiveSession(userId: string = 'default'): Promise<{ exists: boolean; session?: SavedSession }> {
  const res = await fetch(`${BASE}/api/session/active?user_id=${userId}`)
  if (!res.ok) throw new Error(`Session fetch failed: ${res.status}`)
  return res.json()
}

export async function abandonSession(sessionId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/session/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Abandon failed: ${res.status}`)
}
