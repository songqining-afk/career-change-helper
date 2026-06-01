import { useState, useEffect } from 'react'
import { User, Calendar, TrendingUp, Target, Loader2 } from 'lucide-react'

interface UserProfile {
  user_id: string
  name?: string
  age?: number
  city?: string
  education?: string
  years_of_experience?: number
  current_role?: string
  current_industry?: string
  target_direction?: string
  transition_stage?: string
  confidence_level?: string
}

interface Event {
  event_id: string
  event_type: string
  timestamp: string
  summary: string
  metadata: Record<string, unknown>
}

interface Preference {
  key: string
  value: string
  source: string
  confidence: number
}

export default function ProfilePage() {
  const [userId] = useState('default')
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [preferences, setPreferences] = useState<Preference[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadMemory()
  }, [])

  async function loadMemory() {
    setLoading(true)
    try {
      const res = await fetch(`/api/memory/${userId}`)
      if (res.ok) {
        const data = await res.json()
        setProfile(data.profile)
        setEvents(data.recent_events || [])
        setPreferences(data.preferences || [])
      }
    } catch (e) {
      console.error('Failed to load memory:', e)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-accent" />
      </div>
    )
  }

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text-primary">我的进度</h1>
          <p className="text-text-muted text-sm mt-1">转行记忆与历史轨迹</p>
        </div>

        {/* Profile card */}
        {profile ? (
          <div className="card-surface p-6 space-y-5">
            <div className="flex items-center gap-2">
              <User className="w-4 h-4 text-accent" />
              <h2 className="text-sm font-semibold text-text-secondary">用户画像</h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {profile.name && <InfoItem label="姓名" value={profile.name} />}
              {profile.age && <InfoItem label="年龄" value={`${profile.age} 岁`} />}
              {profile.city && <InfoItem label="城市" value={profile.city} />}
              {profile.education && <InfoItem label="学历" value={profile.education} />}
              {profile.years_of_experience !== undefined && (
                <InfoItem label="工作年限" value={`${profile.years_of_experience} 年`} />
              )}
              {profile.current_role && <InfoItem label="当前职位" value={profile.current_role} />}
              {profile.current_industry && <InfoItem label="当前行业" value={profile.current_industry} />}
              {profile.target_direction && (
                <InfoItem
                  label="目标方向"
                  value={profile.target_direction}
                  icon={<Target className="w-3.5 h-3.5 text-accent" />}
                />
              )}
              {profile.transition_stage && <InfoItem label="转行阶段" value={profile.transition_stage} />}
              {profile.confidence_level && <InfoItem label="信心水平" value={profile.confidence_level} />}
            </div>
          </div>
        ) : (
          <div className="card-surface p-10 text-center">
            <div className="w-12 h-12 rounded-full bg-surface-2 flex items-center justify-center mx-auto mb-3">
              <User className="w-5 h-5 text-text-muted" />
            </div>
            <p className="text-sm text-text-muted">还没有用户画像</p>
            <p className="text-xs text-text-muted mt-1">完成一次分析后会自动生成</p>
          </div>
        )}

        {/* Preferences */}
        {preferences.length > 0 && (
          <div className="card-surface p-6 space-y-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-accent" />
              <h2 className="text-sm font-semibold text-text-secondary">偏好记录</h2>
            </div>
            <div className="space-y-2">
              {preferences.map((pref, i) => (
                <div key={i} className="flex items-center justify-between rounded-xl bg-surface-0 ring-1 ring-black/[0.05] p-3.5">
                  <div className="flex items-center gap-3">
                    <span className="text-xs px-2 py-0.5 bg-accent/10 text-accent rounded font-medium">
                      {pref.key}
                    </span>
                    <span className="text-sm text-text-primary">{pref.value}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-text-muted">
                    <span>{pref.source === 'explicit' ? '明确' : '推断'}</span>
                    <span className="text-border">·</span>
                    <span>{(pref.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Event timeline */}
        {events.length > 0 && (
          <div className="card-surface p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-accent" />
              <h2 className="text-sm font-semibold text-text-secondary">历史事件</h2>
            </div>
            <div className="space-y-3">
              {events.map((event) => (
                <div key={event.event_id} className="border-l-2 border-accent/20 pl-4 py-2">
                  <div className="flex items-center gap-2 text-xs">
                    <EventTypeBadge type={event.event_type} />
                    <span className="text-text-muted">
                      {new Date(event.timestamp).toLocaleString('zh-CN')}
                    </span>
                  </div>
                  <p className="text-sm text-text-secondary mt-1.5">{event.summary}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {events.length === 0 && preferences.length === 0 && !profile && (
          <div className="card-surface p-14 text-center">
            <div className="w-14 h-14 rounded-full bg-surface-2 flex items-center justify-center mx-auto mb-4">
              <Calendar className="w-6 h-6 text-text-muted" />
            </div>
            <p className="text-sm text-text-muted">还没有历史记录</p>
            <p className="text-xs text-text-muted mt-1">开始你的第一次分析吧</p>
          </div>
        )}
      </div>
    </div>
  )
}

function InfoItem({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-xs text-text-muted">{label}</p>
      <div className="flex items-center gap-1.5">
        {icon}
        <p className="text-sm text-text-primary font-medium">{value}</p>
      </div>
    </div>
  )
}

function EventTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    analysis: 'bg-accent/10 text-accent ring-1 ring-accent/12',
    interview: 'bg-surface-3 text-text-secondary ring-1 ring-border',
    direction: 'bg-success/10 text-success ring-1 ring-success/12',
    milestone: 'bg-amber-50 text-warning ring-1 ring-warning/20',
    feedback: 'bg-surface-2 text-text-secondary ring-1 ring-black/[0.06]',
  }

  const labels: Record<string, string> = {
    analysis: '分析',
    interview: '面试',
    direction: '方向',
    milestone: '里程碑',
    feedback: '反馈',
  }

  return (
    <span className={`text-xs px-2 py-0.5 rounded-md font-medium ${colors[type] || 'bg-surface-3 text-text-muted ring-1 ring-border'}`}>
      {labels[type] || type}
    </span>
  )
}
