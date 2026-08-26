import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

type Tab = 'matches' | 'saved' | 'chats' | 'profile'

const ACTIVE = '#7fee64'
const INACTIVE = '#677d64'

function MatchesIcon({ color }: { color: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.7" strokeLinecap="round">
      <circle cx="9" cy="8" r="3.3" />
      <path d="M3.6 19c.7-3.3 2.9-5.2 5.4-5.2s4.7 1.9 5.4 5.2" />
      <path d="M16.2 6.2a3 3 0 010 5.6M17.5 14.4c1.8.7 3 2.3 3.4 4.6" />
    </svg>
  )
}

function SavedIcon({ color }: { color: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.7" strokeLinejoin="round">
      <path d="M6.5 4.5h11v15l-5.5-3.8-5.5 3.8z" />
    </svg>
  )
}

function ChatsIcon({ color }: { color: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.7" strokeLinejoin="round">
      <path d="M4 6.5a2 2 0 012-2h12a2 2 0 012 2v7a2 2 0 01-2 2H9.5L4.8 19z" />
    </svg>
  )
}

function ProfileIcon({ color }: { color: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.7" strokeLinecap="round">
      <circle cx="12" cy="8" r="3.4" />
      <path d="M5 19.5c.8-3.7 3.5-5.8 7-5.8s6.2 2.1 7 5.8" />
    </svg>
  )
}

const TABS: { key: Tab; to: string; icon: (color: string) => React.ReactNode }[] = [
  { key: 'matches', to: '/matches', icon: (c) => <MatchesIcon color={c} /> },
  { key: 'saved', to: '/saved', icon: (c) => <SavedIcon color={c} /> },
  { key: 'chats', to: '/chats', icon: (c) => <ChatsIcon color={c} /> },
  { key: 'profile', to: '/profile', icon: (c) => <ProfileIcon color={c} /> },
]

export function BottomNav({ active, unreadChatCount }: { active: Tab; unreadChatCount?: number }) {
  return (
    <nav
      className={cn(
        'cohab-desktop:hidden fixed bottom-1.5 left-1/2 -translate-x-1/2 z-40',
        'flex items-center gap-0.5 rounded-full bg-cohab-card/90 backdrop-blur-md p-1.5',
        'shadow-[0_10px_15px_-3px_rgba(0,0,0,.5),0_4px_6px_-4px_rgba(0,0,0,.5)] border border-cohab-border',
      )}
    >
      {TABS.map((tab) => {
        const isActive = active === tab.key
        const color = isActive ? ACTIVE : INACTIVE
        return (
          <Link
            key={tab.key}
            to={tab.to}
            className="relative w-[54px] min-h-9 flex items-center justify-center rounded-full py-1.5"
          >
            {tab.icon(color)}
            {tab.key === 'chats' && unreadChatCount ? (
              <span className="absolute top-[5px] right-[calc(50%-17px)] min-w-4 h-4 px-1 box-border rounded-full bg-cohab-accent text-cohab-on-fill text-[10px] font-semibold leading-4 text-center">
                {unreadChatCount}
              </span>
            ) : null}
          </Link>
        )
      })}
    </nav>
  )
}
