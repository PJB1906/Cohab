import { useState } from 'react'
import { authApi } from '@/api/auth'
import { ApiError } from '@/api/client'
import { useSetSession } from '@/hooks/useSession'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Logo } from '@/components/Logo'

export function LoginForm({
  onSwitchToSignup,
  onLoggedIn,
}: {
  onSwitchToSignup: () => void
  onLoggedIn: () => void
}) {
  const setSession = useSetSession()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [keepLoggedIn, setKeepLoggedIn] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const user = await authApi.login({ email, password })
      setSession(user)
      onLoggedIn()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-1 flex-col">
      <Logo className="mb-11 cohab-desktop:hidden" />

      <h2 className="poster text-[44px] cohab-desktop:text-[52px] mb-3">
        Log in
      </h2>
      <p className="text-[15px] cohab-desktop:text-[13px] leading-[1.5] cohab-desktop:leading-[1.45] text-cohab-muted mb-7 cohab-desktop:mb-7">
        Use the institutional email you verified with.
      </p>

      <Label htmlFor="login-email">Institutional email</Label>
      <Input
        id="login-email"
        type="email"
        required
        placeholder="name@msds.christuniversity.in"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="mb-[18px]"
      />

      <div className="flex items-baseline justify-between mb-[7px]">
        <Label htmlFor="login-password" className="mb-0">
          Password
        </Label>
        <button
          type="button"
          className="text-xs font-medium text-cohab-primary cursor-pointer bg-transparent border-none p-0"
        >
          Forgot password?
        </button>
      </div>
      <Input
        id="login-password"
        type="password"
        required
        placeholder="••••••••"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="mb-4"
      />

      <button
        type="button"
        onClick={() => setKeepLoggedIn((v) => !v)}
        className="flex items-center gap-2.5 mb-6 text-sm text-cohab-muted-mobile cursor-pointer select-none bg-transparent border-none p-0 text-left"
      >
        <span
          className={
            'w-5 h-5 rounded-[7px] flex-none flex items-center justify-center border-[1.5px] transition-colors ' +
            (keepLoggedIn ? 'bg-cohab-fill border-cohab-primary' : 'bg-cohab-card border-cohab-border')
          }
        >
          {keepLoggedIn && (
            <svg width="11" height="8" viewBox="0 0 12 9" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M1 4.6L4.3 8 11 1.2" />
            </svg>
          )}
        </span>
        Keep me logged in on this device
      </button>

      {error && <p className="text-sm text-cohab-accent mb-2">{error}</p>}

      <Button type="submit" disabled={busy} className="w-full">
        {busy ? 'Logging in…' : 'Log in'}
      </Button>

      <div className="flex items-center gap-3 my-6">
        <span className="h-px flex-1 bg-cohab-border" />
        <span className="text-xs text-cohab-placeholder">New to Cohab?</span>
        <span className="h-px flex-1 bg-cohab-border" />
      </div>
      <Button type="button" variant="secondary" onClick={onSwitchToSignup} className="w-full">
        Sign up
      </Button>
      <p className="text-xs leading-[1.5] text-cohab-subtle text-center mt-4">
        Accounts are limited to verified students during the pilot.
      </p>

      <div className="flex-1 min-h-4 cohab-desktop:hidden" />
      <p className="text-xs leading-[1.5] text-cohab-subtle text-center border-t border-cohab-border-soft pt-4 cohab-desktop:hidden">
        Cohab never handles rent, deposits or payments.
      </p>
    </form>
  )
}
