import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ApiError } from '@/api/client'
import { studyApi, studyToken, type PairStatus } from '@/api/v2'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { OptionPill } from '@/components/OptionPill'
import { CARD_ROWS, ROOMMATE_RATING_FIELDS } from '@/data/studyCards'
import { OwnAnswers, ResumeCode, StudyShell } from './StudyShell'

const KEY = 'pair'
const SCALE = [1, 2, 3, 4, 5]

function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const d = err.detail as { problems?: string[] } | string
    if (typeof d === 'object' && d?.problems) return d.problems.join('; ')
    return err.message
  }
  return 'Something went wrong. Try again.'
}

/** Invite tokens travel in the URL fragment (#invite=...), which browsers
 * never send to the server, so they cannot land in access logs. */
function inviteFromHash(): string | null {
  const m = window.location.hash.match(/invite=([\w-]+)/)
  return m ? m[1] : null
}

/** Roommate-pair validation (Cohab v2 plan W3). Each person answers alone;
 * neither ever sees the other's answers. */
export function PairFlow() {
  const [token, setToken] = useState<string | null>(() => studyToken.get(KEY))
  const [invite, setInvite] = useState<string | null>(null)
  const { data: instrument } = useQuery({ queryKey: ['study', 'instrument'], queryFn: studyApi.instrument })
  const join = useMutation({
    mutationFn: (code: string) => studyApi.joinPair(code),
    onSuccess: (r) => {
      studyToken.set(KEY, r.token)
      setToken(r.token)
      history.replaceState(null, '', window.location.pathname)
    },
  })
  const create = useMutation({
    mutationFn: () => studyApi.createPair(),
    onSuccess: (r) => {
      studyToken.set(KEY, r.token)
      studyToken.set(`${KEY}-invite`, r.invite_token)
      setToken(r.token)
    },
  })

  useEffect(() => {
    const code = inviteFromHash()
    if (code && !token && !join.isPending && !join.isSuccess && !join.isError) join.mutate(code)
  }, [token, join])

  useEffect(() => setInvite(studyToken.get(`${KEY}-invite`)), [token])

  if (!instrument) {
    return (
      <StudyShell>
        <p className="text-cohab-muted">Loading…</p>
      </StudyShell>
    )
  }
  if (!instrument.open) {
    return (
      <StudyShell>
        <h1 className="poster text-[44px] mb-3">The study is closed</h1>
      </StudyShell>
    )
  }
  if (!token) {
    return (
      <StudyShell>
        <h1 className="poster text-[48px] cohab-desktop:text-[60px] mb-3 max-w-[16ch]">Do you live with someone?</h1>
        <p className="text-[14.5px] leading-[1.6] text-cohab-muted max-w-[640px] mb-6">
          This study checks whether Cohab's compatibility score agrees with how real cohabitation goes. You and your
          roommate each answer separately, about ten minutes each. Neither of you sees the other's answers, and no
          names or contact details are collected.
        </p>
        {join.isError && <p className="text-cohab-accent text-sm mb-4">That invite link didn't work: {errorText(join.error)}</p>}
        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          Start, and get a link for my roommate
        </Button>
        {create.isError && <p className="text-cohab-accent text-sm mt-3">{errorText(create.error)}</p>}
      </StudyShell>
    )
  }
  return <PairForm token={token} invite={invite} consentVersion={instrument.pair_consent_version} raterFields={instrument.rater_fields} outcomeItems={instrument.outcome_items} />
}

function PairForm({
  token,
  invite,
  consentVersion,
  raterFields,
  outcomeItems,
}: {
  token: string
  invite: string | null
  consentVersion: string
  raterFields: string[]
  outcomeItems: Record<string, string>
}) {
  const status = useQuery({ queryKey: ['study', 'pair', token], queryFn: () => studyApi.pairStatus(token), retry: false })
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [ratings, setRatings] = useState<Record<string, string>>({})
  const [outcomes, setOutcomes] = useState<Record<string, number>>({})
  const [months, setMonths] = useState('')
  const [together, setTogether] = useState<boolean | null>(null)
  const [agreed, setAgreed] = useState(false)
  const [done, setDone] = useState<PairStatus | null>(null)

  const submit = useMutation({
    mutationFn: () =>
      studyApi.submitPair(token, {
        consent_version: consentVersion,
        answers,
        important_attributes: [],
        roommate_ratings: ratings,
        outcomes,
        months_together: Number(months),
        still_together: together,
      }),
    onSuccess: setDone,
  })

  const s = done ?? status.data
  const inviteLink = invite ? `${window.location.origin}/study/pair#invite=${invite}` : null

  if (s?.submitted) {
    return (
      <StudyShell step="Done">
        <h1 className="poster text-[44px] mb-3">Thank you</h1>
        <p className="text-[14.5px] text-cohab-muted mb-6 max-w-[620px]">
          {s.roommate_submitted
            ? 'Both of you have answered. Your pair is now part of the validation study.'
            : 'Your answers are saved. The pair counts once your roommate answers too.'}
        </p>
        {!s.roommate_joined && inviteLink && <InviteBox link={inviteLink} />}
      </StudyShell>
    )
  }

  const missing =
    raterFields.filter((f) => !answers[f]).length +
    ROOMMATE_RATING_FIELDS.filter((f) => !ratings[f]).length +
    Object.keys(outcomeItems).filter((k) => !outcomes[k]).length +
    (Number(months) > 0 ? 0 : 1) +
    (together === null ? 1 : 0) +
    (agreed ? 0 : 1)

  return (
    <StudyShell step={s ? `You are person ${s.role.toUpperCase()}` : undefined}>
      {s?.role === 'a' && !s.roommate_joined && inviteLink && <InviteBox link={inviteLink} />}

      <h1 className="text-2xl font-semibold mb-1 mt-2">1. About you</h1>
      <p className="text-[14px] text-cohab-muted mb-4">Answer for yourself, as you really are at home.</p>
      <OwnAnswers answers={answers} onChange={(k, v) => setAnswers((a) => ({ ...a, [k]: v }))} fields={raterFields} />

      <h2 className="text-2xl font-semibold mb-1 mt-8">2. How would your roommate describe you?</h2>
      <p className="text-[14px] text-cohab-muted mb-4">
        Not how you'd describe yourself: how they would. This measures how much self-descriptions flatter us.
      </p>
      <div className="flex flex-col gap-4">
        {ROOMMATE_RATING_FIELDS.map((f) => {
          const row = CARD_ROWS.find((r) => r.field === f)!
          return (
            <div key={f} className="bg-cohab-card border border-cohab-border rounded-2xl p-4">
              <p className="text-[14px] font-semibold mb-2.5">{row.heading}</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(row.text).map(([value, label]) => (
                  <OptionPill key={value} selected={ratings[f] === value} onClick={() => setRatings((r) => ({ ...r, [f]: value }))}>
                    {label}
                  </OptionPill>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      <h2 className="text-2xl font-semibold mb-1 mt-8">3. How is living together going?</h2>
      <p className="text-[14px] text-cohab-muted mb-4">1 = not at all, 5 = completely.</p>
      <div className="flex flex-col gap-3">
        {Object.entries(outcomeItems).map(([key, q]) => (
          <div key={key} className="bg-cohab-card border border-cohab-border rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center gap-3">
            <p className="text-[14px] flex-1">{q}</p>
            <div className="flex gap-2">
              {SCALE.map((n) => (
                <OptionPill
                  key={n}
                  selected={outcomes[key] === n}
                  onClick={() => setOutcomes((o) => ({ ...o, [key]: n }))}
                  className="w-10 min-h-10 px-0 justify-center text-center"
                >
                  {n}
                </OptionPill>
              ))}
            </div>
          </div>
        ))}
        <div className="bg-cohab-card border border-cohab-border rounded-2xl p-4 grid gap-3 sm:grid-cols-2">
          <label className="text-[14px]">
            Months you have lived together
            <Input className="mt-2" inputMode="decimal" value={months} onChange={(e) => setMonths(e.target.value.replace(/[^\d.]/g, ''))} placeholder="e.g. 8" />
          </label>
          <div>
            <p className="text-[14px] mb-2">Still living together?</p>
            <div className="flex gap-2">
              <OptionPill selected={together === true} onClick={() => setTogether(true)} className="w-auto min-h-10 px-4">
                Yes
              </OptionPill>
              <OptionPill selected={together === false} onClick={() => setTogether(false)} className="w-auto min-h-10 px-4">
                No
              </OptionPill>
            </div>
          </div>
        </div>
      </div>

      <label className="flex items-start gap-3 mt-8 text-[13.5px] text-cohab-muted max-w-[680px]">
        <input type="checkbox" className="mt-1" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
        I agree to these answers being used, anonymised and in aggregate, in a university project report. No name or
        contact detail is collected, and my roommate never sees my answers. (Consent {consentVersion})
      </label>

      <div className="sticky bottom-0 bg-cohab-bg/95 backdrop-blur py-3 mt-6 flex items-center gap-3">
        <Button onClick={() => submit.mutate()} disabled={missing > 0 || submit.isPending}>
          {missing > 0 ? `${missing} left` : 'Submit my answers'}
        </Button>
        {submit.isError && <p className="text-cohab-accent text-sm">{errorText(submit.error)}</p>}
      </div>
      <div className="mt-6">
        <ResumeCode token={token} />
      </div>
    </StudyShell>
  )
}

function InviteBox({ link }: { link: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="bg-cohab-tint border border-cohab-primary rounded-2xl p-4 mb-6">
      <p className="text-[14px] font-medium mb-2">Send this link to your roommate (single use):</p>
      <div className="flex gap-2 items-center">
        <code className="flex-1 text-[12px] bg-cohab-card rounded-lg px-2.5 py-2 break-all select-all">{link}</code>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            navigator.clipboard?.writeText(link).then(() => setCopied(true), () => setCopied(false))
          }}
        >
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
    </div>
  )
}
