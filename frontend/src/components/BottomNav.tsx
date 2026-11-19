import { Link } from 'react-router-dom'
import { Bookmark, MessageCircle, UserRound, Users } from 'lucide-react'
import { cn } from '@/lib/utils'

type Tab = 'matches' | 'saved' | 'chats' | 'profile'

const TABS: { key: Tab; to: string; label: string; Icon: typeof Users }[] = [
  { key: 'matches', to: '/matches', label: 'Matches', Icon: Users },
  { key: 'saved', to: '/saved', label: 'Saved', Icon: Bookmark },
  { key: 'chats', to: '/chats', label: 'Chats', Icon: MessageCircle },
  { key: 'profile', to: '/profile', label: 'Profile', Icon: UserRound },
]

/** Floating tab bar for phones (D-14.25): a navy capsule; the current tab
 * opens into a white pill with its name, the others stay icon-only. */
export function BottomNav({ active, unreadChatCount }: { active: Tab; unreadChatCount?: number }) {
  return (
    <nav
      aria-label="Main"
      className={cn(
        'cohab-desktop:hidden fixed bottom-3 left-1/2 -translate-x-1/2 z-40',
        'flex items-center gap-1 rounded-full bg-[#0b1033]/92 backdrop-blur-xl p-1.5',
        'shadow-[0_18px_40px_-14px_rgb(11_16_51/0.6)] ring-1 ring-white/10',
      )}
    >
      {TABS.map(({ key, to, label, Icon }) => {
        const on = active === key
        return (
          <Link
            key={key}
            to={to}
            aria-label={label}
            aria-current={on ? 'page' : undefined}
            className={cn(
              'relative h-11 flex items-center justify-center gap-2 rounded-full transition-[background-color,color,padding,width] duration-300 ease-[cubic-bezier(.22,1,.36,1)]',
              on ? 'bg-white text-[#0b1033] px-4 shadow-[inset_0_1px_0_rgb(255_255_255),0_4px_12px_-4px_rgb(0_0_0/0.4)]' : 'w-12 text-white/60 hover:text-white',
            )}
          >
            <Icon className="size-5" strokeWidth={on ? 2.4 : 2} aria-hidden />
            {on && <span className="text-[13px] font-bold">{label}</span>}
            {key === 'chats' && unreadChatCount ? (
              <span className="absolute top-1 right-1 min-w-4 h-4 px-1 rounded-full bg-cohab-sun text-cohab-on-sun text-[10px] font-bold leading-4 text-center">
                {unreadChatCount}
              </span>
            ) : null}
          </Link>
        )
      })}
    </nav>
  )
}
