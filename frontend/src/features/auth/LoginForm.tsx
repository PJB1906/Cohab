import { useState } from 'react'
import { authApi } from '@/api/auth'
import { ApiError } from '@/api/client'
import { useSetSession } from '@/hooks/useSession'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

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
    <form onSubmit={submit} className="flex flex-col">
      <h2 className="text-xl font-semibold mb-1.5">Log in</h2>
      <p className="text-sm text-cohab-muted mb-6">Use the institutional email you verified with.</p>

      <Label htmlFor="login-email">Institutional email</Label>
      <Input
        id="login-email"
        type="email"
        required
        placeholder="name@msds.christuniversity.in"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="mb-4"
      />

      <Label htmlFor="login-password">Password</Label>
      <Input
        id="login-password"
        type="password"
        required
        placeholder="••••••••"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="mb-2"
      />

      {error && <p className="text-sm text-cohab-accent mt-2">{error}</p>}

      <Button type="submit" disabled={busy} className="w-full mt-4">
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
    </form>
  )
}
