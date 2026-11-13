import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { OnboardingHeader } from '@/components/OnboardingHeader'
import { PageTransition } from '@/components/motion/PageTransition'
import { useNavigate } from 'react-router-dom'
import { listingApi } from '@/api/listing'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card } from '@/components/ui/card'
import { PhotoUpload } from '@/components/PhotoUpload'
import { ChipPill } from '@/components/OptionPill'
import { MobileStepHeader } from '@/components/MobileStepHeader'
import type { RoomType } from '@/api/types'

// Proposed tag set — PRD/spec don't enumerate specific amenities.
const AMENITIES = ['Wi-Fi', 'Washing machine', 'Fridge', 'Geyser', 'Power backup', 'AC', 'Attached bath', 'Parking']

const ROOM_TYPES: { value: RoomType; label: string }[] = [
  { value: 'private', label: 'Private room' },
  { value: 'shared', label: 'Shared room' },
]

const mobileLabel = 'block text-[13px] font-medium text-cohab-ink mb-[7px]'

export function ListingForm() {
  const navigate = useNavigate()
  const [locality, setLocality] = useState('')
  const [rent, setRent] = useState('')
  const [deposit, setDeposit] = useState('')
  const [roomType, setRoomType] = useState<RoomType>('private')
  const [availableFrom, setAvailableFrom] = useState('')
  const [housemates, setHousemates] = useState('0')
  const [amenities, setAmenities] = useState<string[]>([])
  const [photos, setPhotos] = useState<(string | null)[]>([null, null, null, null])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Editing an existing listing (Profile -> "Edit listing") used to open
  // this form blank, so saving either failed validation or wiped the
  // listing. Load the saved one once and fill the fields from it.
  const queryClient = useQueryClient()
  const existing = useQuery({
    queryKey: ['listing', 'form-seed'],
    queryFn: () => listingApi.get(),
    retry: false,
    staleTime: 0,
    gcTime: 0,
  })
  const filled = useRef(false)
  useEffect(() => {
    const l = existing.data
    if (!l || filled.current) return
    filled.current = true
    setLocality(l.locality ?? '')
    setRent(String(l.rent_per_person ?? ''))
    setDeposit(String(l.deposit ?? ''))
    setRoomType(l.room_type)
    setAvailableFrom(l.available_from ?? '')
    setHousemates(String(l.current_housemates ?? 0))
    setAmenities(l.amenities ?? [])
    setPhotos([0, 1, 2, 3].map((i) => l.photos?.[i] ?? null))
  }, [existing.data])

  function toggleAmenity(a: string) {
    setAmenities((prev) => (prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a]))
  }

  function setPhoto(index: number, url: string) {
    setPhotos((prev) => prev.map((p, i) => (i === index ? url : p)))
  }

  const [draftSaved, setDraftSaved] = useState(false)

  async function save(advance: boolean) {
    if (!locality.trim() || !(Number(rent) > 0) || !availableFrom) {
      setError('Add the locality, the rent per person and the date the room is available.')
      return
    }
    setBusy(true)
    setError(null)
    setDraftSaved(false)
    try {
      await listingApi.put({
        locality,
        rent_per_person: Number(rent),
        deposit: Number(deposit),
        room_type: roomType,
        available_from: availableFrom,
        amenities,
        photos: photos.filter((p): p is string => Boolean(p)),
        current_housemates: Number(housemates) || 0,
      })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['listing'] }),
        queryClient.invalidateQueries({ queryKey: ['matches'] }),
      ])
      if (advance) navigate('/onboarding/questionnaire')
      else setDraftSaved(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    save(true)
  }

  // "Save as draft" is a plain button, not a second submit — the listing
  // schema still requires every field to be valid (there's no partial-save
  // shape on the backend), but unlike "Save and continue" it persists the
  // listing without forcing the wizard forward, so a member can leave and
  // pick up onboarding later. Used to be `type="submit"` on the same form,
  // which ran the identical validated save-and-advance — the two buttons
  // were indistinguishable in effect.
  async function saveDraft() {
    await save(false)
  }

  const roomTypeChips = (
    <div className="flex flex-wrap gap-2">
      {ROOM_TYPES.map((rt) => (
        <ChipPill key={rt.value} selected={roomType === rt.value} onClick={() => setRoomType(rt.value)}>
          {rt.label}
        </ChipPill>
      ))}
    </div>
  )

  const amenityChips = (
    <div className="flex flex-wrap gap-2">
      {AMENITIES.map((a) => (
        <ChipPill key={a} selected={amenities.includes(a)} onClick={() => toggleAmenity(a)}>
          {a}
        </ChipPill>
      ))}
    </div>
  )

  return (
    <>
      <OnboardingHeader hasOwnMobileBack />
    <PageTransition>
    <form onSubmit={submit} className="cohab-desktop:max-w-[1300px] cohab-desktop:mx-auto cohab-desktop:px-6 cohab-desktop:py-14">
      {error && (
        <p className="px-6 pt-3 text-sm text-cohab-accent cohab-desktop:px-0">{error}</p>
      )}

      {/* Mobile (< cohab-desktop) */}
      <div className="cohab-desktop:hidden flex flex-col">
        <MobileStepHeader step={2} totalSteps={4} progressPercent={50} onBack={() => navigate(-1)} />

        <div className="px-6 pt-3.5 pb-7">
          <h2 className="text-2xl font-semibold tracking-tight mb-1.5">Your room</h2>
          <p className="text-[14.5px] leading-relaxed text-cohab-muted-mobile mb-5.5">
            These details replace your budget and date preferences when we match you — you're
            stating a price, not a range.
          </p>

          <Label htmlFor="locality-m" className={mobileLabel}>
            Locality
          </Label>
          <Input
            id="locality-m"
            required
            value={locality}
            onChange={(e) => setLocality(e.target.value)}
            className="rounded-2xl mb-4.5"
          />

          <div className="grid grid-cols-2 gap-3.5 mb-4.5">
            <div>
              <Label htmlFor="rent-m" className={mobileLabel}>
                Rent per person
              </Label>
              <Input
                id="rent-m"
                type="number"
                min={1}
                required
                value={rent}
                onChange={(e) => setRent(e.target.value)}
                className="rounded-2xl"
              />
            </div>
            <div>
              <Label htmlFor="deposit-m" className={mobileLabel}>
                Deposit
              </Label>
              <Input
                id="deposit-m"
                type="number"
                min={0}
                required
                value={deposit}
                onChange={(e) => setDeposit(e.target.value)}
                className="rounded-2xl"
              />
            </div>
          </div>

          <Label className={mobileLabel}>Room type</Label>
          <div className="mb-4.5">{roomTypeChips}</div>

          <div className="grid grid-cols-2 gap-3.5 mb-4.5">
            <div>
              <Label htmlFor="available-from-m" className={mobileLabel}>
                Available from
              </Label>
              <Input
                id="available-from-m"
                type="date"
                required
                value={availableFrom}
                onChange={(e) => setAvailableFrom(e.target.value)}
                className="rounded-2xl"
              />
            </div>
            <div>
              <Label htmlFor="housemates-m" className={mobileLabel}>
                Flatmates now
              </Label>
              <Input
                id="housemates-m"
                type="number"
                min={0}
                value={housemates}
                onChange={(e) => setHousemates(e.target.value)}
                className="rounded-2xl"
              />
            </div>
          </div>

          <Label className={mobileLabel}>Amenities</Label>
          <div className="mb-2">{amenityChips}</div>
          <p className="text-[12.5px] leading-relaxed text-cohab-subtle-mobile mb-5">
            Tap to toggle. Amenities are shown on your listing, not scored.
          </p>

          <Label className={mobileLabel}>Photos</Label>
          <div className="grid grid-cols-2 gap-2 mb-2">
            <PhotoUpload
              kind="listing"
              placeholder="Living room"
              value={photos[0]}
              onChange={(url) => setPhoto(0, url)}
              aspect="h-[112px]"
            />
            <PhotoUpload
              kind="listing"
              placeholder="The room"
              value={photos[1]}
              onChange={(url) => setPhoto(1, url)}
              aspect="h-[112px]"
            />
            <PhotoUpload
              kind="listing"
              placeholder="Kitchen"
              value={photos[2]}
              onChange={(url) => setPhoto(2, url)}
              aspect="h-[112px]"
            />
            <PhotoUpload
              kind="listing"
              placeholder="Building"
              value={photos[3]}
              onChange={(url) => setPhoto(3, url)}
              aspect="h-[112px]"
            />
          </div>
          <p className="text-[12.5px] leading-relaxed text-cohab-subtle-mobile mb-6">
            At least three photos. Listings with photos of the actual room get roughly twice the
            responses.
          </p>

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? 'Saving…' : 'Save listing and continue'}
          </Button>
        </div>
      </div>

      {/* Desktop (>= cohab-desktop) */}
      <div className="hidden cohab-desktop:block">
        <p className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle mb-3.5">
          Step 2 of 4 · Your listing
        </p>
        <h1 className="text-[26px] font-semibold tracking-tight mb-2">
          Describe the room you're filling
        </h1>
        <p className="text-[15px] leading-relaxed text-cohab-muted mb-7 max-w-[640px]">
          These details also act as your hard constraints — anyone outside this rent, locality or
          date won't be shown to you at all.
        </p>

        <Card className="p-7 mb-5">
          <h2 className="text-[17px] font-semibold mb-5">Location and price</h2>
          <div className="grid grid-cols-2 gap-x-[22px] gap-y-[18px]">
            <div>
              <Label htmlFor="locality-d">Locality</Label>
              <Input id="locality-d" required value={locality} onChange={(e) => setLocality(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="available-from-d">Available from</Label>
              <Input
                id="available-from-d"
                type="date"
                required
                value={availableFrom}
                onChange={(e) => setAvailableFrom(e.target.value)}
              />
              <p className="text-xs text-cohab-subtle mt-1.5">
                Matched within a 30-day window either side.
              </p>
            </div>
            <div>
              <Label htmlFor="rent-d">Rent per person, monthly (₹)</Label>
              <Input
                id="rent-d"
                type="number"
                min={1}
                required
                value={rent}
                onChange={(e) => setRent(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="deposit-d">Security deposit (₹)</Label>
              <Input
                id="deposit-d"
                type="number"
                min={0}
                required
                value={deposit}
                onChange={(e) => setDeposit(e.target.value)}
              />
            </div>
          </div>
        </Card>

        <Card className="p-7 mb-5">
          <h2 className="text-[17px] font-semibold mb-[18px]">The room</h2>
          <Label>Room type</Label>
          <div className="mb-[22px]">{roomTypeChips}</div>
          <Label htmlFor="housemates-d">People already living there</Label>
          <Input
            id="housemates-d"
            type="number"
            min={0}
            value={housemates}
            onChange={(e) => setHousemates(e.target.value)}
            className="mb-[22px] w-40"
          />
          <Label>Amenities</Label>
          {amenityChips}
        </Card>

        <Card className="p-7 mb-6">
          <h2 className="text-[17px] font-semibold mb-1">Photos</h2>
          <p className="text-[13px] leading-relaxed text-cohab-muted mb-[18px]">
            The room itself and the shared kitchen help most.
          </p>
          <div className="grid grid-cols-[2fr_1fr_1fr] gap-3 h-[210px]">
            <PhotoUpload
              kind="listing"
              placeholder="Room — drop a photo"
              value={photos[0]}
              onChange={(url) => setPhoto(0, url)}
              aspect="h-full"
              className="h-full"
            />
            <PhotoUpload
              kind="listing"
              placeholder="Kitchen"
              value={photos[1]}
              onChange={(url) => setPhoto(1, url)}
              aspect="h-full"
              className="h-full"
            />
            <PhotoUpload
              kind="listing"
              placeholder="Building / street"
              value={photos[2]}
              onChange={(url) => setPhoto(2, url)}
              aspect="h-full"
              className="h-full"
            />
          </div>
        </Card>

        <div className="flex items-center gap-3.5">
          <Button type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Save and continue'}
          </Button>
          <Button type="button" variant="secondary" disabled={busy} onClick={saveDraft}>
            {busy ? 'Saving…' : 'Save as draft'}
          </Button>
          {draftSaved && <span className="text-sm text-cohab-primary">Saved</span>}
        </div>
      </div>
    </form>
    </PageTransition>
    </>
  )
}
