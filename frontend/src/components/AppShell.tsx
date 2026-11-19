import { Link, NavLink, useLocation } from 'react-router-dom'
import { useSession } from '@/hooks/useSession'
import { Logo } from '@/components/Logo'
import { ThemeSwitch } from '@/components/ThemeSwitch'
import { Roofline } from '@/components/Roofline'
import { ChartColumn, FlaskConical, MessageCircle, ShieldCheck, UserRound, Users } from 'lucide-react'
import { BottomNav } from '@/components/BottomNav'
import { BackButton } from '@/components/BackButton'
import { AccountMenu } from '@/components/AccountMenu'
import { PageTransition } from '@/components/motion/PageTransition'
import { ScrollProgress } from '@/components/motion/ScrollProgress'
import { cn } from '@/lib/utils'

/** The active underline is drawn by `.cohab-underline::after` (index.css) so
 * it can grow from the centre on hover as well as on becoming active — a
 * `border-b-2` can only appear at full width. The transparent border is kept
 * purely to reserve the same 2px of space it always did, so nothing shifts. */
function navLinkClass({ isActive }: { isActive: boolean }) {
  // Daylight nav (D-14.24): the active section is a cobalt-tinted pill.
  return cn(
    'cohab-press h-9 px-3.5 rounded-full inline-flex items-center gap-2 text-[14px] font-bold transition-colors [&>svg]:size-[16px]',
    isActive ? 'bg-cohab-tint text-cohab-primary' : 'text-cohab-muted hover:bg-cohab-tint hover:text-cohab-ink',
  )
}

function bottomNavTab(pathname: string): 'matches' | 'saved' | 'chats' | 'profile' {
  if (pathname.startsWith('/saved')) return 'saved'
  if (pathname.startsWith('/chats') || pathname.includes('/chat')) return 'chats'
  if (pathname.startsWith('/profile')) return 'profile'
  return 'matches'
}

/** Desktop: sticky top nav (Matches/Chat/Profile, per Cohab Desktop.html's
 * header). Mobile (<cohab-desktop breakpoint): floating bottom pill nav
 * (Matches/Saved/Chats/Profile, per Cohab Prototype.html) instead — the top
 * bar collapses to just the logo. "Blocked" moved into the Profile hub on
 * both breakpoints rather than living as a standalone nav link, since
 * neither mockup's header shows it directly. */
export function AppShell({ children, hideBottomNav }: { children: React.ReactNode; hideBottomNav?: boolean }) {
  const { data: user } = useSession()
  const { pathname } = useLocation()

  // The conversation surfaces nested under a match: the thread itself and the
  // contact-share step that follows it. Both belong to Chat in the nav even
  // though their URLs sit under /matches/:id/.
  const isChat = pathname.startsWith('/chats') || /^\/matches\/[^/]+\/(chat|contact-share)/.test(pathname)
  // Match detail (/matches/:id) is still Matches, so `end` on that NavLink is
  // paired with this explicit test rather than left to prefix matching.
  const isMatches = pathname === '/matches' || (pathname.startsWith('/matches/') && !isChat)

  return (
    // No `bg-cohab-bg` here on purpose (D-13.11): an opaque background on the
    // shell root would paint straight over the fixed canvas behind it. The
    // page's black comes from `body` (index.css), which sits below both.
    <div className="min-h-screen pb-20 cohab-desktop:pb-0">
      <Roofline className="fixed inset-x-0 bottom-0 h-[130px] cohab-desktop:h-[170px] w-full -z-10" />
      <header className="sticky top-0 z-40 bg-cohab-card/80 backdrop-blur-xl backdrop-saturate-150 border-b border-cohab-border-soft">
        <ScrollProgress />
        <div className="max-w-5xl cohab-desktop:max-w-[1800px] mx-auto px-4 cohab-desktop:px-6 h-14 cohab-desktop:h-[60px] flex items-center gap-3 cohab-desktop:gap-4">
          <BackButton pathname={pathname} />
          {/* The wordmark is the app's "home" affordance on both breakpoints —
              it goes to /matches, which is what "/" redirects to (App.tsx). */}
          <Link
            to="/matches"
            aria-label="Cohab — go to your matches"
            className="flex items-center gap-6 cohab-desktop:gap-[34px] transition-opacity hover:opacity-70 cohab-press"
          >
            <Logo />
          </Link>
          <nav className="hidden cohab-desktop:flex items-center gap-1.5 ml-4">
            {/* Active state is computed above rather than left to NavLink's
                prefix matching: the chat and contact-share routes live under
                /matches/:id/…, so by default an open chat thread underlined
                Matches while Chat stayed inactive (reported by the user).
                This mirrors what `bottomNavTab` already did on mobile. */}
            <NavLink to="/matches" className={() => navLinkClass({ isActive: isMatches })}>
              <Users aria-hidden />
              Matches
            </NavLink>
            <NavLink to="/chats" className={({ isActive }) => navLinkClass({ isActive: isActive || isChat })}>
              <MessageCircle aria-hidden />
              Chat
            </NavLink>
            <NavLink to="/profile" className={navLinkClass}>
              <UserRound aria-hidden />
              Profile
            </NavLink>
            {user?.is_moderator && (
              <NavLink to="/moderation" className={navLinkClass}>
                <ShieldCheck aria-hidden />
                Moderation
              </NavLink>
            )}
            {user?.is_moderator && (
              <NavLink to="/analytics" className={navLinkClass}>
                <ChartColumn aria-hidden />
                Analytics
              </NavLink>
            )}
            {user?.is_moderator && (
              <NavLink to="/evidence" className={navLinkClass}>
                <FlaskConical aria-hidden />
                Evidence
              </NavLink>
            )}
          </nav>
          <div className="flex-1" />
          <ThemeSwitch />
          {user && <AccountMenu user={user} />}
        </div>
      </header>
      <main>
        <PageTransition>{children}</PageTransition>
      </main>
      {!hideBottomNav && <BottomNav active={bottomNavTab(pathname)} />}
    </div>
  )
}
