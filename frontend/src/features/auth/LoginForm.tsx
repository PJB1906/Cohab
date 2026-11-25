import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, Eye, EyeOff, KeyRound, Lock, Mail, ShieldCheck, Check } from 'lucide-react'
import { authApi } from '@/api/auth'
import { ApiError } from '@/api/client'
import { useSetSession } from '@/hooks/useSession'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/Logo'
import { cn } from '@/lib/utils'

type Mode = 'login' | 'reset' | 'code'

const swap = {
  initial: { opacity: 0, y: 14, filter: 'blur(4px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  exit: { opacity: 0, y: -10, filter: 'blur(4px)' },
  transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const },
}

function Field({
  id,
  label,
  icon: Icon,
  aside,
  trailing,
  className,
  ...input
}: {
  id: string
  label: string
  icon: typeof Mail
  aside?: React.ReactNode
  trailing?: React.ReactNode
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={cn('mb-4', className)}>
      <div className="flex items-baseline justify-between mb-2">
        <label htmlFor={id} className="text-[13px] font-semibold text-cohab-ink">
          {label}
        </label>
        {aside}
      </div>
      <div className="group relative">
        <Icon
          aria-hidden
          className="absolute left-4 top-1/2 -translate-y-1/2 size-[18px] text-cohab-placeholder transition-colors group-focus-within:text-cohab-ink"
        />
        <input
          id={id}
          className="w-full h-[54px] rounded-[16px] border-[1.5px] border-cohab-border bg-cohab-card pl-11 pr-12 text-[15px] text-cohab-ink placeholder:text-cohab-placeholder outline-none transition-[border-color,box-shadow] duration-200 hover:border-cohab-ink/30 focus:border-cohab-ink focus:ring-4 focus:ring-cohab-ink/10 focus-visible:outline-none"
          {...input}
        />
        {trailing && <div className="absolute right-2 top-1/2 -translate-y-1/2">{trailing}</div>}
      </div>
    </div>
  )
}

function Heading({ kicker, title, children }: { kicker: string; title: string; children: React.ReactNode }) {
  return (
    <div className="mb-7">
      <span className="label text-[10px] text-cohab-subtle">{kicker}</span>
      <h2 className="poster text-[52px] cohab-desktop:text-[68px] mt-2">{title}</h2>
      <p className="text-[15px] leading-[1.5] text-cohab-muted mt-3 max-w-[40ch]">{children}</p>
    </div>
  )
}

function message(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Something went wrong. Try again.'
}

/** Sign in, and the forgot-password flow (D-14.27): email a code, then set a
 * new password with it. "Keep me logged in" is real: unticked, the session
 * ends when the browser closes. */
export function LoginForm({ onSwitchToSignup, onLoggedIn }: { onSwitchToSignup: () => void; onLoggedIn: () => void }) {
  const setSession = useSetSession()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(true)
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function go(next: Mode) {
    setError(null)
    setNote(null)
    setMode(next)
  }

  async function run(fn: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  const eye = (
    <button
      type="button"
      onClick={() => setShowPassword((v) => !v)}
      aria-label={showPassword ? 'Hide password' : 'Show password'}
      className="cohab-press w-9 h-9 grid place-items-center rounded-full text-cohab-subtle hover:text-cohab-ink hover:bg-cohab-tint cursor-pointer"
    >
      {showPassword ? <EyeOff className="size-[18px]" aria-hidden /> : <Eye className="size-[18px]" aria-hidden />}
    </button>
  )

  return (
    <div className="flex flex-1 flex-col w-full max-w-[440px] mx-auto cohab-desktop:mx-0 cohab-desktop:justify-center cohab-desktop:min-h-[calc(100vh-200px)]">
      <Logo className="mb-10 cohab-desktop:hidden" />

      <AnimatePresence mode="wait" initial={false}>
        {mode === 'login' && (
          <motion.form
            key="login"
            {...swap}
            onSubmit={(e) => {
              e.preventDefault()
              run(async () => {
                const user = await authApi.login({ email, password, remember })
                setSession(user)
                onLoggedIn()
              })
            }}
          >
            <Heading kicker="Welcome back" title="Log in">
              Use the institutional email you verified with.
            </Heading>
            <Field
              id="login-email"
              label="Institutional email"
              icon={Mail}
              type="email"
              autoComplete="email"
              required
              placeholder="name@msds.christuniversity.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Field
              id="login-password"
              label="Password"
              icon={Lock}
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              required
              placeholder="Your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              trailing={eye}
              aside={
                <button
                  type="button"
                  onClick={() => go('reset')}
                  className="text-[12.5px] font-semibold text-cohab-primary hover:underline underline-offset-4 cursor-pointer"
                >
                  Forgot password?
                </button>
              }
            />
            <button
              type="button"
              role="checkbox"
              aria-checked={remember}
              onClick={() => setRemember((v) => !v)}
              className="flex items-center gap-2.5 mb-6 text-[14px] text-cohab-muted cursor-pointer select-none"
            >
              <span
                className={cn(
                  'w-5 h-5 rounded-[7px] grid place-items-center border-[1.5px] transition-colors',
                  remember ? 'bg-cohab-fill border-cohab-fill text-cohab-on-fill' : 'bg-cohab-card border-cohab-border',
                )}
              >
                {remember && <Check className="size-3" strokeWidth={3.2} aria-hidden />}
              </span>
              Keep me logged in on this device
            </button>

            {error && (
              <p role="alert" className="text-[13.5px] text-cohab-accent bg-cohab-accent-tint rounded-[12px] px-3.5 py-2.5 mb-4">
                {error}
              </p>
            )}

            <Button type="submit" size="lg" arrow loading={busy} className="w-full justify-between pl-7">
              Log in
            </Button>

            <div className="flex items-center gap-3 my-6">
              <span className="h-px flex-1 bg-cohab-border" />
              <span className="text-[12px] text-cohab-subtle">New to Cohab?</span>
              <span className="h-px flex-1 bg-cohab-border" />
            </div>
            <Button type="button" variant="secondary" size="lg" onClick={onSwitchToSignup} className="w-full">
              Create an account
            </Button>
          </motion.form>
        )}

        {mode === 'reset' && (
          <motion.form
            key="reset"
            {...swap}
            onSubmit={(e) => {
              e.preventDefault()
              run(async () => {
                await authApi.requestPasswordReset(email)
                setMode('code')
                setNote(`If ${email} has an account, a code is on its way. It works for 10 minutes.`)
              })
            }}
          >
            <Heading kicker="Forgot password" title="Reset it">
              We'll email a one-time code to your institutional address. Use it to choose a new password.
            </Heading>
            <Field
              id="reset-email"
              label="Institutional email"
              icon={Mail}
              type="email"
              autoComplete="email"
              required
              placeholder="name@msds.christuniversity.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {error && (
              <p role="alert" className="text-[13.5px] text-cohab-accent bg-cohab-accent-tint rounded-[12px] px-3.5 py-2.5 mb-4">
                {error}
              </p>
            )}
            <Button type="submit" size="lg" arrow loading={busy} className="w-full justify-between pl-7 mt-2">
              Email me a code
            </Button>
            <BackLink onClick={() => go('login')} />
          </motion.form>
        )}

        {mode === 'code' && (
          <motion.form
            key="code"
            {...swap}
            onSubmit={(e) => {
              e.preventDefault()
              run(async () => {
                const user = await authApi.confirmPasswordReset({ email, code: code.trim(), new_password: newPassword, remember })
                setSession(user)
                onLoggedIn()
              })
            }}
          >
            <Heading kicker="Check your inbox" title="New password">
              Enter the code we sent and choose a new password (at least 8 characters).
            </Heading>
            {note && (
              <p className="text-[13.5px] text-cohab-good bg-cohab-good-tint rounded-[12px] px-3.5 py-2.5 mb-4">{note}</p>
            )}
            <Field
              id="reset-code"
              label="Code"
              icon={KeyRound}
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              maxLength={8}
              placeholder="6-digit code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, ''))}
              className="[&_input]:tracking-[0.3em] [&_input]:font-semibold"
            />
            <Field
              id="reset-password"
              label="New password"
              icon={Lock}
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={72}
              placeholder="At least 8 characters"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              trailing={eye}
            />
            {error && (
              <p role="alert" className="text-[13.5px] text-cohab-accent bg-cohab-accent-tint rounded-[12px] px-3.5 py-2.5 mb-4">
                {error}
              </p>
            )}
            <Button type="submit" size="lg" arrow loading={busy} className="w-full justify-between pl-7 mt-2">
              Set password and log in
            </Button>
            <div className="flex items-center justify-between mt-5">
              <BackLink onClick={() => go('login')} inline />
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await authApi.requestPasswordReset(email)
                    setNote('A new code is on its way.')
                  })
                }
                className="text-[13px] font-semibold text-cohab-primary hover:underline underline-offset-4 cursor-pointer disabled:opacity-50"
              >
                Send a new code
              </button>
            </div>
          </motion.form>
        )}
      </AnimatePresence>

      <div className="flex flex-wrap gap-x-5 gap-y-2 mt-8 text-[12.5px] text-cohab-subtle">
        <span className="inline-flex items-center gap-1.5">
          <ShieldCheck className="size-4 text-cohab-good" aria-hidden />
          Verified students only
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Lock className="size-4 text-cohab-good" aria-hidden />
          Numbers stay hidden until you both agree
        </span>
      </div>
      <p className="text-[12px] leading-[1.5] text-cohab-subtle mt-3">Cohab never handles rent, deposits or payments.</p>
    </div>
  )
}

function BackLink({ onClick, inline = false }: { onClick: () => void; inline?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 text-[13px] font-semibold text-cohab-muted hover:text-cohab-ink cursor-pointer',
        !inline && 'mt-5',
      )}
    >
      <ArrowLeft className="size-4" aria-hidden />
      Back to log in
    </button>
  )
}
