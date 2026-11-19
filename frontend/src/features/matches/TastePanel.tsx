import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { tasteApi, type Taste } from '@/api/v2'
import { cn } from '@/lib/utils'

/** "Your list is learning" (D-14.22). Shows, in plain terms, what the taste
 * model has learned from your interest/pass decisions, how far it is from
 * starting, and a switch to turn it off. Everything here is about *you*:
 * no other member's data appears. */
export function TastePanel({ className, compact = false }: { className?: string; compact?: boolean }) {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['me', 'taste'], queryFn: tasteApi.get, staleTime: 30_000 })
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => tasteApi.set(enabled),
    onSuccess: (t) => {
      qc.setQueryData(['me', 'taste'], t)
      qc.invalidateQueries({ queryKey: ['matches'] })
    },
  })
  if (!data) return null

  return (
    <section className={cn('relative isolate grain overflow-hidden bg-[linear-gradient(135deg,#0b1033_0%,#1b2a9a_100%)] text-white rounded-[26px] p-6 shadow-[var(--shadow-soft)]', className)} aria-label="What your list has learned">
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="label text-[10px] text-cohab-sun">{data.active && data.enabled ? 'Learning from you' : 'Learns from you'}</span>
          <h2 className="poster text-white text-[30px] mt-1.5">
            {data.active ? 'Your list, tuned' : 'Say yes. Say no.'}
          </h2>
        </div>
        <Switch
          checked={data.enabled}
          disabled={toggle.isPending}
          onChange={(v) => toggle.mutate(v)}
          label="Use what it learned"
        />
      </div>

      {!data.active ? (
        <Progress taste={data} />
      ) : !data.enabled ? (
        <p className="text-[13.5px] leading-[1.5] text-white/70 mt-3">
          Off. Your list uses only your answers. Turn it back on any time; nothing it learned is lost.
        </p>
      ) : (
        <>
          {data.insights.length > 0 ? (
            <ul className="mt-3 flex flex-col gap-2">
              {data.insights.map((i) => (
                <li key={i.attribute} className="text-[14px] leading-[1.45] font-semibold">
                  <span className={cn('inline-block mr-1.5', i.direction === 'up' ? 'text-cohab-sun' : 'text-white/60')} aria-hidden>
                    {i.direction === 'up' ? '↑' : '↓'}
                  </span>
                  {i.text}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13.5px] leading-[1.5] text-white/70 mt-3">
              Your choices match what you said so far. It keeps watching.
            </p>
          )}
          {!compact && <ShiftBars weights={data.weights} />}
          <p className="text-[11.5px] text-white/50 mt-4">
            From {data.decisions} decisions ({data.positives} yes, {data.negatives} no). Scores on cards stay the same;
            only your order changes.
          </p>
        </>
      )}
    </section>
  )
}

function Progress({ taste }: { taste: Taste }) {
  const target = taste.decisions + taste.needed
  const pct = target ? Math.round((taste.decisions / target) * 100) : 0
  return (
    <div className="mt-3">
      <p className="text-[13.5px] leading-[1.5] text-white/75">
        Every interest and every pass teaches your list what you really care about. It starts after{' '}
        <span className="font-bold text-white">{taste.needed} more</span> {taste.needed === 1 ? 'decision' : 'decisions'}, with at
        least two of each.
      </p>
      <div className="mt-3 h-2 rounded-full bg-white/15 overflow-hidden">
        <div className="h-full rounded-full bg-cohab-sun transition-[width] duration-700" style={{ width: `${pct}%` }} />
      </div>
      <p className="label text-[9.5px] text-white/50 mt-2">
        {taste.decisions} of {target}
      </p>
    </div>
  )
}

/** Stated vs learned for the habits that moved most. */
function ShiftBars({ weights }: { weights: Taste['weights'] }) {
  const top = [...weights].sort((a, b) => Math.abs(b.shift) - Math.abs(a.shift)).slice(0, 5)
  const max = Math.max(...top.flatMap((w) => [w.stated, w.learned]), 0.01)
  return (
    <div className="mt-4 flex flex-col gap-2.5">
      <div className="flex gap-4 text-[11px] text-white/60">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-3 h-1.5 rounded-full bg-white/35" /> you said
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-3 h-1.5 rounded-full bg-cohab-sun" /> you chose
        </span>
      </div>
      {top.map((w) => (
        <div key={w.attribute}>
          <div className="flex justify-between text-[12.5px] font-semibold">
            <span className="capitalize">{w.label}</span>
            <span className={cn('tabular-nums', w.shift > 0 ? 'text-cohab-sun' : 'text-white/60')}>
              {w.shift > 0 ? '+' : ''}
              {(w.shift * 100).toFixed(1)} pts
            </span>
          </div>
          <div className="mt-1 flex flex-col gap-[3px]">
            <div className="h-[5px] rounded-full bg-white/35" style={{ width: `${(w.stated / max) * 100}%` }} />
            <div className="h-[5px] rounded-full bg-cohab-sun" style={{ width: `${(w.learned / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function Switch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative shrink-0 w-12 h-7 rounded-full transition-colors cursor-pointer disabled:opacity-50',
        checked ? 'bg-cohab-sun' : 'bg-white/25',
      )}
    >
      <span
        className={cn(
          'absolute top-1 w-5 h-5 rounded-full bg-cohab-dark-bg transition-[left] duration-200',
          checked ? 'left-6' : 'left-1',
        )}
      />
    </button>
  )
}
