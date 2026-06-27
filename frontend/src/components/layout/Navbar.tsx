import { Link, useNavigate } from 'react-router-dom'
import { TrendingUp, LogOut, PlusCircle } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'

export function Navbar() {
  const { user, signOut } = useAuthStore()
  const navigate = useNavigate()

  const handleSignOut = async () => {
    await signOut()
    navigate('/login')
  }

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link to="/" className="flex items-center gap-2 font-bold text-brand-700">
          <TrendingUp className="h-5 w-5" />
          MarketLens
        </Link>

        <div className="flex items-center gap-3">
          <span className="hidden text-sm text-slate-500 sm:block">{user?.email}</span>
          <Link to="/research/new" className="btn-primary py-1.5 text-xs">
            <PlusCircle className="h-3.5 w-3.5" />
            New Research
          </Link>
          <button onClick={handleSignOut} className="btn-secondary py-1.5 text-xs">
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </div>
    </header>
  )
}
