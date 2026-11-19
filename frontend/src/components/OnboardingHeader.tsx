import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { profileApi } from '@/api/profile'
import { Logo } from '@/components/Logo'
import { cn } from '@/lib/utils'

/** Escape hatch for the four onboarding screens (docs/DECISIONS.md D-13.3).
 *
 * Those screens deliberately render without `AppShell`: during first-run
 * signup there is nowhere to go but forward, and a nav bar inviting you to
 * abandon a half-finished profile is the wrong affordance. But they are also
 * the *edit* surface reached from the Profile hub — and entered that way they
 * were a dead end on desktop, with no header, no wordmark and no back button
 * (mobile at least had a bare back arrow). Found by the user on a live
 * walkthrough, not by any build or type check.
 *
 * The fix is scoped to that second case: the header only renders once the
 * user's profile is complete, which is exactly when they can have arrived
 * from Profile rather than from signup. Someone genuinely mid-signup still
 * sees the original uninterrupted flow.
 */
export function OnboardingHeader({
  /** Where "back" goes when there is no history to pop — landing on Profile
   * is friendlier than the match list, since that is the screen these are
   * linked from. */
  fallback = '/profile',
  /** Set by the screens that already draw their own back arrow at mobile
   * width, so this header does not stack a second one above it. */
  hasOwnMobileBack = false,
}: {
  fallback?: string
  hasOwnMobileBack?: boolean
}) {
  const navigate = useNavigate()

  // An existing preference profile is the signal that this is an *edit*
  // visit rather than a first run: `GET /profile` 404s until onboarding has
  // been completed once (verified against the running API — the same 404 the
  // user's own account was returning before it was seeded). `retry: false`
  // so that expected 404 doesn't churn through retries on every signup.
  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: () => profileApi.get(),
    retry: false,
  })

  // While loading — and during a genuine first-run signup — render no header,
  // rather than flashing one that may not belong on this visit. The ambient
  // field still mounts (D-13.11): the background belongs on these screens
  // either way, and it is the header specifically that is conditional.
  if (!profile) return null

  function goBack() {
    // A direct paste of /onboarding/weights has no in-app history to return
    // to; `navigate(-1)` there would leave the app entirely.
    if (window.history.length > 1) navigate(-1)
    else navigate(fallback)
  }

  return (
    <>
    {/* Was `hidden cohab-desktop:block` (D-13.11). That left the mobile
        breakpoint with no header at all, and `RequiredQuestionnaire` — unlike
        the other three onboarding screens — has no back control of its own,
        so editing the questionnaire from Profile on a phone was a dead end.
        The other three do carry their own mobile back affordance, which is
        why this header hides its arrow below the desktop breakpoint rather
        than stacking a second one on top of theirs. */}
    <header className="sticky top-0 z-40 bg-cohab-bg/95 backdrop-blur border-b border-cohab-border">
      <div className="max-w-[1160px] mx-auto px-4 cohab-desktop:px-6 h-14 cohab-desktop:h-[60px] flex items-center gap-3 cohab-desktop:gap-4">
        <button
          type="button"
          onClick={goBack}
          aria-label="Back"
          className={cn(
            'items-center justify-center w-8 h-8 -ml-1.5 rounded-full text-cohab-ink hover:bg-cohab-tint transition-colors cursor-pointer',
            // See the header comment: the three screens that already own a
            // mobile back control pass `hasOwnMobileBack`, so this one only
            // appears below the desktop breakpoint where nothing else does.
            hasOwnMobileBack ? 'hidden cohab-desktop:flex' : 'flex',
          )}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>

        <Link
          to="/matches"
          aria-label="Cohab — go to your matches"
          className="flex items-center transition-opacity hover:opacity-70 cohab-press"
        >
          <Logo />
        </Link>

        <div className="flex-1" />

        <Link
          to="/profile"
          className="text-sm font-medium text-cohab-muted hover:text-cohab-primary transition-colors"
        >
          Done editing
        </Link>
      </div>
    </header>
    </>
  )
}
