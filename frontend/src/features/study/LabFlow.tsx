import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '@/api/client'
import { studyApi, studyToken, type StudyTrial } from '@/api/v2'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { OptionPill } from '@/components/OptionPill'
import { WEIGHT_TILES } from '@/data/questionnaire'
import { cn } from '@/lib/utils'
import { OwnAnswers, ProfileCard, ResumeCode, StudyShell } from './StudyShell'

const KEY = 'lab'

function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const d = err.detail as { problems?: string[] } | string
    if (typeof d === 'object' && d?.problems) return d.problems.join('; ')
    return err.message
  }
  return 'Something went wrong. Try again.'
}

/** Cohab Lab (Cohab v2 plan W2): consent -> your own answers -> ~40 short
 * comparisons -> done. Anonymous; resumable with the code shown on screen. */
export function LabFlow() {
  const [token, setToken] = useState<string | null>(() => studyToken.get(KEY))
  const { data: instrument } = useQuery({ queryKey: ['study', 'instrument'], queryFn: studyApi.instrument })

  function begin(t: string) {
    studyToken.set(KEY, t)
    setToken(t)
  }

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
        <p className="text-cohab-muted">Thank you for your interest. Responses are no longer being collected.</p>
      </StudyShell>
    )
  }
  if (!token) return <Intro onBegin={begin} />
  return <LabSession token={token} consentVersion={instrument.consent_version} raterFields={instrument.rater_fields} onReset={() => { studyToken.clear(KEY); setToken(null) }} />
}

function Intro({ onBegin }: { onBegin: (token: string) => void }) {
  const [resume, setResume] = useState('')
  const create = useMutation({ mutationFn: () => studyApi.createRater('main'), onSuccess: (r) => onBegin(r.token) })
  return (
    <StudyShell>
      <h1 className="poster text-[48px] cohab-desktop:text-[60px] mb-3 max-w-[16ch]">Who would you rather live with?</h1>
      <p className="text-[14.5px] leading-[1.6] text-cohab-muted max-w-[640px] mb-6">
        A 20-minute study for Cohab, a roommate-matching project at CHRIST University. You answer the same lifestyle
        questions the app asks, then compare pairs of made-up roommates. Your choices teach the matcher what people
        actually weigh, instead of what we assumed.
      </p>
      <div className="flex flex-wrap gap-3 mb-8">
        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          Start the study
        </Button>
      </div>
      {create.isError && <p className="text-cohab-accent text-sm mb-4">{errorText(create.error)}</p>}
      <div className="surface rounded-[22px] p-4 max-w-[520px]">
        <p className="text-[13px] font-medium mb-2">Continuing from before?</p>
        <div className="flex gap-2">
          <Input value={resume} onChange={(e) => setResume(e.target.value.trim())} placeholder="Paste your resume code" />
          <Button variant="secondary" size="sm" className="h-auto" disabled={resume.length < 16} onClick={() => onBegin(resume)}>
            Resume
          </Button>
        </div>
      </div>
    </StudyShell>
  )
}

function LabSession({
  token,
  consentVersion,
  raterFields,
  onReset,
}: {
  token: string
  consentVersion: string
  raterFields: string[]
  onReset: () => void
}) {
  const qc = useQueryClient()
  const next = useQuery({
    queryKey: ['study', 'lab', 'next', token],
    queryFn: () => studyApi.next(token),
    retry: false,
  })

  const err = next.error as ApiError | null
  // 409 = an earlier step is missing (consent or own answers).
  const needsSetup = err?.status === 409
  if (err?.status === 401) {
    return (
      <StudyShell>
        <p className="text-cohab-muted mb-4">That resume code wasn't recognised. It may have been withdrawn.</p>
        <Button variant="secondary" onClick={onReset}>
          Start again
        </Button>
      </StudyShell>
    )
  }
  if (needsSetup) {
    return (
      <Setup
        token={token}
        consentVersion={consentVersion}
        raterFields={raterFields}
        onDone={() => qc.invalidateQueries({ queryKey: ['study', 'lab', 'next', token] })}
      />
    )
  }
  if (!next.data) {
    return (
      <StudyShell>
        <p className="text-cohab-muted">Loading…</p>
      </StudyShell>
    )
  }
  const { trial, progress } = next.data
  if (!trial) return <Finished token={token} onReset={onReset} />
  return (
    <StudyShell step={`${progress.answered + 1} / ${progress.total}`}>
      <Progress value={(progress.answered / progress.total) * 100} className="h-1 mb-5" />
      {trial.kind === 'rank' ? (
        <RankTrial key={trial.trial_id} token={token} trial={trial} />
      ) : (
        <PairTrial key={trial.trial_id} token={token} trial={trial} />
      )}
      <div className="mt-8">
        <ResumeCode token={token} />
      </div>
    </StudyShell>
  )
}

function Setup({
  token,
  consentVersion,
  raterFields,
  onDone,
}: {
  token: string
  consentVersion: string
  raterFields: string[]
  onDone: () => void
}) {
  const [step, setStep] = useState<'consent' | 'answers'>('consent')
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [important, setImportant] = useState<string[]>([])
  const consent = useMutation({ mutationFn: () => studyApi.consent(token, consentVersion), onSuccess: () => setStep('answers') })
  const save = useMutation({ mutationFn: () => studyApi.saveProfile(token, answers, important), onSuccess: onDone })
  const missing = raterFields.filter((f) => !answers[f]).length

  if (step === 'consent') {
    return (
      <StudyShell step="Consent">
        <h1 className="text-2xl font-semibold mb-4">Before you start</h1>
        <ul className="text-[14px] leading-[1.65] text-cohab-muted list-disc pl-5 mb-6 max-w-[680px] space-y-1.5">
          <li>We collect your lifestyle answers and your choices between made-up profiles. Nothing else: no name, email, phone or account.</li>
          <li>The profiles you compare are generated for the study. None of them is a real person.</li>
          <li>Responses are analysed in aggregate for a university project and may appear, anonymised, in its report.</li>
          <li>You can stop at any time. You can withdraw at the end, which deletes everything you answered.</li>
          <li>It takes about 20 minutes. There are no right answers.</li>
        </ul>
        <p className="text-[12px] text-cohab-subtle mb-4">Consent version {consentVersion}</p>
        <div className="flex gap-3">
          <Button onClick={() => consent.mutate()} disabled={consent.isPending}>
            I agree, continue
          </Button>
        </div>
        {consent.isError && <p className="text-cohab-accent text-sm mt-3">{errorText(consent.error)}</p>}
        <div className="mt-8">
          <ResumeCode token={token} />
        </div>
      </StudyShell>
    )
  }

  return (
    <StudyShell step={`Your answers · ${raterFields.length - missing}/${raterFields.length}`}>
      <h1 className="text-2xl font-semibold mb-1">First, about you</h1>
      <p className="text-[14px] text-cohab-muted mb-5 max-w-[640px]">
        The same questions Cohab asks every member. Your answers let us work out how well each made-up profile would
        suit you specifically.
      </p>
      <OwnAnswers answers={answers} onChange={(k, v) => setAnswers((a) => ({ ...a, [k]: v }))} fields={raterFields} />

      <section className="mt-6 surface rounded-[22px] p-4">
        <h3 className="text-[15.5px] font-semibold mb-1">What matters most to you? (up to three, optional)</h3>
        <p className="text-[13px] text-cohab-muted mb-3">The app boosts these by 1.5×. This study checks whether that number is right.</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {WEIGHT_TILES.map((t) => {
            const on = important.includes(t.id)
            return (
              <OptionPill
                key={t.id}
                selected={on}
                onClick={() =>
                  setImportant((cur) => (on ? cur.filter((x) => x !== t.id) : cur.length < 3 ? [...cur, t.id] : cur))
                }
              >
                {t.title}
              </OptionPill>
            )
          })}
        </div>
      </section>

      <div className="sticky bottom-0 bg-cohab-bg/95 backdrop-blur py-3 mt-6 flex items-center gap-3">
        <Button onClick={() => save.mutate()} disabled={missing > 0 || save.isPending}>
          {missing > 0 ? `${missing} left to answer` : 'Start comparing'}
        </Button>
        {save.isError && <p className="text-cohab-accent text-sm">{errorText(save.error)}</p>}
      </div>
    </StudyShell>
  )
}

const CONFIDENCE = [1, 2, 3, 4, 5]

function PairTrial({ token, trial }: { token: string; trial: StudyTrial }) {
  const qc = useQueryClient()
  const [left, right] = trial.cards
  const shownAt = useRef(performance.now())
  const [choice, setChoice] = useState<'left' | 'right' | 'none' | null>(null)
  const [confidence, setConfidence] = useState<number | null>(null)
  const [message, setMessage] = useState<{ left: boolean; right: boolean }>({ left: false, right: false })
  const [reason, setReason] = useState('')

  const differs = useMemo(
    () => new Set(Object.keys(left.answers).filter((k) => left.answers[k] !== right.answers[k])),
    [left, right],
  )

  useEffect(() => {
    shownAt.current = performance.now()
  }, [trial.trial_id])

  const submit = useMutation({
    mutationFn: () =>
      studyApi.respond(token, trial.trial_id, {
        choice,
        confidence,
        would_message: message.left && message.right ? 'both' : message.left ? 'left' : message.right ? 'right' : 'neither',
        reason_text: reason.trim() || null,
        response_ms: Math.round(performance.now() - shownAt.current),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['study', 'lab', 'next', token] }),
  })

  return (
    <div>
      <h1 className="text-xl font-semibold mb-1">Who would you rather live with?</h1>
      <p className="text-[13px] text-cohab-muted mb-4">Highlighted rows are where they differ. Tap a card to choose.</p>
      <div className="grid gap-3 sm:grid-cols-2 mb-4">
        <ProfileCard label="Person 1" answers={left.answers} differs={differs} selected={choice === 'left'} onSelect={() => setChoice('left')} />
        <ProfileCard label="Person 2" answers={right.answers} differs={differs} selected={choice === 'right'} onSelect={() => setChoice('right')} />
      </div>
      <button
        type="button"
        onClick={() => setChoice('none')}
        className={cn('text-[13px] mb-5 underline-offset-2 cursor-pointer', choice === 'none' ? 'text-cohab-ink font-semibold underline' : 'text-cohab-muted hover:underline')}
      >
        No preference between them
      </button>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-[13px] font-medium mb-2">How sure are you?</p>
          <div className="flex gap-2">
            {CONFIDENCE.map((c) => (
              <OptionPill key={c} selected={confidence === c} onClick={() => setConfidence(c)} className="w-11 min-h-10 px-0 text-center justify-center">
                {c}
              </OptionPill>
            ))}
          </div>
          <p className="text-[11.5px] text-cohab-subtle mt-1">1 = a guess, 5 = certain</p>
        </div>
        <div>
          <p className="text-[13px] font-medium mb-2">Would you message them to explore living together?</p>
          <div className="flex gap-2">
            {(['left', 'right'] as const).map((side, i) => (
              <OptionPill
                key={side}
                selected={message[side]}
                onClick={() => setMessage((m) => ({ ...m, [side]: !m[side] }))}
                className="w-auto min-h-10 px-3"
              >
                Person {i + 1}
              </OptionPill>
            ))}
          </div>
          <p className="text-[11.5px] text-cohab-subtle mt-1">Pick either, both, or neither.</p>
        </div>
      </div>

      <div className="mt-4">
        <Input value={reason} maxLength={140} onChange={(e) => setReason(e.target.value)} placeholder="What drove your choice? (optional, 140 characters)" />
      </div>

      <div className="mt-5 flex items-center gap-3">
        <Button onClick={() => submit.mutate()} disabled={!choice || !confidence || submit.isPending}>
          Next
        </Button>
        {submit.isError && <p className="text-cohab-accent text-sm">{errorText(submit.error)}</p>}
      </div>
    </div>
  )
}

function RankTrial({ token, trial }: { token: string; trial: StudyTrial }) {
  const qc = useQueryClient()
  const [order, setOrder] = useState<string[]>([])
  const shownAt = useRef(performance.now())
  const submit = useMutation({
    mutationFn: () =>
      studyApi.respond(token, trial.trial_id, { ranking: order, response_ms: Math.round(performance.now() - shownAt.current) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['study', 'lab', 'next', token] }),
  })
  function tap(id: string) {
    setOrder((o) => (o.includes(id) ? o.filter((x) => x !== id) : [...o, id]))
  }
  return (
    <div>
      <h1 className="text-xl font-semibold mb-1">Last one: put these six in order</h1>
      <p className="text-[13px] text-cohab-muted mb-4">Tap them from the person you'd most like to live with to the least. Tap again to undo.</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {trial.cards.map((c) => {
          const pos = order.indexOf(c.id)
          return (
            <div key={c.id} className="relative">
              {pos >= 0 && (
                <span className="absolute -top-2 -left-2 z-10 w-7 h-7 rounded-full bg-cohab-fill text-cohab-on-fill text-[13px] font-semibold flex items-center justify-center">
                  {pos + 1}
                </span>
              )}
              <ProfileCard label={`Person ${c.id}`} answers={c.answers} compact selected={pos >= 0} onSelect={() => tap(c.id)} />
            </div>
          )
        })}
      </div>
      <div className="mt-5 flex items-center gap-3">
        <Button onClick={() => submit.mutate()} disabled={order.length !== trial.cards.length || submit.isPending}>
          Finish
        </Button>
        {submit.isError && <p className="text-cohab-accent text-sm">{errorText(submit.error)}</p>}
      </div>
    </div>
  )
}

function Finished({ token, onReset }: { token: string; onReset: () => void }) {
  const [confirm, setConfirm] = useState(false)
  const withdraw = useMutation({ mutationFn: () => studyApi.withdraw(token), onSuccess: onReset })
  return (
    <StudyShell step="Done">
      <h1 className="poster text-[44px] mb-3">Thank you, that's everything</h1>
      <p className="text-[14.5px] text-cohab-muted max-w-[620px] mb-6">
        Your choices are now part of the dataset Cohab learns its weights from. If you know people who share a flat
        or room, the roommate-pair study takes ten minutes for each of them.
      </p>
      <div className="flex flex-wrap gap-3 mb-10">
        <Button variant="secondary" onClick={() => (window.location.href = '/study/pair')}>
          Open the roommate-pair study
        </Button>
      </div>
      {!confirm ? (
        <button type="button" onClick={() => setConfirm(true)} className="text-[13px] text-cohab-subtle underline cursor-pointer">
          Withdraw and delete my answers
        </button>
      ) : (
        <div className="bg-cohab-accent-tint border border-cohab-warn-border rounded-xl p-4 max-w-[520px]">
          <p className="text-[13.5px] mb-3">This permanently deletes everything you answered in this study.</p>
          <div className="flex gap-3">
            <Button variant="destructive" size="sm" onClick={() => withdraw.mutate()} disabled={withdraw.isPending}>
              Delete my answers
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setConfirm(false)}>
              Keep them
            </Button>
          </div>
        </div>
      )}
    </StudyShell>
  )
}
