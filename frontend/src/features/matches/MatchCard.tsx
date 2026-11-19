import { Link } from 'react-router-dom'
import { isGeneratedAvatar } from '@/components/ui/avatar'
import { CountUp } from '@/components/motion/CountUp'
import { SaveToggle } from './SaveToggle'
import { TierBadge } from './MatchInsightsPanel'
import { scorePercent, scoreBand, BAND_BAR_CLASS } from '@/lib/score'
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

/** Portrait tile. A real uploaded photo fills it; otherwise the initials are
 * set in the poster cut, alternating ink and outlined tiles so a list of
 * people without photos still has rhythm. Never a stock face: these are
 * real members, and a borrowed photo would misrepresent them. */
function Portrait({ item, rank }: { item: MatchListItem; rank: number }) {
  const photo = item.avatar_url && !isGeneratedAvatar(item.avatar_url) ? item.avatar_url : null
  const inverted = rank % 2 === 0
  return (
    <div
      className={cn(
        'relative shrink-0 w-[88px] h-[88px] sm:w-[120px] sm:h-[120px] rounded-[18px] overflow-hidden flex items-center justify-center',
        photo ? '' : inverted ? 'bg-cohab-card border-2 border-cohab-ink' : 'bg-cohab-ink',
      )}
    >
      {photo ? (
        <img src={photo} alt="" className="w-full h-full object-cover" />
      ) : (
        <span className={cn('poster text-[44px] sm:text-[58px]', inverted ? 'text-cohab-ink' : 'text-cohab-card')}>
          {initials(item.candidate_name)}
        </span>
      )}
      <span className="absolute left-1.5 top-1.5 label text-[9.5px] bg-cohab-card text-cohab-ink rounded-full px-1.5 py-[3px] border border-cohab-ink">
        #{rank}
      </span>
    </div>
  )
}

export function MatchCard({ item, rank = 1 }: { item: MatchListItem; rank?: number }) {
  const pct = scorePercent(item.combined_score)
  const band = scoreBand(pct)
  const seekerLine = item.seeker_type === 'has_place' ? 'Has a place' : 'Looking too'
  const moved = item.taste_rank_change ?? 0

  return (
    <Link to={`/matches/${item.match_id}`} className="block group" data-reveal-item="">
      <article className="relative bg-cohab-card border-2 border-cohab-ink rounded-[22px] p-3.5 sm:p-4 flex gap-4 transition-[transform,box-shadow] duration-300 ease-[cubic-bezier(.22,1,.36,1)] group-hover:-translate-y-0.5 group-hover:shadow-[6px_6px_0_0_var(--color-cohab-ink)]">
        <Portrait item={item} rank={rank} />

        <div className="min-w-0 flex-1 flex flex-col">
          <div className="flex items-start gap-2">
            <h3 className="poster text-[30px] sm:text-[38px] truncate min-w-0">{item.candidate_name}</h3>
            <SaveToggle matchId={item.match_id} className="ml-auto -mr-1 -mt-1 w-8 h-8 shrink-0" />
          </div>
          <p className="text-[13.5px] text-cohab-subtle mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-semibold text-cohab-ink">{seekerLine}</span>
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
              <span className="volt rounded-full px-2 py-[2px] text-[11.5px] font-bold" title="Moved up because of what you've chosen so far">
                ↑{moved} for you
              </span>
            )}
            <TierBadge tier={item.confidence_tier} source={item.calibration_source} probability={item.would_message_probability} />
          </p>

          <div className="flex flex-wrap gap-1.5 mt-3 pr-12 sm:pr-0">
            {item.agreements.slice(0, 3).map((a) => (
              <span key={a} className="rounded-full bg-cohab-tint text-cohab-ink text-[12.5px] font-semibold px-2.5 py-1">
                {a}
              </span>
            ))}
          </div>
          {item.divergence && (
            <p className="text-[13px] leading-[1.4] text-cohab-accent font-semibold mt-2.5 pr-12 sm:pr-0">
              Talk about: <span className="font-normal text-cohab-muted">{item.divergence}</span>
            </p>
          )}
        </div>

        <div className="shrink-0 hidden sm:flex flex-col items-end justify-between pl-4 border-l-2 border-cohab-ink/10 w-[120px]">
          <span className="label text-[9.5px] text-cohab-subtle">Match</span>
          <CountUp value={pct} className="poster-num text-[72px] text-cohab-ink" />
          <div className="w-full h-[6px] rounded-full bg-cohab-track overflow-hidden">
            <div className={cn('h-full rounded-full', BAND_BAR_CLASS[band])} style={{ width: `${pct}%` }} />
          </div>
          <span className="label text-[9.5px] text-cohab-ink mt-1.5">{band}</span>
        </div>
        {/* Phone: the score sits in the bottom-right corner instead of a column. */}
        <div className="sm:hidden absolute right-3.5 bottom-3 text-right leading-none">
          <span className="poster-num text-[40px] text-cohab-ink">{pct}</span>
          <span className="block label text-[8.5px] text-cohab-subtle mt-0.5">{band}</span>
        </div>
      </article>
    </Link>
  )
}
