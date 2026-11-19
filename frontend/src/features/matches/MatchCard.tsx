import { Link } from 'react-router-dom'
import { isGeneratedAvatar } from '@/components/ui/avatar'
import { CountUp } from '@/components/motion/CountUp'
import { ScoreRing } from '@/components/ScoreRing'
import { SaveToggle } from './SaveToggle'
import { TierBadge } from './MatchInsightsPanel'
import { scorePercent, scoreBand, BAND_COLOR } from '@/lib/score'
import { identity } from '@/lib/identity'
import { spotlightMove } from '@/lib/spotlight'
import { cn } from '@/lib/utils'
import type { MatchListItem } from '@/api/types'

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('')
}

/** Identity tile. A real uploaded photo fills it; otherwise the initials sit
 * on a colour keyed to the person's name. Never a stock face: these are real
 * members, and a borrowed photo would misrepresent them. */
function Portrait({ item, rank }: { item: MatchListItem; rank: number }) {
  const photo = item.avatar_url && !isGeneratedAvatar(item.avatar_url) ? item.avatar_url : null
  const id = identity(item.candidate_name)
  return (
    <div
      className="relative shrink-0 w-[84px] h-[84px] sm:w-[116px] sm:h-[116px] rounded-[24px] overflow-hidden flex items-center justify-center"
      style={photo ? undefined : { background: id.bg }}
    >
      {photo ? (
        <img src={photo} alt="" className="w-full h-full object-cover" />
      ) : (
        <span className="poster text-[42px] sm:text-[56px]" style={{ color: id.fg }}>
          {initials(item.candidate_name)}
        </span>
      )}
      <span className="absolute left-2 top-2 label text-[9.5px] bg-cohab-card text-cohab-ink rounded-full px-1.5 py-[3px] shadow-[0_2px_6px_rgb(11_16_51/0.18)]">
        #{rank}
      </span>
    </div>
  )
}

function Check() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
      <path d="M2.5 6.3l2.3 2.3 4.7-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function MatchCard({ item, rank = 1 }: { item: MatchListItem; rank?: number }) {
  const pct = scorePercent(item.combined_score)
  const band = scoreBand(pct)
  const seekerLine = item.seeker_type === 'has_place' ? 'Has a place' : 'Looking too'
  const moved = item.taste_rank_change ?? 0

  return (
    <Link to={`/matches/${item.match_id}`} className="block group" data-reveal-item="">
      <article onPointerMove={spotlightMove} className="cohab-lift surface spotlight relative rounded-[28px] p-4 sm:p-5 flex gap-4 sm:gap-5">
        <Portrait item={item} rank={rank} />

        <div className="min-w-0 flex-1 flex flex-col">
          <div className="flex items-start gap-2">
            <h3 className="poster text-[30px] sm:text-[38px] truncate min-w-0">{item.candidate_name}</h3>
            <SaveToggle matchId={item.match_id} className="ml-auto -mr-1 -mt-1 w-8 h-8 shrink-0" />
          </div>
          <p className="text-[13.5px] text-cohab-subtle mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-bold text-cohab-ink">{seekerLine}</span>
            <span aria-hidden>·</span>
            <span>
              ₹{item.budget_min.toLocaleString('en-IN')}
              {item.budget_max !== item.budget_min && `–${item.budget_max.toLocaleString('en-IN')}`}
            </span>
            {item.listing_locality && (
              <>
                <span aria-hidden>·</span>
                <span>{item.listing_locality}</span>
              </>
            )}
            {moved > 0 && (
              <span className="sun rounded-full px-2 py-[2px] text-[11.5px] font-bold" title="Moved up because of what you've chosen so far">
                ↑{moved} for you
              </span>
            )}
            <TierBadge tier={item.confidence_tier} source={item.calibration_source} probability={item.would_message_probability} />
          </p>

          <div className="flex flex-wrap gap-1.5 mt-3.5 pr-12 sm:pr-0">
            {item.agreements.slice(0, 3).map((a, i) => (
              <span
                key={a}
                className={cn(
                  'items-start sm:items-center gap-1.5 rounded-[14px] sm:rounded-full bg-cohab-tint text-cohab-primary text-[12.5px] leading-[1.3] font-bold px-2.5 py-1.5 sm:py-1',
                  i === 2 ? 'hidden sm:inline-flex' : 'inline-flex',
                )}
              >
                <span className="mt-[3px] sm:mt-0 shrink-0"><Check /></span>
                {a}
              </span>
            ))}
          </div>
          {item.divergence && (
            <p className="text-[13px] leading-[1.4] bg-cohab-accent-tint rounded-[12px] px-3 py-2 mt-3 pr-12 sm:pr-3 self-start">
              <span className="font-bold text-cohab-accent">Talk about:</span>{' '}
              <span className="text-cohab-muted">{item.divergence}</span>
            </p>
          )}
        </div>

        <div className="shrink-0 hidden sm:flex flex-col items-center justify-center pl-5 border-l border-cohab-border-soft w-[148px] gap-2">
          <ScoreRing pct={pct} size={104} stroke={9}>
            <CountUp value={pct} className="poster-num text-[44px] text-cohab-ink" />
          </ScoreRing>
          <span className="label text-[10px]" style={{ color: BAND_COLOR[band] }}>
            {band} fit
          </span>
        </div>
        {/* Phone: the score sits in the bottom-right corner instead of a column. */}
        <div className="sm:hidden absolute right-4 bottom-3.5 text-right leading-none">
          <span className="poster-num text-[40px]" style={{ color: BAND_COLOR[band] }}>
            {pct}
          </span>
          <span className="block label text-[8.5px] text-cohab-subtle mt-0.5">{band}</span>
        </div>
      </article>
    </Link>
  )
}
