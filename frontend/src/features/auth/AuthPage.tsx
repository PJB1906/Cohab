import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoginForm } from './LoginForm'
import { SignUpWizard } from './SignUpWizard'
import { Logo } from '@/components/Logo'
import { HeroStagger } from '@/components/motion/HeroStagger'
import { CompatibilityField } from '@/components/CompatibilityField'

const LANDING_STATS: { big: string; caption: string }[] = [
  { big: '12', caption: 'lifestyle questions, under 4 minutes' },
  { big: '2', caption: 'stage matching — hard filters, then a weighted score' },
  { big: '100%', caption: 'of matches come with a plain-language reason' },
]

const LANDING_STEPS: { title: string; body: string }[] = [
  {
    title: 'Verify your student email',
    body: 'A one-time code confirms you belong to the campus before anything else happens.',
  },
  {
    title: 'Answer twelve questions',
    body: 'Sleep, cleanliness, guests, noise and budget — the things that actually make or break living together.',
  },
  {
    title: 'Get a ranked, explainable shortlist',
    body: 'Every match shows the reasons it was suggested, including where the two of you disagree.',
  },
  {
    title: 'Chat once you both opt in',
    body: 'Contact details stay private until you and a match choose to share them.',
  },
]

const LANDING_CHIPS = [
  'Verified students only',
  'Contact details stay private',
  'Report or block anytime',
  'No rent or deposits handled here',
]

/** Two-column desktop shell (marketing panel + auth panel) that wraps the
 * login form and the signup wizard's account/OTP steps — mockup screen 1.
 * The wizard's seeker-type step (screen 2) does not use this shell; it has
 * its own centred layout. Mobile never shows the marketing panel. */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col cohab-desktop:grid cohab-desktop:grid-cols-[minmax(0,1fr)_minmax(460px,40%)]">
      {/* `relative` so the ambient canvas can sit behind the copy; the panel's
          own children are lifted above it with `relative z-10`. */}
      <HeroStagger className="hidden cohab-desktop:flex cohab-desktop:flex-col relative overflow-hidden cohab-desktop:border-r cohab-desktop:border-cohab-border cohab-desktop:pt-12 cohab-desktop:pr-[60px] cohab-desktop:pb-10 cohab-desktop:pl-12 cohab-desktop:box-border">
        <CompatibilityField className="absolute inset-0 w-full h-full pointer-events-none opacity-70" />
        <Logo className="mb-11 relative z-10" data-stagger-item="" />
        <h1 data-stagger-item="" className="relative z-10 text-[34px] font-semibold leading-[1.14] tracking-[-0.02em] mb-3.5 max-w-[540px]">
          Find someone you can actually live with.
        </h1>
        <p data-stagger-item="" className="relative z-10 text-base leading-[1.55] text-cohab-muted mb-[30px] max-w-[540px]">
          Cohab compares how you sleep, clean, host and pay before it introduces anyone. Every
          match comes with the reasons behind it — including the one thing you disagree on.
        </p>

        <div data-stagger-item="" className="relative z-10 grid grid-cols-3 gap-px bg-cohab-border border border-cohab-border rounded-[14px] overflow-hidden mb-[30px]">
          {LANDING_STATS.map((s) => (
            <div key={s.caption} className="bg-cohab-bg px-4 py-[15px]">
              <span className="block text-[22px] font-semibold leading-[1.1] tracking-[-0.02em]">{s.big}</span>
              <span className="block text-[12.5px] leading-[1.35] text-cohab-subtle mt-[5px]">{s.caption}</span>
            </div>
          ))}
        </div>

        <p data-stagger-item="" className="relative z-10 font-mono font-medium text-[10px] uppercase tracking-[.08em] text-cohab-subtle mb-4">
          How it works
        </p>
        <div data-stagger-item="" className="relative z-10 flex flex-col gap-4 mb-[30px]">
          {LANDING_STEPS.map((s, i) => (
            <div key={s.title} className="grid grid-cols-[26px_1fr] gap-3.5 items-start">
              <span className="w-6 h-6 rounded-full border border-cohab-border bg-cohab-tint text-cohab-primary text-[11px] font-semibold flex items-center justify-center">
                {i + 1}
              </span>
              <div>
                <span className="block text-[14.5px] font-semibold leading-[1.3]">{s.title}</span>
                <span className="block text-[13.5px] leading-[1.45] text-cohab-muted mt-[3px] max-w-[460px]">
                  {s.body}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div data-stagger-item="" className="relative z-10 flex flex-wrap gap-2 mb-[26px]">
          {LANDING_CHIPS.map((c) => (
            <span
              key={c}
              className="border border-cohab-border rounded-full bg-cohab-card px-3 py-1.5 text-xs font-medium text-cohab-muted"
            >
              {c}
            </span>
          ))}
        </div>

        <div className="flex-1 min-h-4" />
        <p data-stagger-item="" className="relative z-10 text-xs leading-[1.5] text-cohab-subtle border-t border-cohab-border pt-4 max-w-[520px]">
          Matching opens for your locality once enough verified profiles have joined. Cohab never
          handles rent, deposits or payments.
        </p>
      </HeroStagger>

      <div className="flex-1 flex flex-col bg-cohab-card px-6 pt-3 pb-7 cohab-desktop:px-14 cohab-desktop:py-14 cohab-desktop:justify-center box-border">
        {children}
      </div>
    </div>
  )
}

export function AuthPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'signup'>('login')

  if (mode === 'login') {
    return (
      <AuthShell>
        <LoginForm onSwitchToSignup={() => setMode('signup')} onLoggedIn={() => navigate('/matches')} />
      </AuthShell>
    )
  }

  return (
    <SignUpWizard
      onSwitchToLogin={() => setMode('login')}
      onDone={(seekerType) =>
        navigate(seekerType === 'has_place' ? '/onboarding/listing' : '/onboarding/questionnaire')
      }
    />
  )
}
