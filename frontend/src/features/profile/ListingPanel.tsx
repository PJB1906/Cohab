import { Link } from 'react-router-dom'
import { Eyebrow } from '@/components/Eyebrow'
import { Button } from '@/components/ui/button'
import type { ListingOut } from '@/api/types'

function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

/** The member's own listing, shown back to them (docs/DECISIONS.md D-13.9).
 *
 * `has_place` members fill in a listing — rent, locality, dates, amenities
 * and up to four photos — during onboarding, and then never saw any of it
 * again: the profile hub reduced the whole thing to a row reading "Added".
 * That is the record other people judge them on, and the values that act as
 * their own Stage 1 hard constraints, so it belongs on screen.
 *
 * The `listing` query already ran on this page to decide that row's label,
 * so rendering the detail costs no additional request. Editing routes back
 * to the existing `ListingForm`, which owns photo upload — deliberately not
 * duplicated here, since two places that can write `photos` is how they
 * drift apart.
 */
export function ListingPanel({ listing }: { listing: ListingOut | null | undefined }) {
  if (!listing) {
    return (
      <div className="mt-2 cohab-desktop:bg-cohab-card cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-[18px] cohab-desktop:p-7 cohab-desktop:mb-5">
        <Eyebrow className="mb-2">Your listing</Eyebrow>
        <p className="text-[13px] leading-[1.5] text-cohab-muted mb-4">
          You haven't described your room yet. Until you do, nobody looking for a place can be
          matched with you — the rent, locality and date are the hard constraints matching runs on.
        </p>
        <Link to="/onboarding/listing">
          <Button size="sm">Add your listing</Button>
        </Link>
      </div>
    )
  }

  const photos = listing.photos ?? []

  return (
    <div className="mt-2 cohab-desktop:bg-cohab-card cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-[18px] cohab-desktop:p-7 cohab-desktop:mb-5">
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <Eyebrow>Your listing</Eyebrow>
        <Link
          to="/onboarding/listing"
          className="text-[13px] font-medium text-cohab-primary hover:underline"
        >
          Edit
        </Link>
      </div>

      {photos.length > 0 ? (
        <div className="grid grid-cols-[2fr_1fr_1fr] gap-1.5 h-[132px] rounded-xl overflow-hidden mb-4">
          {photos.slice(0, 3).map((url) => (
            <img key={url} src={url} alt="" className="w-full h-full object-cover min-w-0" />
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3 border border-dashed border-cohab-border rounded-xl px-4 py-3.5 mb-4">
          <p className="text-[12.5px] leading-[1.45] text-cohab-subtle">
            No photos yet. Listings with photos get looked at far more often.
          </p>
          <Link to="/onboarding/listing" className="flex-none">
            <Button size="sm" variant="secondary">
              Add photos
            </Button>
          </Link>
        </div>
      )}

      <div className="grid grid-cols-2 gap-x-4 gap-y-2.5">
        <Fact label="Locality" value={listing.locality} />
        <Fact label="Rent" value={`₹${listing.rent_per_person.toLocaleString('en-IN')}/mo`} />
        <Fact label="Deposit" value={`₹${listing.deposit.toLocaleString('en-IN')}`} />
        <Fact label="Room" value={listing.room_type === 'private' ? 'Private' : 'Shared'} />
        <Fact label="Available from" value={formatDate(listing.available_from)} />
        <Fact
          label="Already living there"
          value={
            listing.current_housemates === undefined
              ? '—'
              : listing.current_housemates === 0
                ? 'Nobody yet'
                : `${listing.current_housemates}`
          }
        />
      </div>

      {listing.amenities.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-4">
          {listing.amenities.map((a) => (
            <span
              key={a}
              className="text-[12px] text-cohab-muted border border-cohab-border rounded-lg px-2.5 py-1"
            >
              {a}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[12px] text-cohab-subtle">{label}</div>
      <div className="text-[13.5px] font-medium text-cohab-ink mt-0.5">{value}</div>
    </div>
  )
}
