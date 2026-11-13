import { Link } from 'react-router-dom'
import { Avatar, isGeneratedAvatar } from '@/components/ui/avatar'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Eyebrow } from '@/components/Eyebrow'
import { CountUp } from '@/components/motion/CountUp'
import { SaveToggle } from './SaveToggle'
import { TierBadge } from './MatchInsightsPanel'
import { scorePercent, scoreBand, BAND_COLOR, BAND_BAR_CLASS } from '@/lib/score'
import type { MatchListItem } from '@/api/types'

export function MatchCard({ item }: { item: MatchListItem }) {
  const pct = scorePercent(item.combined_score)
  const band = scoreBand(pct)
  const barClass = BAND_BAR_CLASS[band]
  const seekerLine = item.seeker_type === 'has_place' ? 'Has a place' : 'Looking with you'

  return (
    <Link
      to={`/matches/${item.match_id}`}
      className="block group cohab-lift rounded-2xl"
      data-reveal-item=""
    >
      {/* Desktop — screen 7's card: 186px photo | info | 150px compatibility+budget col */}
      <div className="hidden cohab-desktop:grid grid-cols-[186px_1fr_150px] gap-5 bg-cohab-card border border-cohab-border rounded-2xl p-[18px] transition-colors group-hover:border-cohab-primary">
        <div className="relative h-[150px] min-w-0 rounded-xl overflow-hidden bg-cohab-tint flex items-center justify-center">
          {/* A generated initials avatar is a 256px square, and stretching it
              into this 186x150 landscape tile made the letters read as huge
              cropped type rather than a portrait (D-13.11). Seeded members
              have no real photograph, so the tile falls back to the same
              circular treatment the rest of the app uses. A genuine uploaded
              photo still fills the tile as screen 7 intends. */}
          {item.avatar_url && !isGeneratedAvatar(item.avatar_url) ? (
            <img src={item.avatar_url} alt="" className="w-full h-full object-cover" />
          ) : (
            <Avatar name={item.candidate_name} src={null} size={68} />
          )}
          <SaveToggle
            matchId={item.match_id}
            className="absolute top-2 right-2 w-7 h-7 bg-cohab-card/90 backdrop-blur border border-cohab-border"
          />
        </div>

        <div className="min-w-0 flex flex-col">
          <div className="flex items-center gap-2 mb-[3px]">
            <h3 className="text-lg font-semibold leading-[1.15]">{item.candidate_name}</h3>
            <Badge variant="verified" className="rounded">
              Verified
            </Badge>
            <TierBadge tier={item.confidence_tier} source={item.calibration_source} probability={item.would_message_probability} />
          </div>
          <p className="text-[13px] leading-[1.4] text-cohab-muted mb-2.5">
            {seekerLine} · {item.city}
          </p>
          <div className="flex flex-wrap gap-[7px]">
            {item.agreements.slice(0, 3).map((a) => (
              <Badge key={a} variant="agreement" className="rounded">
                {a}
              </Badge>
            ))}
            {item.divergence && (
              <Badge variant="divergence" className="rounded">
                {item.divergence}
              </Badge>
            )}
          </div>
          <div className="flex-1" />
        </div>

        <div className="border-l border-cohab-border pl-[18px] flex flex-col">
          <Eyebrow>Compatibility</Eyebrow>
          <CountUp
            value={pct}
            suffix="%"
            className="text-[27px] font-semibold tracking-[-.02em] tabular-nums mt-1.5 mb-2"
          />
          <Progress value={pct} barClassName={barClass} className="h-[3px] mb-3.5" animate />
          <Eyebrow>Budget</Eyebrow>
          <span className="text-[17px] font-semibold mt-[5px] mb-0.5 tabular-nums">
            ₹{item.budget_min.toLocaleString('en-IN')}–{item.budget_max.toLocaleString('en-IN')}
          </span>
          <span className="text-xs leading-[1.35] text-cohab-muted">per month</span>
        </div>
      </div>

      {/* Mobile — s7's card: avatar row, score bar, 2-col fact grid, agreement chips, divergence callout */}
      <div className="cohab-desktop:hidden bg-cohab-card border border-cohab-border rounded-[18px] p-[15px]">
        <div className="flex gap-3 items-start">
          <Avatar name={item.candidate_name} src={item.avatar_url} size={52} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[16.5px] font-semibold text-cohab-ink truncate">{item.candidate_name}</span>
              <Badge variant="verified" className="rounded">
                Verified
              </Badge>
            </div>
            <p className="text-[13px] text-cohab-muted-mobile mt-[3px]">
              {seekerLine} · {item.city}
            </p>
            <div className="mt-1">
              <TierBadge tier={item.confidence_tier} source={item.calibration_source} probability={item.would_message_probability} />
            </div>
          </div>
          <div className="text-right flex-none flex flex-col items-end gap-1">
            <SaveToggle matchId={item.match_id} className="w-6 h-6" />
            <CountUp value={pct} suffix="%" className="text-xl font-bold tabular-nums text-cohab-ink" />
            <div className="text-[11px] font-medium" style={{ color: BAND_COLOR[band] }}>
              {band}
            </div>
          </div>
        </div>

        <Progress value={pct} barClassName={barClass} className="h-[3px] mt-3 mb-3.5" animate />

        <div className="grid grid-cols-2 gap-x-3 gap-y-[7px] text-[13px] text-cohab-ink pb-3 border-b border-cohab-border-soft">
          <div>
            <span className="text-cohab-subtle-mobile">Budget </span>
            <span className="font-semibold tabular-nums">
              ₹{item.budget_min.toLocaleString('en-IN')}–{item.budget_max.toLocaleString('en-IN')}
            </span>
          </div>
          <div>{item.city}</div>
        </div>

        <div className="flex flex-wrap gap-1.5 mt-3">
          {item.agreements.slice(0, 3).map((a) => (
            <Badge key={a} variant="agreement" className="rounded-[10px] px-[9px] py-1.5">
              {a}
            </Badge>
          ))}
        </div>

        {item.divergence && (
          <div className="flex gap-2 items-start mt-2.5 bg-cohab-accent-tint rounded-xl px-2.5 py-2.5">
            <div className="w-[3px] self-stretch bg-cohab-accent rounded flex-none" />
            <p className="text-[12.5px] leading-[1.4] text-cohab-warn">
              <span className="font-semibold">Worth discussing · </span>
              {item.divergence}
            </p>
          </div>
        )}
      </div>
    </Link>
  )
}
