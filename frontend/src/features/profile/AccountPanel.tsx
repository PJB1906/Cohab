import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { authApi } from '@/api/auth'
import { uploadsApi } from '@/api/uploads'
import { ApiError } from '@/api/client'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SESSION_QUERY_KEY } from '@/hooks/useSession'
import type { UserOut } from '@/api/types'

/** Editable account details and profile photo (docs/DECISIONS.md D-13.9).
 *
 * Before this, `full_name`, `course` and `phone_number` were write-once at
 * registration and the avatar could only be set inside the signup wizard —
 * so a member who skipped the photo, or mistyped their name, had no way back
 * to either. `POST /uploads/image` already applied an avatar immediately on
 * upload; it simply had no entry point outside signup.
 *
 * The photo saves on selection (the upload endpoint commits it server-side),
 * while the text fields are an explicit edit/save pair — a name that
 * rewrites itself as you type is the wrong model for something that appears
 * on every match card another member sees.
 */
export function AccountPanel({ user }: { user: UserOut }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [fullName, setFullName] = useState(user.full_name)
  const [course, setCourse] = useState(user.course ?? '')
  const [phone, setPhone] = useState(user.phone_number ?? '')
  const [photoError, setPhotoError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const save = useMutation({
    mutationFn: () =>
      authApi.updateMe({ full_name: fullName, course, phone_number: phone }),
    onSuccess: (updated) => {
      // Write straight into the session cache so the header avatar and name
      // update without a refetch round-trip.
      queryClient.setQueryData(SESSION_QUERY_KEY, updated)
      setEditing(false)
    },
  })

  async function onPickPhoto(file: File) {
    setPhotoError(null)
    setUploading(true)
    try {
      await uploadsApi.image(file, 'avatar')
      // The endpoint persists `user.avatar_url` itself, so the authoritative
      // value comes back from a session refetch rather than being guessed.
      await queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY })
    } catch (e) {
      setPhotoError(
        e instanceof ApiError ? e.message : 'Could not upload that image — try another file.',
      )
    } finally {
      setUploading(false)
    }
  }

  function cancel() {
    setFullName(user.full_name)
    setCourse(user.course ?? '')
    setPhone(user.phone_number ?? '')
    save.reset()
    setEditing(false)
  }

  return (
    <div className="flex items-start gap-4 pb-5 mb-1 border-b border-cohab-border-soft cohab-desktop:bg-cohab-card cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-[18px] cohab-desktop:p-7 cohab-desktop:mb-5">
      <div className="flex flex-col items-center gap-2 flex-none">
        <Avatar name={user.full_name} src={user.avatar_url} size={60} />
        <label className="text-[12px] font-medium text-cohab-primary cursor-pointer hover:underline">
          {uploading ? 'Uploading…' : user.avatar_url ? 'Change' : 'Add photo'}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            disabled={uploading}
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) onPickPhoto(file)
              // Reset so re-picking the same file fires `change` again.
              e.target.value = ''
            }}
          />
        </label>
      </div>

      <div className="flex-1 min-w-0">
        {editing ? (
          <div className="flex flex-col gap-2.5">
            <div>
              <label htmlFor="acct-name" className="block text-[12px] font-medium text-cohab-muted mb-1">
                Full name
              </label>
              <Input
                id="acct-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your name"
              />
            </div>
            <div>
              <label htmlFor="acct-course" className="block text-[12px] font-medium text-cohab-muted mb-1">
                Course and year
              </label>
              <Input
                id="acct-course"
                value={course}
                onChange={(e) => setCourse(e.target.value)}
                placeholder="e.g. MSc Data Science, 2nd year"
              />
            </div>
            <div>
              <label htmlFor="acct-phone" className="block text-[12px] font-medium text-cohab-muted mb-1">
                Phone number
              </label>
              <Input
                id="acct-phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Optional"
                inputMode="tel"
              />
              <p className="text-[12px] leading-[1.45] text-cohab-subtle mt-1">
                Hidden by default. Shared with one match at a time, and only after you both agree.
              </p>
            </div>

            {save.isError && (
              <p className="text-[13px] text-cohab-accent">
                {save.error instanceof ApiError
                  ? save.error.message
                  : 'Could not save those changes — try again.'}
              </p>
            )}

            <div className="flex items-center gap-2.5">
              <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
                {save.isPending ? 'Saving…' : 'Save changes'}
              </Button>
              <Button size="sm" variant="secondary" onClick={cancel} disabled={save.isPending}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xl font-semibold text-cohab-ink truncate">{user.full_name}</div>
              <div className="text-[13px] text-cohab-muted mt-1 leading-[1.45]">
                {user.course ? (
                  <>
                    {user.course}
                    <br />
                  </>
                ) : (
                  <>
                    <span className="text-cohab-subtle">No course added yet</span>
                    <br />
                  </>
                )}
                {user.phone_number ? `Phone ${user.phone_number}` : 'No phone number yet'}
              </div>
            </div>
            <Button size="sm" variant="secondary" onClick={() => setEditing(true)} className="flex-none">
              Edit
            </Button>
          </div>
        )}

        {photoError && <p className="text-[13px] text-cohab-accent mt-2">{photoError}</p>}
      </div>
    </div>
  )
}
