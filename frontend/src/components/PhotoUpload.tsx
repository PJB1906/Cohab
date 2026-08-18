import { useRef, useState } from 'react'
import { uploadsApi, type UploadKind } from '@/api/uploads'
import { ApiError } from '@/api/client'
import { cn } from '@/lib/utils'

/** Dropzone-style upload tile, matching the mockups' `<image-slot>`
 * placeholder aesthetic. Uploads immediately on file select and reports the
 * resulting URL back to the caller — no separate "save" step for the photo
 * itself (docs/DECISIONS.md D-5.3). */
export function PhotoUpload({
  kind,
  value,
  onChange,
  placeholder,
  className,
  aspect = 'aspect-square',
}: {
  kind: UploadKind
  value?: string | null
  onChange: (url: string) => void
  placeholder: string
  className?: string
  aspect?: string
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleFile(file: File) {
    setBusy(true)
    setError(null)
    try {
      const { url } = await uploadsApi.image(file, kind)
      onChange(url)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className={cn(
          aspect,
          'w-full rounded-xl border border-dashed border-cohab-border bg-cohab-bg overflow-hidden',
          'flex items-center justify-center text-center cursor-pointer disabled:opacity-60',
        )}
      >
        {value ? (
          <img src={value} alt={placeholder} className="w-full h-full object-cover" />
        ) : (
          <span className="text-[12.5px] text-cohab-subtle px-2">
            {busy ? 'Uploading…' : placeholder}
          </span>
        )}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) void handleFile(file)
          e.target.value = ''
        }}
      />
      {error && <span className="text-[11.5px] text-cohab-accent">{error}</span>}
    </div>
  )
}
