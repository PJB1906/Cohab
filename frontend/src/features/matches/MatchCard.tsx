import { Link } from 'react-router-dom'
import { Avatar } from '@/components/ui/avatar'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { scorePercent, scoreBand, BAND_COLOR, BAND_BAR_CLASS } from '@/lib/score'
import type { MatchListItem } from '@/api/types'

export function MatchCard({ item }: { item: MatchListItem }) {
  const pct = scorePercent(item.combined_score)
  const band = scoreBand(pct)

  return (
    <Link
      to={`/matches/${item.match_id}`}
      className="block bg-white border border-cohab-border rounded-2xl p-4 hover:border-cohab-primary transition-colors"
    >
      <div className="flex gap-3 items-start">
        <Avatar name={item.candidate_name} src={item.avatar_url} size={52} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[16.5px] font-semibold text-cohab-ink truncate">{item.candidate_name}</span>
          </div>
          <p className="text-[13px] text-cohab-muted mt-0.5">
            {item.seeker_type === 'has_place' ? 'Has a place' : 'Looking with you'} · {item.city}
          </p>
        </div>
        <div className="text-right flex-none">
          <div className="text-xl font-bold tabular-nums text-cohab-ink">{pct}%</div>
          <div className="text-[11px] font-medium mt-0.5" style={{ color: BAND_COLOR[band] }}>
            {band}
          </div>
        </div>
      </div>

      <Progress value={pct} className="mt-3 mb-3" barClassName={BAND_BAR_CLASS[band]} />

      <div className="flex flex-wrap gap-2 text-[13px] text-cohab-ink pb-3 border-b border-cohab-border-soft">
        <span>
          <span className="text-cohab-subtle">Budget </span>
          <span className="font-semibold tabular-nums">
            ₹{item.budget_min.toLocaleString('en-IN')}–{item.budget_max.toLocaleString('en-IN')}
          </span>
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5 mt-3">
        {item.agreements.slice(0, 3).map((a) => (
          <Badge key={a} variant="agreement">
            {a}
          </Badge>
        ))}
      </div>

      {item.divergence && (
        <div className="flex gap-2 items-start mt-2.5 bg-cohab-accent-tint rounded-xl px-3 py-2.5">
          <div className="w-[3px] self-stretch bg-cohab-accent rounded flex-none" />
          <p className="text-[12.5px] text-cohab-ink">
            <span className="font-semibold">Worth discussing · </span>
            {item.divergence}
          </p>
        </div>
      )}
    </Link>
  )
}
