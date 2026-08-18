import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoginForm } from './LoginForm'
import { SignUpWizard } from './SignUpWizard'
import { Card } from '@/components/ui/card'

export function AuthPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'signup'>('login')

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="flex items-baseline gap-2 mb-6 justify-center">
          <span className="text-xl font-bold tracking-tight text-cohab-primary">Cohab</span>
          <span className="font-mono text-[9px] uppercase tracking-wider text-cohab-subtle border border-cohab-border rounded px-1.5 py-0.5">
            Pilot
          </span>
        </div>
        <Card className="p-7 sm:p-10">
          {mode === 'login' ? (
            <LoginForm onSwitchToSignup={() => setMode('signup')} onLoggedIn={() => navigate('/matches')} />
          ) : (
            <SignUpWizard
              onSwitchToLogin={() => setMode('login')}
              onDone={(seekerType) =>
                navigate(seekerType === 'has_place' ? '/onboarding/listing' : '/onboarding/questionnaire')
              }
            />
          )}
        </Card>
      </div>
    </div>
  )
}
