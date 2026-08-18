import { useState } from 'react'
import { authApi } from '@/api/auth'
import { ApiError } from '@/api/client'
import { useSetSession } from '@/hooks/useSession'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PhotoUpload } from '@/components/PhotoUpload'
import type { Gender, SeekerType } from '@/api/types'

type Step = 'seeker' | 'form' | 'otp' | 'avatar'

/** Sign-up as a short wizard: seeker type first, then the account form
 * (which now also collects gender), then OTP, then an optional avatar.
 * One `POST /auth/register` call at the end of the form step — this
 * reconciles the mockups' "which are you" moment with D-4.1
 * (gender/seeker_type belong in the register payload, not a separate
 * post-verify step). docs/DECISIONS.md D-5.1. */
export function SignUpWizard({
  onSwitchToLogin,
  onDone,
}: {
  onSwitchToLogin: () => void
  onDone: (seekerType: SeekerType) => void
}) {
  const setSession = useSetSession()
  const [step, setStep] = useState<Step>('seeker')
  const [seekerType, setSeekerType] = useState<SeekerType | null>(null)

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [gender, setGender] = useState<Gender | ''>('')
  const [password, setPassword] = useState('')
  const [userId, setUserId] = useState<string | null>(null)

  const [otp, setOtp] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submitAccount(e: React.FormEvent) {
    e.preventDefault()
    if (!seekerType || !gender) return
    setBusy(true)
    setError(null)
    try {
      const res = await authApi.register({
        email,
        password,
        full_name: fullName,
        gender,
        seeker_type: seekerType,
      })
      setUserId(res.user_id)
      setStep('otp')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  async function submitOtp(e: React.FormEvent) {
    e.preventDefault()
    if (!userId) return
    setBusy(true)
    setError(null)
    try {
      const user = await authApi.verify({ user_id: userId, code: otp })
      setSession(user)
      setStep('avatar')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  if (step === 'seeker') {
    return (
      <div className="flex flex-col">
        <h2 className="text-xl font-semibold mb-1.5">Which of these is you?</h2>
        <p className="text-sm text-cohab-muted mb-6">
          This decides who you can be matched with. Two people who both already have a flat
          have nothing to offer each other, so Cohab won't pair them.
        </p>
        <div className="flex flex-col gap-3">
          <button
            type="button"
            onClick={() => {
              setSeekerType('needs_place')
              setStep('form')
            }}
            className="text-left rounded-2xl border border-cohab-border bg-white p-4 hover:border-cohab-primary cursor-pointer"
          >
            <span className="block text-[15px] font-semibold mb-1">I need a place</span>
            <span className="block text-[13px] text-cohab-muted">
              You're looking for somewhere to live and someone to live with.
            </span>
          </button>
          <button
            type="button"
            onClick={() => {
              setSeekerType('has_place')
              setStep('form')
            }}
            className="text-left rounded-2xl border border-cohab-border bg-white p-4 hover:border-cohab-primary cursor-pointer"
          >
            <span className="block text-[15px] font-semibold mb-1">I have a place and need someone</span>
            <span className="block text-[13px] text-cohab-muted">
              You have a room to fill — your listing's rent, locality and available-from date
              replace your stated preferences when matching.
            </span>
          </button>
        </div>
        <Button type="button" variant="ghost" onClick={onSwitchToLogin} className="mt-6">
          ← Back to log in
        </Button>
      </div>
    )
  }

  if (step === 'form') {
    return (
      <form onSubmit={submitAccount} className="flex flex-col">
        <Button type="button" variant="ghost" onClick={() => setStep('seeker')} className="mb-4 self-start px-0">
          ← Back
        </Button>
        <h2 className="text-xl font-semibold mb-1.5">Create your account</h2>
        <p className="text-sm text-cohab-muted mb-6">
          Use your institutional email — it's how we verify you belong to the campus.
        </p>

        <Label htmlFor="su-name">Full name</Label>
        <Input id="su-name" required value={fullName} onChange={(e) => setFullName(e.target.value)} className="mb-4" />

        <Label htmlFor="su-email">Institutional email</Label>
        <Input
          id="su-email"
          type="email"
          required
          placeholder="name@msds.christuniversity.in"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4"
        />

        <Label htmlFor="su-gender">Gender</Label>
        <select
          id="su-gender"
          required
          value={gender}
          onChange={(e) => setGender(e.target.value as Gender)}
          className="w-full box-border rounded-xl border border-cohab-border bg-white px-3.5 py-3 text-sm text-cohab-ink mb-4 focus:outline-none focus:ring-2 focus:ring-cohab-primary"
        >
          <option value="" disabled>
            Select…
          </option>
          <option value="female">Female</option>
          <option value="male">Male</option>
          <option value="non_binary">Non-binary</option>
        </select>

        <Label htmlFor="su-password">Password</Label>
        <Input
          id="su-password"
          type="password"
          required
          minLength={8}
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-2"
        />

        {error && <p className="text-sm text-cohab-accent mt-2">{error}</p>}

        <Button type="submit" disabled={busy} className="w-full mt-4">
          {busy ? 'Sending code…' : 'Send verification code'}
        </Button>
        <p className="text-xs text-cohab-subtle text-center mt-4">
          By continuing you agree to the matching and communication notices. You are 18 or over.
        </p>
      </form>
    )
  }

  if (step === 'otp') {
    return (
      <form onSubmit={submitOtp} className="flex flex-col">
        <h2 className="text-xl font-semibold mb-1.5">Enter the six-digit code</h2>
        <p className="text-sm text-cohab-muted mb-6">
          Sent to <strong className="text-cohab-ink font-semibold">{email}</strong>. It expires in 10 minutes.
        </p>
        <Label htmlFor="su-otp">Code</Label>
        <Input
          id="su-otp"
          required
          inputMode="numeric"
          placeholder="Type the code"
          value={otp}
          onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
          className="mb-2 tracking-[0.3em] text-center"
        />
        {error && <p className="text-sm text-cohab-accent mt-2">{error}</p>}
        <Button type="submit" disabled={busy} className="w-full mt-4">
          {busy ? 'Verifying…' : 'Verify and continue'}
        </Button>
      </form>
    )
  }

  // step === 'avatar'
  return (
    <div className="flex flex-col">
      <h2 className="text-xl font-semibold mb-1.5">Add a profile photo</h2>
      <p className="text-sm text-cohab-muted mb-6">Optional — you can add or change this later.</p>
      <PhotoUpload
        kind="avatar"
        placeholder="Tap to add a photo"
        onChange={() => {}}
        aspect="aspect-square"
        className="w-32 mx-auto mb-6"
      />
      <Button type="button" onClick={() => onDone(seekerType!)} className="w-full">
        Continue
      </Button>
    </div>
  )
}
