import { Navigate } from 'react-router-dom'
import { useSession } from '@/hooks/useSession'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { data: user, isLoading } = useSession()

  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center text-cohab-muted">Loading…</div>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}
