import { Logo } from '@/components/Logo'
import { Roofline } from '@/components/Roofline'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { LoginForm } from './LoginForm'
import { SignUpWizard } from './SignUpWizard'
import { HeroStagger } from '@/components/motion/HeroStagger'
import { StepTransition } from '@/components/motion/StepTransition'
import { ThemeToggle } from '@/components/ThemeToggle'

const POSTER_STEPS: { n: string; title: string }[] = [
  { n: '01', title: 'Verify your student email' },
  { n: '02', title: 'Twelve questions, four minutes' },
  { n: '03', title: 'A ranked list, with reasons' },
  { n: '04', title: 'Numbers stay hidden until you both say yes' },
]

export function AuthShell({
  children,
  /** Trims the desktop top padding for the one step tall enough to need it.
   * The signup account form overflows a laptop viewport, so pixels above its
   * heading are pixels the user has to scroll past; login, OTP and the avatar
   * step are short, and sit better with the roomier default. */
  compactTop = false,
}: {
  children: React.ReactNode
  compactTop?: boolean
}) {
  return (
    <div className="min-h-screen flex flex-col cohab-desktop:grid cohab-desktop:grid-cols-[minmax(0,1fr)_minmax(460px,40%)]">
      {/* Poster panel (D-14.23): black, one real photograph, condensed caps.
          Desktop only; on a phone the form is the whole screen. */}
      <HeroStagger className="hidden cohab-desktop:flex cohab-desktop:flex-col relative isolate grain overflow-hidden bg-[#0d0f14] text-white px-12 pt-11 pb-10">
        <Roofline tone="panel" seed={11} className="absolute inset-x-0 bottom-0 h-[150px] w-full -z-10" />
        <div data-stagger-item="" className="mb-10">
          <Logo onDark pilot={false} size="lg" />
        </div>
        <h1 data-stagger-item="" className="poster text-white text-[clamp(64px,7vw,112px)] max-w-[11ch]">
          Find the one you can live with.
        </h1>
        <div data-stagger-item="" className="relative mt-10 flex-1 min-h-[260px]">
          <img
            src="/photos/cooking-together.webp"
            alt="Two flatmates cooking together in a shared kitchen"
            className="absolute inset-0 w-full h-full object-cover rounded-[22px]"
          />
          <div className="absolute left-5 bottom-5 flex flex-col gap-2 items-start">
            <span className="bg-white text-cohab-on-sun rounded-[18px] rounded-bl-[4px] px-4 py-2.5 text-[14px] font-semibold shadow-lg">
              you cook on weekdays?
            </span>
            <span className="bg-cohab-sun text-cohab-on-sun rounded-[18px] rounded-bl-[4px] px-4 py-2.5 text-[14px] font-semibold shadow-lg">
              every night. you do the dishes?
            </span>
          </div>
          <div className="absolute right-5 top-5 bg-cohab-dark-bg rounded-[18px] px-4 pt-3 pb-2.5 text-right">
            <span className="block label text-white/60 text-[10px]">Compatibility</span>
            <span className="poster-num block text-[56px] text-cohab-sun">92</span>
          </div>
        </div>
        <ol data-stagger-item="" className="grid grid-cols-2 gap-x-8 gap-y-3 mt-8">
          {POSTER_STEPS.map((s) => (
            <li key={s.n} className="flex gap-3 items-baseline">
              <span className="poster-num text-[22px] text-cohab-sun">{s.n}</span>
              <span className="text-[14px] font-semibold leading-[1.3] text-white/90">{s.title}</span>
            </li>
          ))}
        </ol>
        <p data-stagger-item="" className="text-[12px] leading-[1.5] text-white/50 mt-7 max-w-[560px]">
          Cohab never handles rent, deposits or payments. Photo: Odiseo Castrejon, Unsplash.
        </p>
      </HeroStagger>

      <div
        className={`relative flex-1 flex flex-col bg-cohab-bg cohab-desktop:bg-cohab-card px-6 pt-3 pb-7 cohab-desktop:px-14 cohab-desktop:justify-start box-border ${
          compactTop ? 'cohab-desktop:pt-12' : 'cohab-desktop:pt-20'
        }`}
      >
        <ThemeToggle
          iconOnly
          className="self-end w-auto shrink-0 mb-3 cohab-desktop:absolute cohab-desktop:top-8 cohab-desktop:right-8 cohab-desktop:mb-0"
        />
        {children}
      </div>
    </div>
  )
}

export function AuthPage() {
  const navigate = useNavigate()
  // /login?mode=signup opens straight on the signup form (landing CTAs).
  const [params] = useSearchParams()
  const [mode, setMode] = useState<'login' | 'signup'>(params.get('mode') === 'signup' ? 'signup' : 'login')

  if (mode === 'login') {
    return (
      <AuthShell>
        <StepTransition step="login">
          <LoginForm onSwitchToSignup={() => setMode('signup')} onLoggedIn={() => navigate('/matches')} />
        </StepTransition>
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
