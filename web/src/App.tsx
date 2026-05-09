import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { BookOpen, User, Compass, LayoutGrid } from 'lucide-react'
import HomePage from './pages/HomePage'
import AnalyzePage from './pages/AnalyzePage'
import InterviewPage from './pages/InterviewPage'
import KnowledgePage from './pages/KnowledgePage'
import ProfilePage from './pages/ProfilePage'

export default function App() {
  const location = useLocation()
  const isHome = location.pathname === '/'

  return (
    <div className="min-h-screen bg-surface-0 text-text-primary bg-noise">
      {!isHome && (
        <nav className="sticky top-0 z-50 bg-surface-1/80 backdrop-blur-xl border-b border-border-subtle">
          <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
            <NavLink to="/" className="flex items-center gap-2.5 group">
              <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center group-hover:bg-accent/20 transition-colors">
                <Compass className="w-4 h-4 text-accent" />
              </div>
              <span className="font-semibold text-sm tracking-tight">转行帮</span>
            </NavLink>
            <div className="flex items-center gap-1">
              <NavItem to="/" icon={<LayoutGrid className="w-4 h-4" />} label="首页" />
              <NavItem to="/knowledge" icon={<BookOpen className="w-4 h-4" />} label="知识库" />
              <NavItem to="/profile" icon={<User className="w-4 h-4" />} label="我的" />
            </div>
          </div>
        </nav>
      )}

      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/interview" element={<InterviewPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Routes>
    </div>
  )
}

function NavItem({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-200 ${
          isActive
            ? 'bg-accent/10 text-accent'
            : 'text-text-muted hover:text-text-secondary hover:bg-surface-2'
        }`
      }
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </NavLink>
  )
}
