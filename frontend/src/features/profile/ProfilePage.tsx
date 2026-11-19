import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useSession } from '@/hooks/useSession'
import { profileApi } from '@/api/profile'
import { listingApi } from '@/api/listing'
import { ApiError } from '@/api/client'
import { AppShell } from '@/components/AppShell'
import { PageBanner } from '@/components/PageBanner'
import { ProfileSummaryRail } from './ProfileSummaryRail'
import { AccountPanel } from './AccountPanel'
import { ListingPanel } from './ListingPanel'
import { Eyebrow } from '@/components/Eyebrow'
import { cn } from '@/lib/utils'
import {
  REQUIRED_QUESTIONNAIRE_KEYS,
  OPTIONAL_TIER2_QUESTIONS,
  WEIGHT_TILES,
} from '@/data/questionnaire'

/** Mobile mockup Cohab Prototype.html #sProfile (fourth bottom-nav tab) and
 * the desktop mockup's header "Profile" link, which points nowhere in either
 * mockup's own screen set — Cohab Desktop.html has no dedicated Profile
 * screen among its 13. The desktop layout below is therefore this
 * component's own judgment call: same card/Eyebrow language as the rest of
 * that mockup (white cards, 1px #485346 border, 16-18px radius), centered in
 * a max-width column matching the desktop mockup's other single-column
 * screens — Contact Share (`max-width:760px`, page.html line 737) and
 * Report (`max-width:680px`, line 777) — rather than literal extraction,
 * since no such screen exists to extract from.
 *
 * Renders at /profile (route added centrally elsewhere); takes no params. */

const OPTIONAL_KEYS = OPTIONAL_TIER2_QUESTIONS.flatMap((q) => q.parts.map((p) => p.key))
const OPTIONAL_TOTAL = OPTIONAL_KEYS.length + 2 // + interests + lifestyle_notes, per ImportanceWeights.tsx's save payload

function isFilled(value: unknown): boolean {
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'string') return value.trim().length > 0
  return value !== undefined && value !== null
}

function Row({
  to,
  label,
  status,
  statusTone = 'muted',
}: {
  to: string
  label: string
  status?: string | null
  statusTone?: 'muted' | 'primary' | 'accent'
}) {
  return (
    <Link
      to={to}
      className="flex items-center justify-between gap-3 py-3.5 border-b border-cohab-border-soft last:border-b-0 no-underline"
    >
      <div>
        <div className="text-[15px] font-medium text-cohab-ink">{label}</div>
        {status && (
          <div
            className={cn(
              'text-[13px] mt-0.5',
              statusTone === 'primary' && 'text-cohab-primary',
              statusTone === 'accent' && 'text-cohab-accent',
              statusTone === 'muted' && 'text-cohab-muted',
            )}
          >
            {status}
          </div>
        )}
      </div>
      <span className="text-cohab-subtle text-base flex-none">&rsaquo;</span>
    </Link>
  )
}

function DisabledRow({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-3.5 border-b border-cohab-border-soft last:border-b-0">
      <span className="text-[15px] font-medium text-cohab-subtle">{label}</span>
      <span className="text-[11px] font-medium text-cohab-subtle border border-cohab-border rounded px-1.5 py-0.5 flex-none">
        Coming soon
      </span>
    </div>
  )
}

export function ProfilePage() {
  const { data: user } = useSession()

  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: async () => {
      try {
        return await profileApi.get()
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null
        throw e
      }
    },
  })

  const { data: listing } = useQuery({
    queryKey: ['listing'],
    queryFn: async () => {
      try {
        return await listingApi.get()
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null
        throw e
      }
    },
    enabled: user?.seeker_type === 'has_place',
  })

  if (!user) {
    return (
      <AppShell>
        <div className="max-w-md mx-auto px-4 py-10 text-cohab-muted">Loading…</div>
      </AppShell>
    )
  }

  const answers = profile?.questionnaire ?? {}
  const requiredDone = REQUIRED_QUESTIONNAIRE_KEYS.filter((k) => isFilled(answers[k])).length
  const requiredTotal = REQUIRED_QUESTIONNAIRE_KEYS.length
  const requiredAllDone = requiredDone === requiredTotal

  const optionalDone =
    OPTIONAL_KEYS.filter((k) => isFilled(answers[k])).length +
    (isFilled(answers.interests) ? 1 : 0) +
    (isFilled(answers.lifestyle_notes) ? 1 : 0)

  const priorityLabels = (profile?.important_attributes ?? [])
    .map((id) => WEIGHT_TILES.find((t) => t.id === id)?.title)
    .filter((t): t is string => Boolean(t))

  const isVerified = user.verification_status === 'verified'
  const seekerLine =
    user.seeker_type === 'has_place'
      ? 'Has a place'
      : profile
        ? `Looking for a place · ₹${profile.budget_min.toLocaleString('en-IN')}–${profile.budget_max.toLocaleString('en-IN')}`
        : 'Looking for a place'

  return (
    <AppShell>
      {/* Two-column on desktop (docs/DECISIONS.md D-13.8). Was a 720px
          column centred in an 1800px viewport, which left most of the screen
          empty — reported by the user. The right rail shows the hard
          constraints and lifestyle answers already fetched by the `profile`
          query but previously never rendered anywhere on this screen. */}
      <div className="px-4 py-5 cohab-desktop:max-w-[1800px] cohab-desktop:mx-auto cohab-desktop:px-6 cohab-desktop:py-10 cohab-desktop:grid cohab-desktop:grid-cols-[minmax(0,1fr)_460px] cohab-desktop:gap-6 cohab-desktop:items-start">
        <div className="min-w-0">
        {/* Editable account details + avatar (D-13.9) — replaces the static
            header, which showed the same fields with no way to change any. */}
        <PageBanner photo="/photos/bedroom-warm.webp" label="Your profile" title={user.full_name?.split(" ")[0] || "You"} size="sm" className="mb-4">
          <p className="text-[14px] text-white/85">{seekerLine}</p>
        </PageBanner>
        <AccountPanel user={user} />

        {isVerified && (
          <div className="flex items-center gap-2.5 px-1 py-3.5 mb-1 cohab-desktop:bg-cohab-tint cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-2xl cohab-desktop:px-4 cohab-desktop:mb-5">
            <div className="w-5 h-5 rounded-full bg-cohab-fill text-cohab-on-fill text-[11px] font-semibold flex items-center justify-center flex-none">
              &#10003;
            </div>
            <span className="text-[13.5px] font-medium text-cohab-primary">
              Verified student{user.email ? ` · ${user.email}` : ''}
            </span>
          </div>
        )}

        {/* Your answers */}
        <div className="mt-5 cohab-desktop:bg-cohab-card cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-[18px] cohab-desktop:p-7 cohab-desktop:mb-5">
          <Eyebrow className="mb-3">Your answers</Eyebrow>
          <Row
            to="/onboarding/questionnaire"
            label="Required questions"
            status={`${requiredDone} of ${requiredTotal} answered`}
            statusTone={requiredAllDone ? 'primary' : 'accent'}
          />
          <Row
            to="/onboarding/optional"
            label="Optional questions"
            status={
              optionalDone === OPTIONAL_TOTAL
                ? `${optionalDone} of ${OPTIONAL_TOTAL} answered`
                : `${optionalDone} of ${OPTIONAL_TOTAL} answered — finish anytime`
            }
            statusTone={optionalDone === OPTIONAL_TOTAL ? 'primary' : 'accent'}
          />
          <Row
            to="/onboarding/weights"
            label="What matters most"
            status={priorityLabels.length > 0 ? priorityLabels.join(' · ') : null}
          />
        </div>

        {/* Full listing detail rather than an "Added" row (D-13.9) — the
            `listing` query already ran above, so this costs no extra call. */}
        {user.seeker_type === 'has_place' && <ListingPanel listing={listing} />}

        {/* Privacy and safety */}
        <div className="mt-2 cohab-desktop:bg-cohab-card cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-[18px] cohab-desktop:p-7">
          <Eyebrow className="mb-3">Privacy and safety</Eyebrow>

          {/* Phone number is edited in the account panel above; this row is
              the privacy explanation for it, not a second control. */}
          <div className="py-3.5 border-b border-cohab-border-soft">
            <div className="text-[15px] font-medium text-cohab-ink">Phone number</div>
            <div className="text-[13px] text-cohab-muted mt-0.5 leading-[1.45]">
              {user.phone_number
                ? 'On file. Hidden by default, shared with one match at a time, only after you both agree.'
                : "Not added yet — use Edit above. It stays hidden until you agree to share it."}
            </div>
          </div>

          <Row to="/blocked" label="Blocked people" />
          <DisabledRow label="Consent and data" />
          <DisabledRow label="Pause my profile" />

          <p className="text-[12.5px] text-cohab-subtle leading-[1.5] mt-4">
            Pausing hides you from everyone's matches and keeps your answers. You can come back
            without redoing the questionnaire.
          </p>
        </div>
        </div>

        <ProfileSummaryRail profile={profile} />
      </div>
    </AppShell>
  )
}
