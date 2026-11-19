import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { savedApi } from '@/api/saved'
import { AppShell } from '@/components/AppShell'
import { RevealGroup } from '@/components/motion/RevealGroup'
import { Avatar } from '@/components/ui/avatar'
import { Progress } from '@/components/ui/progress'
import { MatchCard } from './MatchCard'
import { PageBanner } from '@/components/PageBanner'
import { EmptyState, emptyActionClass } from '@/components/EmptyState'
import { SaveToggle } from './SaveToggle'
import { scorePercent, scoreBand, BAND_COLOR, BAND_BAR_CLASS } from '@/lib/score'
import type { SavedMatchOut } from '@/api/types'

/** Condensed card per the mobile mockup's `#sSaved`: 44px avatar, one summary
 * line instead of MatchCard's full fact grid. The mockup's summary line is
 * "locality · rent · from <move-in date>" — those are listing fields, not on
 * `MatchListItem` (which only carries city + budget range for the candidate),
 * so this substitutes city + budget range rather than inventing a listing. */
function CondensedCard({ entry }: { entry: SavedMatchOut }) {
  const item = entry.match
  const pct = scorePercent(item.combined_score)
  const band = scoreBand(pct)

  return (
    <Link
      to={`/matches/${item.match_id}`}
      data-reveal-item=""
      className="block cohab-lift surface rounded-[22px] p-[15px]"
    >
      <div className="flex gap-3 items-start">
        <Avatar name={item.candidate_name} src={item.avatar_url} size={44} />
        <div className="flex-1 min-w-0">
          <div className="text-[16px] font-semibold text-cohab-ink truncate">{item.candidate_name}</div>
          <div className="text-[12.5px] leading-[1.4] text-cohab-muted-mobile mt-[3px] tabular-nums">
            {item.city} · ₹{item.budget_min.toLocaleString('en-IN')}–{item.budget_max.toLocaleString('en-IN')}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5 flex-none">
          <SaveToggle matchId={item.match_id} className="w-6 h-6" />
          <div className="text-right">
            <div className="text-[18px] font-bold tabular-nums text-cohab-ink leading-none">{pct}%</div>
            <div className="text-[11px] font-medium mt-1" style={{ color: BAND_COLOR[band] }}>
              {band}
            </div>
          </div>
        </div>
      </div>

      <Progress value={pct} barClassName={BAND_BAR_CLASS[band]} className="h-[3px] mt-3" />

      {item.divergence && (
        <p className="text-[12.5px] leading-[1.4] text-cohab-warn mt-2.5">{item.divergence} — worth discussing</p>
      )}
    </Link>
  )
}

export function SavedList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['saved'],
    queryFn: () => savedApi.list(),
  })

  const emptyMessage =
    data && data.length === 0
      ? "Nothing saved yet. Bookmark a match from your list to compare it later."
      : null

  return (
    <AppShell>
      {/* Desktop — no dedicated Saved screen in the desktop mockup; reusing
          MatchList's card language (header + card stack, no filters sidebar
          since Saved has nothing to filter) for token/layout consistency —
          a judgment call, not a mockup-sourced layout. */}
      <div className="hidden cohab-desktop:block max-w-[1800px] mx-auto px-6 py-7">
        <PageBanner photo="/photos/balcony-plants.webp" label="Private to you" title="Saved" className="mb-5">
          <p className="text-[14px] leading-[1.5] text-white/85 max-w-[52ch]">
            People you kept to compare later. Saving is private; they won't know.
          </p>
        </PageBanner>

        {isLoading && <p className="text-cohab-muted">Loading…</p>}
        {error && <p className="text-cohab-accent">Couldn't load your saved matches. Try again shortly.</p>}
        {emptyMessage && (
          <EmptyState
            art="saved"
            title="Nothing saved yet"
            action={<Link to="/matches" className={emptyActionClass}>Browse your matches</Link>}
          >
            Tap the bookmark on any match to keep them here and compare later.
          </EmptyState>
        )}

        <RevealGroup className="flex flex-col gap-3.5" runKey={data?.length}>
          {data?.map((entry) => (
            <MatchCard key={entry.match.match_id} item={entry.match} />
          ))}
        </RevealGroup>
      </div>

      {/* Mobile — mockup's #sSaved: header + condensed card stack + inert
          "compare" stub + drop-off caption */}
      <div className="cohab-desktop:hidden">
        <div className="px-4 pt-3">
          <PageBanner photo="/photos/balcony-plants.webp" title="Saved" size="sm">
            <p className="text-[13px] leading-[1.4] text-white/85">People you kept to compare. Saving is private.</p>
          </PageBanner>
        </div>

        <RevealGroup className="px-5 py-3.5 flex flex-col gap-2.5" runKey={data?.length}>
          {isLoading && <p className="text-cohab-muted-mobile">Loading…</p>}
          {error && <p className="text-cohab-accent">Couldn't load your saved matches. Try again shortly.</p>}
          {emptyMessage && (
            <EmptyState
              art="saved"
              title="Nothing saved yet"
              action={<Link to="/matches" className={emptyActionClass}>Browse your matches</Link>}
            >
              Tap the bookmark on any match to keep them here.
            </EmptyState>
          )}

          {data?.map((entry) => (
            <CondensedCard key={entry.match.match_id} entry={entry} />
          ))}

          {data && data.length > 0 && (
            <p className="text-[12.5px] leading-[1.5] text-cohab-subtle-mobile text-center px-3 pt-1">
              Saved people drop out of your list if they match with someone else or their room fills.
            </p>
          )}
        </RevealGroup>
      </div>
    </AppShell>
  )
}
