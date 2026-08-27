import { useState } from 'react'
import { authApi } from '@/api/auth'
import { ApiError } from '@/api/client'
import { useSetSession } from '@/hooks/useSession'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { PhotoUpload } from '@/components/PhotoUpload'
import { Logo } from '@/components/Logo'
import { Eyebrow } from '@/components/Eyebrow'
import { OptionRadio } from '@/components/OptionRadio'
import { MobileStepHeader } from '@/components/MobileStepHeader'
import { StepTransition } from '@/components/motion/StepTransition'
import { AmbientField } from '@/components/CompatibilityField'
import { ThemeToggle } from '@/components/ThemeToggle'
import { AuthShell } from './AuthPage'
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
  const [phoneNumber, setPhoneNumber] = useState('')
  const [password, setPassword] = useState('')
  const [userId, setUserId] = useState<string | null>(null)

  const [otp, setOtp] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
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
        phone_number: phoneNumber || null,
      })
      setUserId(res.user_id)
      setStep('otp')
    } catch (err) {
      // A 409 here doesn't have to be a dead end: the account may just be
      // unverified (e.g. the user closed the tab before entering the code
      // and came back). Try to recover into the OTP step rather than
      // stopping at "already registered" — docs/DECISIONS.md D-10.1.
      if (err instanceof ApiError && err.status === 409) {
        try {
          const res = await authApi.resendOtp({ email })
          setUserId(res.user_id)
          setNotice("You've already started signing up with this email — we've sent a fresh code.")
          setStep('otp')
          return
        } catch (resendErr) {
          // Only a second 409 actually means "already registered and
          // verified" — anything else (a 429 cooldown, a transient
          // network/500) is a distinct failure and shouldn't be reported
          // as if the account were the problem (found in code review).
          setError(
            resendErr instanceof ApiError && resendErr.status === 409
              ? 'This email is already registered and verified — log in instead.'
              : resendErr instanceof ApiError
                ? resendErr.message
                : 'Something went wrong',
          )
          return
        }
      }
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

  async function resendOtp() {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const res = await authApi.resendOtp({ email })
      setUserId(res.user_id)
      setNotice('A new code is on its way.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not resend the code')
    } finally {
      setBusy(false)
    }
  }

  if (step === 'seeker') {
    return (
      <div className="min-h-screen flex flex-col relative">
        <AmbientField />
        <ThemeToggle
          iconOnly
          className="hidden cohab-desktop:grid absolute cohab-desktop:top-8 cohab-desktop:right-8 z-10"
        />
        <MobileStepHeader step={1} totalSteps={4} minutesLeft={5} onBack={onSwitchToLogin} progressPercent={25} />
        <div className="cohab-desktop:hidden flex justify-end px-4 pt-2">
          <ThemeToggle iconOnly />
        </div>

        <StepTransition step="seeker">
        <div className="flex-1 flex flex-col px-6 pt-6 pb-7 cohab-desktop:flex-none cohab-desktop:px-6 cohab-desktop:max-w-[1200px] cohab-desktop:mx-auto cohab-desktop:pt-[72px] cohab-desktop:pb-[72px] cohab-desktop:w-full">
          <Button
            type="button"
            variant="ghost"
            onClick={onSwitchToLogin}
            className="hidden cohab-desktop:inline-flex mb-[18px] self-start px-0"
          >
            ← Back to login
          </Button>

          <Eyebrow className="hidden cohab-desktop:block mb-3.5">Step 1 of 4 · Setup</Eyebrow>

          <h1 className="text-2xl cohab-desktop:text-[26px] font-semibold tracking-[-0.02em] cohab-desktop:leading-[1.18] leading-[1.2] mb-2">
            <span className="cohab-desktop:hidden">What are you looking for?</span>
            <span className="hidden cohab-desktop:inline">Which of these is you?</span>
          </h1>
          <p className="text-[15px] leading-[1.5] text-cohab-muted mb-6 cohab-desktop:mb-[34px] cohab-desktop:max-w-[620px]">
            <span className="cohab-desktop:hidden">
              This decides who you can match with. Two people who both already have a place aren't
              shown to each other.
            </span>
            <span className="hidden cohab-desktop:inline">
              This decides who you can be matched with. Two people who both already have a flat
              have nothing to offer each other, so Cohab won't pair them.
            </span>
          </p>

          <div className="flex flex-col gap-3.5 cohab-desktop:grid cohab-desktop:grid-cols-2 cohab-desktop:gap-5">
            <OptionRadio
              selected={seekerType === 'needs_place'}
              onClick={() => setSeekerType('needs_place')}
              className="!rounded-2xl px-[18px] py-[17px] cohab-desktop:px-[26px] cohab-desktop:py-6 cohab-desktop:items-start"
              sub={
                <>
                  <span className="cohab-desktop:hidden">
                    You're looking for somewhere to live and someone to live with. You'll be
                    matched with others searching, and with people offering a room.
                  </span>
                  <span className="hidden cohab-desktop:inline">
                    You are looking for both somewhere to live and someone to live with. You will
                    be matched with other seekers and with people who have a room.
                  </span>
                  <span className="hidden cohab-desktop:block mt-2 text-[13px] text-cohab-subtle">
                    Next: 12 questions, then your matches.
                  </span>
                </>
              }
            >
              <span className="hidden cohab-desktop:block font-mono font-medium text-[10px] uppercase tracking-[.08em] text-cohab-subtle mb-1">
                needs_place
              </span>
              <span className="text-[17px] cohab-desktop:text-lg font-semibold">I need a place</span>
            </OptionRadio>

            <OptionRadio
              selected={seekerType === 'has_place'}
              onClick={() => setSeekerType('has_place')}
              className="!rounded-2xl px-[18px] py-[17px] cohab-desktop:px-[26px] cohab-desktop:py-6 cohab-desktop:items-start"
              sub={
                <>
                  <span className="cohab-desktop:hidden">
                    You have a room to fill. You'll add the flat details next, and your rent and
                    move-in date come from that listing.
                  </span>
                  <span className="hidden cohab-desktop:inline">
                    You have a room to fill — your listing's rent, locality and available-from
                    date replace your stated preferences when matching.
                  </span>
                  <span className="hidden cohab-desktop:block mt-2 text-[13px] text-cohab-subtle">
                    Next: your listing, then 12 questions.
                  </span>
                </>
              }
            >
              <span className="hidden cohab-desktop:block font-mono font-medium text-[10px] uppercase tracking-[.08em] text-cohab-subtle mb-1">
                has_place
              </span>
              <span className="text-[17px] cohab-desktop:text-lg font-semibold">
                I have a place and need someone
              </span>
            </OptionRadio>
          </div>

          <p className="mt-[22px] px-[15px] py-3.5 bg-cohab-row-tint rounded-2xl text-[13px] leading-[1.5] text-cohab-muted cohab-desktop:hidden">
            You can change this later from your profile, but it re-runs your matches.
          </p>

          <div className="flex-1 cohab-desktop:hidden" />

          <Button
            disabled={!seekerType}
            onClick={() => seekerType && setStep('form')}
            className="w-full mt-6 cohab-desktop:hidden"
          >
            Continue
          </Button>

          <div className="hidden cohab-desktop:flex cohab-desktop:items-center cohab-desktop:gap-3.5 cohab-desktop:mt-8">
            <Button disabled={!seekerType} onClick={() => seekerType && setStep('form')}>
              Continue
            </Button>
            {!seekerType && <span className="text-[13px] text-cohab-subtle">Pick one to continue.</span>}
          </div>
        </div>
        </StepTransition>
      </div>
    )
  }

  if (step === 'form') {
    return (
      <AuthShell compactTop>
        <StepTransition step="form">
        <form onSubmit={submitAccount} className="flex flex-1 flex-col">
          <Logo className="mb-[22px] cohab-desktop:hidden" />
          <Button
            type="button"
            variant="ghost"
            onClick={() => setStep('seeker')}
            className="hidden cohab-desktop:inline-flex mb-[18px] self-start px-0"
          >
            ← Back
          </Button>

          <h2 className="text-2xl cohab-desktop:text-[19px] font-semibold tracking-[-0.02em] cohab-desktop:tracking-normal leading-[1.2] cohab-desktop:leading-[1.1] mb-2 cohab-desktop:mb-1.5">
            Create your account
          </h2>
          <p className="text-[15px] cohab-desktop:text-[13px] leading-[1.5] cohab-desktop:leading-[1.45] text-cohab-muted mb-5 cohab-desktop:mb-7">
            <span className="cohab-desktop:hidden">
              Cohab is open to verified students. Nothing is visible to anyone until you finish
              setting up.
            </span>
            <span className="hidden cohab-desktop:inline">
              Use your institutional email — it's how we verify you belong to the campus.
            </span>
          </p>

          <Label htmlFor="su-name">Full name</Label>
          <Input
            id="su-name"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="mb-4"
          />

          <Label htmlFor="su-email">Institutional email</Label>
          <Input
            id="su-email"
            type="email"
            required
            placeholder="name@msds.christuniversity.in"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mb-4 cohab-desktop:mb-1.5"
          />
          <p className="hidden cohab-desktop:block text-xs leading-[1.4] text-cohab-subtle mb-[18px]">
            Personal domains are not accepted during the pilot.
          </p>

          <Label htmlFor="su-phone" className="cohab-desktop:hidden">
            Mobile number
          </Label>
          <Label htmlFor="su-phone" className="hidden cohab-desktop:block">
            Phone number
          </Label>
          <Input
            id="su-phone"
            type="tel"
            placeholder="+91 98XXX XXXXX"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            className="mb-4"
          />

          <Label htmlFor="su-gender">Gender</Label>
          <Select
            id="su-gender"
            required
            value={gender}
            onChange={(e) => setGender(e.target.value as Gender)}
            className="mb-4"
          >
            <option value="" disabled>
              Select…
            </option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="non_binary">Non-binary</option>
          </Select>

          <Label htmlFor="su-password">Password</Label>
          <Input
            id="su-password"
            type="password"
            required
            minLength={8}
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mb-4"
          />

          <div className="mt-20 mb-6 mx-auto max-w-[280px] text-center">
            <p className="text-[8px] font-semibold text-cohab-primary mb-1">Your number stays private.</p>
            <p className="text-[8px] leading-[1.4] text-cohab-muted">Released only if both agree.</p>
          </div>

          {error && <p className="text-sm text-cohab-accent mb-2">{error}</p>}

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? 'Sending code…' : 'Send verification code'}
          </Button>
          <p className="text-xs leading-[1.5] text-cohab-subtle text-center mt-4">
            <span className="cohab-desktop:hidden">By continuing you agree to the Terms and Privacy Notice.</span>
            <span className="hidden cohab-desktop:inline">
              By continuing you agree to the matching and communication notices. You are 18 or
              over.
            </span>
          </p>

          <div className="flex-1 min-h-4 cohab-desktop:hidden" />
          <p className="text-sm text-cohab-muted-mobile text-center pt-3 cohab-desktop:hidden">
            Already have an account?{' '}
            <button
              type="button"
              onClick={onSwitchToLogin}
              className="text-cohab-primary font-semibold bg-transparent border-none p-0 cursor-pointer"
            >
              Log in
            </button>
          </p>
          <p className="hidden cohab-desktop:block text-[13px] text-cohab-subtle text-center pt-4">
            Already have an account?{' '}
            <button
              type="button"
              onClick={onSwitchToLogin}
              className="text-cohab-primary font-semibold bg-transparent border-none p-0 cursor-pointer"
            >
              Log in
            </button>
          </p>
        </form>
        </StepTransition>
      </AuthShell>
    )
  }

  if (step === 'otp') {
    return (
      <AuthShell>
        <StepTransition step="otp">
        <button
          type="button"
          onClick={() => setStep('form')}
          className="cohab-desktop:hidden w-11 h-11 -ml-2 mb-1 flex items-center justify-center text-cohab-ink text-[22px] cursor-pointer bg-transparent border-none"
        >
          ←
        </button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => setStep('form')}
          className="hidden cohab-desktop:inline-flex mb-[18px] self-start px-0"
        >
          ← Back
        </Button>

        <form onSubmit={submitOtp} className="flex flex-1 flex-col">
          <h2 className="text-2xl cohab-desktop:text-[19px] font-semibold tracking-[-0.02em] cohab-desktop:tracking-normal leading-[1.2] cohab-desktop:leading-[1.1] mb-2 cohab-desktop:mb-1.5">
            <span className="cohab-desktop:hidden">Enter the code</span>
            <span className="hidden cohab-desktop:inline">Enter the six-digit code</span>
          </h2>
          <p className="text-[15px] cohab-desktop:text-[13px] leading-[1.5] cohab-desktop:leading-[1.45] text-cohab-muted mb-[26px] cohab-desktop:mb-[22px]">
            <span className="cohab-desktop:hidden">We sent a six-digit code to </span>
            <span className="hidden cohab-desktop:inline">Sent to </span>
            <strong className="text-cohab-ink font-semibold">{email}</strong>. It expires in 10
            minutes.
          </p>

          <div className="grid grid-cols-6 gap-[9px] mb-[22px]">
            {Array.from({ length: 6 }).map((_, i) => {
              const ch = otp[i]
              const isCaret = i === otp.length && otp.length < 6
              return (
                <div
                  key={i}
                  className={
                    'h-[58px] rounded-[14px] flex items-center justify-center text-[22px] font-semibold text-cohab-ink ' +
                    (ch
                      ? 'border border-cohab-primary bg-cohab-card'
                      : isCaret
                        ? 'border-[1.5px] border-cohab-primary bg-cohab-card'
                        : 'border border-cohab-border')
                  }
                >
                  {ch ?? (isCaret && <span className="w-[1.5px] h-6 bg-cohab-primary" />)}
                </div>
              )
            })}
          </div>

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

          <p className="text-sm text-cohab-muted-mobile mt-2 mb-[26px] cohab-desktop:mb-2">
            Didn't get it?{' '}
            <button
              type="button"
              onClick={resendOtp}
              disabled={busy}
              className="text-cohab-primary font-semibold bg-transparent border-none p-0 cursor-pointer disabled:opacity-50"
            >
              Resend code
            </button>
          </p>

          {notice && <p className="text-sm text-cohab-primary mb-2">{notice}</p>}
          {error && <p className="text-sm text-cohab-accent mb-2">{error}</p>}

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? 'Verifying…' : 'Verify and continue'}
          </Button>

          <div className="hidden cohab-desktop:block mt-[26px] pt-[18px] border-t border-cohab-border-soft">
            <p className="text-[13px] font-semibold text-cohab-ink mb-[5px]">Why we verify</p>
            <p className="text-[13px] leading-[1.5] text-cohab-muted">
              Only verified students appear in anyone's matches. Your phone number is not part of
              verification and is never shown to other members until you both share it.
            </p>
          </div>

          <div className="flex-1 min-h-4" />
          <p className="text-[13px] leading-[1.5] text-cohab-subtle text-center">
            Wrong address?{' '}
            <button
              type="button"
              onClick={() => setStep('form')}
              className="text-cohab-primary font-semibold bg-transparent border-none p-0 cursor-pointer"
            >
              Change email
            </button>
          </p>
        </form>
        </StepTransition>
      </AuthShell>
    )
  }

  // step === 'avatar'
  return (
    <AuthShell>
      <StepTransition step="avatar">
      <div className="flex flex-1 flex-col">
        <h2 className="text-2xl cohab-desktop:text-[19px] font-semibold tracking-[-0.02em] cohab-desktop:tracking-normal leading-[1.2] cohab-desktop:leading-[1.1] mb-2 cohab-desktop:mb-1.5">
          Add a profile photo
        </h2>
        <p className="text-[15px] cohab-desktop:text-[13px] leading-[1.5] cohab-desktop:leading-[1.45] text-cohab-muted mb-7">
          Optional — you can add or change this later.
        </p>
        <PhotoUpload
          kind="avatar"
          placeholder="Tap to add a photo"
          onChange={() => {}}
          aspect="aspect-square"
          className="w-32 mx-auto mb-8"
        />
        <div className="flex-1 cohab-desktop:hidden" />
        <Button type="button" onClick={() => onDone(seekerType!)} className="w-full">
          Continue
        </Button>
      </div>
      </StepTransition>
    </AuthShell>
  )
}
