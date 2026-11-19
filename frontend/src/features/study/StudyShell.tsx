import { Link } from 'react-router-dom'
import { Logo } from '@/components/Logo'
import { ThemeToggle } from '@/components/ThemeToggle'
import { CARD_ROWS } from '@/data/studyCards'
import { OPTIONAL_TIER2_QUESTIONS, REQUIRED_QUESTIONS, type Question } from '@/data/questionnaire'
import { OptionPill } from '@/components/OptionPill'
import { cn } from '@/lib/utils'

/** The study lives outside the product: no account, no navigation into the
 * app, and nothing on screen that identifies a real member. */
export function StudyShell({ children, step }: { children: React.ReactNode; step?: string }) {
  return (
    <div className="min-h-screen bg-cohab-bg text-cohab-ink">
      <header className="border-b border-cohab-border-soft">
        <div className="max-w-[880px] mx-auto px-4 h-14 flex items-center gap-3">
          <Link to="/study" className="cohab-press">
            <Logo />
          </Link>
          <span className="text-[12px] font-medium text-cohab-subtle border border-cohab-border rounded-full px-2 py-0.5">
            Research study
          </span>
          <div className="flex-1" />
          {step && <span className="text-[12.5px] tabular-nums text-cohab-muted">{step}</span>}
          <ThemeToggle />
        </div>
      </header>
      <main className="max-w-[880px] mx-auto px-4 py-6 pb-16">{children}</main>
    </div>
  )
}

export const STUDY_QUESTIONS: Question[] = [...REQUIRED_QUESTIONS, ...OPTIONAL_TIER2_QUESTIONS]

/** The rater's own answers: the same 21 lifestyle fields the product asks. */
export function OwnAnswers({
  answers,
  onChange,
  fields,
}: {
  answers: Record<string, string>
  onChange: (key: string, value: string) => void
  fields: string[]
}) {
  return (
    <div className="flex flex-col gap-5">
      {STUDY_QUESTIONS.map((q) => {
        const parts = q.parts.filter((p) => fields.includes(p.key))
        if (parts.length === 0) return null
        return (
          <fieldset key={q.id} className="surface rounded-[22px] p-4">
            <legend className="sr-only">{q.title}</legend>
            <p className="text-[11px] uppercase tracking-wide text-cohab-subtle mb-1">{q.theme}</p>
            <h3 className="text-[15.5px] font-semibold mb-3">{q.title}</h3>
            {parts.map((part) => (
              <div key={part.key} className="mb-3 last:mb-0">
                {part.label && <p className="text-[13px] font-medium text-cohab-muted mb-2">{part.label}</p>}
                <div className="grid gap-2 sm:grid-cols-2">
                  {part.options.map((o) => (
                    <OptionPill key={o.value} selected={answers[part.key] === o.value} onClick={() => onChange(part.key, o.value)}>
                      {o.label}
                    </OptionPill>
                  ))}
                </div>
              </div>
            ))}
          </fieldset>
        )
      })}
    </div>
  )
}

/** One anonymised profile card. In a pair trial, rows that differ from the
 * other card are marked, so the comparison is quick to read. */
export function ProfileCard({
  label,
  answers,
  differs,
  selected,
  onSelect,
  compact,
}: {
  label: string
  answers: Record<string, string>
  differs?: Set<string>
  selected?: boolean
  onSelect?: () => void
  compact?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={!onSelect}
      aria-pressed={selected}
      className={cn(
        'text-left w-full rounded-2xl border p-4 transition-colors bg-cohab-card',
        onSelect && 'cursor-pointer hover:border-cohab-primary',
        selected ? 'border-cohab-primary ring-2 ring-cohab-primary/40' : 'border-cohab-border',
      )}
    >
      <p className="text-[13px] font-semibold mb-2.5">{label}</p>
      <dl className={cn('grid gap-y-1.5', compact ? 'text-[12px]' : 'text-[13px]')}>
        {CARD_ROWS.map((row) => {
          const value = answers[row.field]
          if (!value) return null
          const diff = differs?.has(row.field)
          return (
            <div key={row.field} className={cn('grid grid-cols-[112px_1fr] gap-2 rounded-md px-1.5 py-0.5', diff && 'bg-cohab-tint')}>
              <dt className="text-cohab-subtle">{row.heading}</dt>
              <dd className={cn(diff ? 'text-cohab-ink font-medium' : 'text-cohab-muted')}>{row.text[value] ?? value}</dd>
            </div>
          )
        })}
      </dl>
    </button>
  )
}

export function ResumeCode({ token }: { token: string }) {
  return (
    <div className="text-[12px] text-cohab-subtle">
      Resume code (keep it to continue later on this or another device):{' '}
      <code className="select-all bg-cohab-tint text-cohab-ink rounded px-1.5 py-0.5 break-all">{token}</code>
    </div>
  )
}
