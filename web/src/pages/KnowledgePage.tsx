import { useState, useEffect } from 'react'
import { Upload, FileText, Trash2, Loader2, Search } from 'lucide-react'
import { useToast } from '../components/Toast'

interface Document {
  filename: string
  doc_type: string
  chunk_count: number
  uploaded_at: string
}

export default function KnowledgePage() {
  const { toast } = useToast()
  const [userId] = useState('default')
  const [documents, setDocuments] = useState<Document[]>([])
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Array<{ text: string; score: number }>>([])
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    loadDocuments()
  }, [])

  async function loadDocuments() {
    setLoading(true)
    try {
      const res = await fetch(`/api/knowledge/documents?user_id=${userId}`)
      if (res.ok) {
        const data = await res.json()
        setDocuments(data.documents || [])
      }
    } catch (e) {
      console.error('Failed to load documents:', e)
    } finally {
      setLoading(false)
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)
    formData.append('user_id', userId)
    formData.append('doc_type', 'industry')

    setUploading(true)
    try {
      const res = await fetch('/api/knowledge/upload', {
        method: 'POST',
        body: formData,
      })
      if (res.ok) {
        await loadDocuments()
      } else {
        const err = await res.json()
        toast(`上传失败: ${err.detail || res.statusText}`, 'error')
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : '上传失败', 'error')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  async function handleDelete(filename: string) {
    if (!confirm(`确定删除 ${filename}?`)) return

    try {
      const res = await fetch(`/api/knowledge/${encodeURIComponent(filename)}?user_id=${userId}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        await loadDocuments()
      } else {
        toast('删除失败', 'error')
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : '删除失败', 'error')
    }
  }

  async function handleSearch() {
    if (!searchQuery.trim()) return

    setSearching(true)
    try {
      const res = await fetch('/api/knowledge/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, query: searchQuery, top_k: 5 }),
      })
      if (res.ok) {
        const data = await res.json()
        setSearchResults(data.results || [])
      } else {
        toast('搜索失败', 'error')
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : '搜索失败', 'error')
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-text-primary">知识库</h1>
            <p className="text-text-muted text-sm mt-1">
              上传行业报告、岗位 JD 等文档，AI 会在分析时自动检索
            </p>
          </div>
          <label className="px-4 py-2.5 bg-accent hover:bg-accent-soft rounded-xl cursor-pointer flex items-center gap-2 text-sm font-medium text-white transition-colors shadow-sm">
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                上传中
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                上传文档
              </>
            )}
            <input
              type="file"
              accept=".pdf,.txt,.md"
              onChange={handleUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
        </div>

        {/* Search */}
        <div className="card-surface p-5 space-y-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="搜索知识库..."
              className="flex-1 bg-surface-0 border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted/80 focus:outline-none focus:ring-2 focus:ring-accent/25 focus:border-accent/40 transition-shadow"
            />
            <button
              onClick={handleSearch}
              disabled={!searchQuery.trim() || searching}
              className="px-4 py-2.5 bg-surface-1 hover:bg-surface-2 disabled:opacity-35 rounded-xl flex items-center gap-2 transition-colors ring-1 ring-border"
            >
              {searching ? (
                <Loader2 className="w-4 h-4 animate-spin text-text-muted" />
              ) : (
                <Search className="w-4 h-4 text-text-secondary" />
              )}
            </button>
          </div>

          {searchResults.length > 0 && (
            <div className="space-y-2 pt-2 border-t border-border-subtle">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">搜索结果</h3>
              {searchResults.map((r, i) => (
                <div key={i} className="rounded-xl bg-surface-0 ring-1 ring-black/[0.05] p-3.5">
                  <p className="text-xs text-text-secondary leading-relaxed">{r.text}</p>
                  <span className="text-xs text-text-muted mt-2 inline-block">
                    相关度 {(r.score * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Documents list */}
        <div className="card-surface p-5">
          <h2 className="text-sm font-semibold text-text-secondary mb-4">已上传文档</h2>

          {loading ? (
            <div className="flex items-center justify-center py-12 text-text-muted">
              <Loader2 className="w-5 h-5 animate-spin mr-2" />
              <span className="text-sm">加载中</span>
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-12 h-12 rounded-full bg-surface-2 flex items-center justify-center mx-auto mb-3">
                <FileText className="w-5 h-5 text-text-muted" />
              </div>
              <p className="text-sm text-text-muted">还没有上传任何文档</p>
              <p className="text-xs text-text-muted mt-1">支持 PDF、TXT、Markdown 格式</p>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.filename}
                  className="flex items-center justify-between rounded-xl bg-surface-0 ring-1 ring-black/[0.05] p-4 hover:ring-border transition-shadow"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-surface-1 flex items-center justify-center ring-1 ring-black/[0.06]">
                      <FileText className="w-4 h-4 text-accent" />
                    </div>
                    <div>
                      <p className="text-sm text-text-primary font-medium">{doc.filename}</p>
                      <p className="text-xs text-text-muted">
                        {doc.chunk_count} 个片段 · {new Date(doc.uploaded_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(doc.filename)}
                    className="p-2 text-text-muted hover:text-danger hover:bg-danger/10 rounded-lg transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
