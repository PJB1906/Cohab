import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listingApi } from '@/api/listing'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card } from '@/components/ui/card'
import { PhotoUpload } from '@/components/PhotoUpload'
import { ChipPill } from '@/components/OptionPill'
import type { RoomType } from '@/api/types'

// Proposed tag set — PRD/spec don't enumerate specific amenities.
const AMENITIES = ['Wi-Fi', 'Washing machine', 'Fridge', 'Geyser', 'Power backup', 'AC', 'Attached bath', 'Parking']

export function ListingForm() {
  const navigate = useNavigate()
  const [locality, setLocality] = useState('')
  const [rent, setRent] = useState('')
  const [deposit, setDeposit] = useState('')
  const [roomType, setRoomType] = useState<RoomType>('private')
  const [availableFrom, setAvailableFrom] = useState('')
  const [housemates, setHousemates] = useState('0')
  const [amenities, setAmenities] = useState<string[]>([])
  const [photos, setPhotos] = useState<(string | null)[]>([null, null, null])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function toggleAmenity(a: string) {
    setAmenities((prev) => (prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a]))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
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
      navigate('/onboarding/questionnaire')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <p className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle mb-3">
        Step 2 of 4 · Your listing
      </p>
      <h1 className="text-2xl font-semibold tracking-tight mb-2">Describe the room you're filling</h1>
      <p className="text-[15px] text-cohab-muted mb-7">
        These details also act as your hard constraints — anyone outside this rent, locality or
        date won't be shown to you at all.
      </p>

      <form onSubmit={submit} className="flex flex-col gap-5">
        <Card className="p-6">
          <h2 className="text-base font-semibold mb-4">Location and price</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="locality">Locality</Label>
              <Input id="locality" required value={locality} onChange={(e) => setLocality(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="available-from">Available from</Label>
              <Input
                id="available-from"
                type="date"
                required
                value={availableFrom}
                onChange={(e) => setAvailableFrom(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="rent">Rent per person, monthly (₹)</Label>
              <Input id="rent" type="number" min={1} required value={rent} onChange={(e) => setRent(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="deposit">Security deposit (₹)</Label>
              <Input
                id="deposit"
                type="number"
                min={0}
                required
                value={deposit}
                onChange={(e) => setDeposit(e.target.value)}
              />
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="text-base font-semibold mb-4">The room</h2>
          <Label>Room type</Label>
          <div className="flex gap-2 mb-4">
            {(['private', 'shared'] as const).map((rt) => (
              <ChipPill key={rt} selected={roomType === rt} onClick={() => setRoomType(rt)}>
                {rt === 'private' ? 'Private room' : 'Shared room'}
              </ChipPill>
            ))}
          </div>
          <Label htmlFor="housemates">People already living there</Label>
          <Input
            id="housemates"
            type="number"
            min={0}
            value={housemates}
            onChange={(e) => setHousemates(e.target.value)}
            className="mb-4 sm:w-40"
          />
          <Label>Amenities</Label>
          <div className="flex flex-wrap gap-2">
            {AMENITIES.map((a) => (
              <ChipPill key={a} selected={amenities.includes(a)} onClick={() => toggleAmenity(a)}>
                {a}
              </ChipPill>
            ))}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="text-base font-semibold mb-1">Photos</h2>
          <p className="text-[13px] text-cohab-muted mb-4">
            The room itself and the shared kitchen help most.
          </p>
          <div className="grid grid-cols-3 gap-3">
            <PhotoUpload
              kind="listing"
              placeholder="Room"
              value={photos[0]}
              onChange={(url) => setPhotos([url, photos[1], photos[2]])}
            />
            <PhotoUpload
              kind="listing"
              placeholder="Kitchen"
              value={photos[1]}
              onChange={(url) => setPhotos([photos[0], url, photos[2]])}
            />
            <PhotoUpload
              kind="listing"
              placeholder="Building"
              value={photos[2]}
              onChange={(url) => setPhotos([photos[0], photos[1], url])}
            />
          </div>
        </Card>

        {error && <p className="text-sm text-cohab-accent">{error}</p>}

        <Button type="submit" disabled={busy} className="self-start">
          {busy ? 'Saving…' : 'Save and continue'}
        </Button>
      </form>
    </div>
  )
}
