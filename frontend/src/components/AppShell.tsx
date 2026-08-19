import { NavLink } from 'react-router-dom'
import { useSession } from '@/hooks/useSession'
import { Avatar } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'

/** Sticky top nav for the signed-in app. No "Chat" link in the global nav —
 * chat is per-match, reached from match detail once a match is mutual or
 * later (PRD has no chat-inbox screen). */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: user } = useSession()

  return (
    <div className="min-h-screen bg-cohab-bg">
      <header className="sticky top-0 z-40 bg-cohab-bg/95 backdrop-blur border-b border-cohab-border">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-6">
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold tracking-tight text-cohab-primary">Cohab</span>
            <span className="font-mono text-[9px] uppercase tracking-wider text-cohab-subtle border border-cohab-border rounded px-1.5 py-0.5">
              Pilot
            </span>
          </div>
          <nav className="flex items-center gap-5">
            <NavLink
              to="/matches"
              className={({ isActive }) =>
                cn(
                  'text-sm pb-1 border-b-2',
                  isActive
                    ? 'font-semibold text-cohab-ink border-cohab-primary'
                    : 'text-cohab-muted border-transparent',
                )
              }
            >
              Matches
            </NavLink>
          </nav>
          <div className="flex-1" />
          {user && <Avatar name={user.full_name} src={user.avatar_url} size={30} />}
        </div>
      </header>
      <main>{children}</main>
    </div>
  )
}
