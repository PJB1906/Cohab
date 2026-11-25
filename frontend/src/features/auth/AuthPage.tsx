import { Roofline } from '@/components/Roofline'
import { AuthStage } from './AuthStage'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { LoginForm } from './LoginForm'
import { SignUpWizard } from './SignUpWizard'
import { StepTransition } from '@/components/motion/StepTransition'
import { ThemeToggle } from '@/components/ThemeToggle'

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
    <div className="min-h-screen flex flex-col cohab-desktop:grid cohab-desktop:grid-cols-[minmax(0,1.15fr)_minmax(480px,1fr)]">
      <AuthStage />

      <div
        className={`relative isolate flex-1 flex flex-col bg-cohab-bg px-6 pt-3 pb-7 cohab-desktop:px-14 cohab-desktop:justify-start box-border overflow-hidden ${
          compactTop ? 'cohab-desktop:pt-12' : 'cohab-desktop:pt-20'
        }`}
      >
        <ThemeToggle
          iconOnly
          className="self-end w-auto shrink-0 mb-3 cohab-desktop:absolute cohab-desktop:top-8 cohab-desktop:right-8 cohab-desktop:mb-0"
        />
        <Roofline seed={19} className="absolute inset-x-0 bottom-0 h-[110px] w-full -z-10" />
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
