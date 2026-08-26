import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { useSetSession } from '@/hooks/useSession'
import { Avatar } from '@/components/ui/avatar'
import { ThemeToggle } from '@/components/ThemeToggle'
import type { UserOut } from '@/api/types'
import { cn } from '@/lib/utils'

export function AccountMenu({ user }: { user: UserOut }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const setSession = useSetSession()

  useEffect(() => {
    if (!open) return
    function onClickOutside(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    function onEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    document.addEventListener('keydown', onEscape)
    return () => {
      document.removeEventListener('mousedown', onClickOutside)
      document.removeEventListener('keydown', onEscape)
    }
  }, [open])

  async function handleLogout() {
    setOpen(false)
    try {
      await authApi.logout()
    } finally {
      setSession(null)
      navigate('/login', { replace: true })
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="cohab-press rounded-full cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-cohab-primary"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Avatar name={user.full_name} src={user.avatar_url} size={30} />
      </button>
      <div
        role="menu"
        className={cn(
          'absolute right-0 top-[calc(100%+8px)] w-64 rounded-xl border border-cohab-border bg-cohab-card shadow-lg py-1.5 z-50',
          'origin-top-right transition duration-150 ease-out',
          open ? 'opacity-100 scale-100 pointer-events-auto' : 'opacity-0 scale-95 pointer-events-none',
        )}
      >
        <div className="px-4 py-2.5 border-b border-cohab-border-soft">
          <div className="text-sm font-semibold text-cohab-ink truncate">{user.full_name}</div>
          <div className="text-xs text-cohab-muted truncate mt-0.5">{user.email}</div>
        </div>
        <button
          type="button"
          role="menuitem"
          onClick={() => {
            setOpen(false)
            navigate('/profile')
          }}
          className="w-full text-left px-4 py-2 text-sm text-cohab-ink hover:bg-cohab-tint transition-colors"
        >
          Profile
        </button>
        {/* Appearance sits above Log out so the destructive item stays last
            (D-13.12). Not a menuitem — it is a segmented control, and the
            menu stays open while you compare the two themes. */}
        <div className="px-4 py-2.5 border-t border-cohab-border-soft">
          <div className="text-[11px] font-medium uppercase tracking-[.06em] text-cohab-subtle mb-1.5">
            Appearance
          </div>
          <ThemeToggle />
        </div>
        <button
          type="button"
          role="menuitem"
          onClick={handleLogout}
          className="w-full text-left px-4 py-2 text-sm text-cohab-accent hover:bg-cohab-accent-tint transition-colors border-t border-cohab-border-soft"
        >
          Log out
        </button>
      </div>
    </div>
  )
}
