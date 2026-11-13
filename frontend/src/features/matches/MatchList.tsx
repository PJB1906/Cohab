import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { matchesApi } from '@/api/matches'
import { feedbackApi } from '@/api/feedback'
import { insightsApi } from '@/api/v2'
import { MatchCard } from './MatchCard'
import { MatchInsightsPanel } from './MatchInsightsPanel'
import { AppShell } from '@/components/AppShell'
import { Tab } from '@/components/Tab'
import { ChipPill } from '@/components/OptionPill'
import { Input } from '@/components/ui/input'
import { Reveal } from '@/components/motion/Reveal'
import { RevealGroup } from '@/components/motion/RevealGroup'
import { cn } from '@/lib/utils'
import type { MatchListItem } from '@/api/types'

type SortKey = 'best' | 'budget'
type SeekerFilter = 'all' | 'has_place' | 'needs_place'

const SEEKER_OPTIONS: [SeekerFilter, string][] = [
  ['all', 'Anyone'],
  ['has_place', 'Has a place'],
  ['needs_place', 'Looking with you'],
]

type RoomFilter = 'any' | 'private' | 'shared'
type WindowFilter = 'any' | '14' | '30'

const ROOM_OPTIONS: [RoomFilter, string][] = [
  ['any', 'Any'],
  ['private', 'Private'],
  ['shared', 'Shared'],
]

const WINDOW_OPTIONS: [WindowFilter, string][] = [
  ['14', '±14 days'],
  ['30', '±30 days'],
  ['any', 'Any date'],
]

/** Days between the candidate's availability and your own move-in date.
 * Returns null when either date is missing — a candidate with no listing has
 * no `listing_available_from`, and is treated as unfiltered rather than
 * silently excluded. */
function moveInGapDays(item: MatchListItem): number | null {
  const theirs = item.listing_available_from ?? null
  const mine = item.move_in_date ?? null
  if (!theirs || !mine) return null
  const a = new Date(theirs).getTime()
  const b = new Date(mine).getTime()
  if (Number.isNaN(a) || Number.isNaN(b)) return null
  return Math.abs(a - b) / 86_400_000
}

function matchesFilters(
  item: MatchListItem,
  seekerFilter: SeekerFilter,
  cities: Set<string>,
  localities: Set<string>,
  room: RoomFilter,
  moveWindow: WindowFilter,
  min: number | null,
  max: number | null,
): boolean {
  if (seekerFilter !== 'all' && item.seeker_type !== seekerFilter) return false
  if (cities.size > 0 && !cities.has(item.city)) return false
  if (min !== null && item.budget_max < min) return false
  if (max !== null && item.budget_min > max) return false
  // Room type and locality only exist on a candidate who has a place, so a
  // set filter necessarily narrows to those candidates.
  if (localities.size > 0 && !localities.has(item.listing_locality ?? '')) return false
  if (room !== 'any' && item.listing_room_type !== room) return false
  if (moveWindow !== 'any') {
    const gap = moveInGapDays(item)
    if (gap !== null && gap > Number(moveWindow)) return false
  }
  return true
}

export function MatchList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['matches'],
    queryFn: () => matchesApi.list(),
  })

  const { data: pending } = useQuery({
    queryKey: ['feedback', 'pending'],
    queryFn: () => feedbackApi.pending(),
  })

  // `pool: null` from the insights endpoint means this account has no
  // preference profile yet, which is a different empty state from "nobody
  // fits": the fix is to finish the profile, not to wait.
  const { data: insights } = useQuery({ queryKey: ['matches', 'insights'], queryFn: insightsApi.get, staleTime: 60_000 })
  const noProfile = insights !== undefined && insights.pool === null

  const [sortBy, setSortBy] = useState<SortKey>('best')
  const [seekerFilter, setSeekerFilter] = useState<SeekerFilter>('all')
  const [rentMin, setRentMin] = useState('')
  const [rentMax, setRentMax] = useState('')
  const [cities, setCities] = useState<Set<string>>(new Set())
  const [localities, setLocalities] = useState<Set<string>>(new Set())
  const [room, setRoom] = useState<RoomFilter>('any')
  const [moveWindow, setMoveWindow] = useState<WindowFilter>('any')

  const allCities = useMemo(() => Array.from(new Set((data ?? []).map((m) => m.city))).sort(), [data])

  // Only candidates with a listing have a locality, so this list is naturally
  // limited to the "has a place" side of the pool.
  const allLocalities = useMemo(
    () =>
      Array.from(new Set((data ?? []).map((m) => m.listing_locality).filter((l): l is string => Boolean(l)))).sort(),
    [data],
  )

  function toggleLocality(locality: string) {
    setLocalities((prev) => {
      const next = new Set(prev)
      if (next.has(locality)) next.delete(locality)
      else next.add(locality)
      return next
    })
  }

  function toggleCity(city: string) {
    setCities((prev) => {
      const next = new Set(prev)
      if (next.has(city)) next.delete(city)
      else next.add(city)
      return next
    })
  }

  function resetFilters() {
    setSeekerFilter('all')
    setRentMin('')
    setRentMax('')
    setCities(new Set())
    setLocalities(new Set())
    setRoom('any')
    setMoveWindow('any')
  }

  const filtered = useMemo(() => {
    if (!data) return []
    const min = rentMin ? Number(rentMin.replace(/[^\d]/g, '')) || null : null
    const max = rentMax ? Number(rentMax.replace(/[^\d]/g, '')) || null : null
    const list = data.filter((m) =>
      matchesFilters(m, seekerFilter, cities, localities, room, moveWindow, min, max),
    )
    if (sortBy === 'budget') {
      return [...list].sort((a, b) => a.budget_min - b.budget_min)
    }
    return list
  }, [data, seekerFilter, cities, localities, room, moveWindow, rentMin, rentMax, sortBy])

  /** Identity of the current result set — re-runs the card stagger whenever
   * filtering or sorting actually changed what is on screen, which is the
   * feedback that a filter took effect. Includes the ids, not just the
   * count, so swapping one city for another of the same size still replays. */
  const runKey = useMemo(() => filtered.map((m) => m.match_id).join(','), [filtered])

  const excludedCount = (data?.length ?? 0) - filtered.length
  const countLine = data ? `${filtered.length} ${filtered.length === 1 ? 'match' : 'matches'}` : 'Your matches'

  const emptyMessage =
    data && data.length === 0
      ? noProfile
        ? null
        : "No matches yet — once more verified profiles join your area, they'll show up here."
      : data && filtered.length === 0
        ? 'No matches fit these filters — try widening your rent range or clearing a filter.'
        : null

  const profilePrompt = data && data.length === 0 && noProfile && (
    <div className="bg-cohab-card border border-cohab-border rounded-2xl p-5 max-w-[560px]">
      <p className="text-[15px] font-medium mb-1">Finish your profile to see matches</p>
      <p className="text-[13.5px] text-cohab-muted mb-3">
        Matches are worked out from your budget, move-in date and lifestyle answers. It takes about four minutes.
      </p>
      <Link to="/onboarding/questionnaire" className="text-cohab-primary font-medium text-[14px]">
        Answer the questions →
      </Link>
    </div>
  )

  const pendingBanner = pending && pending.length > 0 && (
    <div className="bg-cohab-tint border border-cohab-primary rounded-2xl p-4 mb-5">
      <p className="text-[13.5px] font-medium text-cohab-ink mb-2">
        {pending.length === 1 ? 'One match is' : `${pending.length} matches are`} waiting on your feedback.
      </p>
      <div className="flex flex-col gap-1.5">
        {pending.map((p) => (
          <Link key={p.match_id} to={`/matches/${p.match_id}`} className="text-[13px] text-cohab-primary font-medium">
            How did it go with {p.other_user_name}? →
          </Link>
        ))}
      </div>
    </div>
  )

  return (
    <AppShell>
      {/* Desktop — screen 7: 262px filters sidebar + ranked list */}
      <div className="hidden cohab-desktop:grid max-w-[1800px] mx-auto px-6 py-7 grid-cols-[262px_1fr] gap-8 items-start">
        {/* y=0: a sticky rail must not be given a transform, or it detaches
            from its containing block while the tween runs. Fade only. */}
        <Reveal
          as="aside"
          y={0}
          className="sticky top-[88px] bg-cohab-card border border-cohab-border rounded-2xl px-5 pt-5 pb-[22px]"
        >
          <div className="flex items-baseline justify-between mb-[18px]">
            <h2 className="text-[17px] font-semibold">Filters</h2>
            <button
              type="button"
              onClick={resetFilters}
              className="text-xs font-medium text-cohab-primary cursor-pointer"
            >
              Reset
            </button>
          </div>

          <p className="text-xs font-semibold text-cohab-score mb-[9px]">Monthly rent</p>
          <div className="flex items-center gap-2 mb-5">
            <Input
              value={rentMin}
              onChange={(e) => setRentMin(e.target.value)}
              placeholder="₹ Min"
              className="px-2.5 py-2.5 text-[13px] rounded-[10px] cohab-desktop:py-2.5 cohab-desktop:text-[13px]"
            />
            <span className="text-cohab-placeholder">–</span>
            <Input
              value={rentMax}
              onChange={(e) => setRentMax(e.target.value)}
              placeholder="₹ Max"
              className="px-2.5 py-2.5 text-[13px] rounded-[10px] cohab-desktop:py-2.5 cohab-desktop:text-[13px]"
            />
          </div>

          <p className="text-xs font-semibold text-cohab-score mb-[9px]">City</p>
          <div className="flex flex-col gap-[7px] mb-5">
            {allCities.map((city) => {
              const selected = cities.has(city)
              const count = (data ?? []).filter((m) => m.city === city).length
              return (
                <button
                  key={city}
                  type="button"
                  onClick={() => toggleCity(city)}
                  className={cn(
                    'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] text-left cursor-pointer transition-colors',
                    selected ? 'bg-cohab-tint' : 'bg-transparent hover:bg-cohab-bg',
                  )}
                >
                  <span
                    className={cn(
                      'w-[15px] h-[15px] rounded-[4px] border flex-none',
                      selected ? 'bg-cohab-primary border-cohab-primary' : 'bg-cohab-card border-cohab-border',
                    )}
                  />
                  <span className="flex-1 text-cohab-ink">{city}</span>
                  <span className="text-xs text-cohab-placeholder">{count}</span>
                </button>
              )
            })}
            {allCities.length === 0 && <p className="text-xs text-cohab-placeholder">No matches yet</p>}
          </div>

          {/* Locality / Room type / Move-in window (D-13.14) — the mockup's
              own sidebar has all three and the app shipped without them. All
              are computed from fields the API already sends; only
              `listing_locality` had to be added to the payload. */}
          {allLocalities.length > 0 && (
            <>
              <p className="text-xs font-semibold text-cohab-score mb-[9px]">Locality</p>
              <div className="flex flex-col gap-[7px] mb-5">
                {allLocalities.map((locality) => {
                  const selected = localities.has(locality)
                  const count = (data ?? []).filter((m) => m.listing_locality === locality).length
                  return (
                    <button
                      key={locality}
                      type="button"
                      onClick={() => toggleLocality(locality)}
                      className={cn(
                        'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] text-left cursor-pointer transition-colors',
                        selected ? 'bg-cohab-tint' : 'bg-transparent hover:bg-cohab-bg',
                      )}
                    >
                      <span
                        className={cn(
                          'w-[15px] h-[15px] rounded-[4px] border flex-none',
                          selected ? 'bg-cohab-primary border-cohab-primary' : 'bg-cohab-card border-cohab-border',
                        )}
                      />
                      <span className="flex-1 text-cohab-ink">{locality}</span>
                      <span className="text-xs text-cohab-placeholder">{count}</span>
                    </button>
                  )
                })}
              </div>
            </>
          )}

          <p className="text-xs font-semibold text-cohab-score mb-[9px]">Room type</p>
          <div className="flex flex-wrap gap-2 mb-5">
            {ROOM_OPTIONS.map(([value, label]) => (
              <Tab key={value} selected={room === value} onClick={() => setRoom(value)}>
                {label}
              </Tab>
            ))}
          </div>

          <p className="text-xs font-semibold text-cohab-score mb-[9px]">Move-in window</p>
          <div className="flex flex-wrap gap-2 mb-5">
            {WINDOW_OPTIONS.map(([value, label]) => (
              <Tab key={value} selected={moveWindow === value} onClick={() => setMoveWindow(value)}>
                {label}
              </Tab>
            ))}
          </div>

          <p className="text-xs font-semibold text-cohab-score mb-[9px]">Who they are</p>
          <div className="flex flex-wrap gap-2 mb-[18px]">
            {SEEKER_OPTIONS.map(([value, label]) => (
              <Tab key={value} selected={seekerFilter === value} onClick={() => setSeekerFilter(value)}>
                {label}
              </Tab>
            ))}
          </div>

          <div className="border-t border-cohab-border pt-3.5">
            <p className="text-xs leading-[1.5] text-cohab-subtle">
              Gender preference and other deal-breakers are applied as hard filters and can&apos;t be changed here.
              {excludedCount > 0 &&
                ` ${excludedCount} candidate${excludedCount === 1 ? '' : 's'} excluded by your filters.`}
            </p>
          </div>
        </Reveal>

        <div>
          <div className="flex items-end justify-between gap-5 mb-1.5">
            <h1 className="text-[26px] font-semibold tracking-[-.015em] leading-[1.18]">{countLine}</h1>
            <div className="flex items-center gap-2">
              <span className="text-[13px] text-cohab-muted">Sort</span>
              <Tab selected={sortBy === 'best'} onClick={() => setSortBy('best')}>
                Best match
              </Tab>
              <Tab selected={sortBy === 'budget'} onClick={() => setSortBy('budget')}>
                Budget
              </Tab>
            </div>
          </div>
          <p className="text-[13.5px] leading-[1.5] text-cohab-muted mb-5 max-w-[720px]">
            Ranked by compatibility computed in both directions. Every card shows the three strongest agreements and
            the single largest difference. A score is not a recommendation to move in — it is a shortlist.
          </p>

          {pendingBanner}

          {data && <MatchInsightsPanel className="mb-5 max-w-[720px]" listSize={data.length} />}

          {isLoading && <p className="text-cohab-muted">Loading…</p>}
          {error && <p className="text-cohab-accent">Couldn't load your matches. Try again shortly.</p>}
          {emptyMessage && <p className="text-cohab-muted">{emptyMessage}</p>}
          {profilePrompt}

          <RevealGroup className="flex flex-col gap-3.5" runKey={runKey}>
            {filtered.map((item) => (
              <MatchCard key={item.match_id} item={item} />
            ))}
          </RevealGroup>
        </div>
      </div>

      {/* Mobile — s7: header + horizontally-scrolling filter chips + card stack */}
      <div className="cohab-desktop:hidden">
        <div className="px-5 pt-2 pb-2.5 border-b border-cohab-border-soft">
          <div className="flex items-baseline justify-between mb-0.5">
            <h2 className="text-2xl font-semibold tracking-[-.02em]">Matches</h2>
            <button
              type="button"
              onClick={() => setSortBy((s) => (s === 'best' ? 'budget' : 'best'))}
              className="text-[13.5px] font-medium text-cohab-primary"
            >
              Sort: {sortBy === 'best' ? 'Best' : 'Budget'}
            </button>
          </div>
          <p className="text-[13px] leading-[1.4] text-cohab-muted-mobile mb-2.5">
            {data
              ? `${filtered.length} verified ${filtered.length === 1 ? 'person fits' : 'people fit'} your budget and area.`
              : 'Loading your matches…'}
          </p>
          <div className="flex gap-[7px] overflow-x-auto">
            {SEEKER_OPTIONS.map(([value, label]) => (
              <ChipPill key={value} selected={seekerFilter === value} onClick={() => setSeekerFilter(value)}>
                {label}
              </ChipPill>
            ))}
          </div>
        </div>

        <div className="px-5 py-3.5">
          {pendingBanner}

          {data && <MatchInsightsPanel className="mb-4" listSize={data.length} />}

          {isLoading && <p className="text-cohab-muted-mobile">Loading…</p>}
          {error && <p className="text-cohab-accent">Couldn't load your matches. Try again shortly.</p>}
          {emptyMessage && <p className="text-cohab-muted-mobile">{emptyMessage}</p>}
          {profilePrompt}

          <RevealGroup className="flex flex-col gap-3" runKey={runKey}>
            {filtered.map((item) => (
              <MatchCard key={item.match_id} item={item} />
            ))}
          </RevealGroup>

          {filtered.length > 0 && (
            <p className="text-center text-[12.5px] leading-[1.5] text-cohab-subtle-mobile pt-2.5 px-2.5">
              Scores compare your answers with theirs. They are not a guarantee — meet, talk, and decide for
              yourself.
            </p>
          )}
        </div>
      </div>
    </AppShell>
  )
}
