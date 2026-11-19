import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Logo } from '@/components/Logo'

interface Credit {
  file: string
  photographer: string
  source: string
  license: string
}

/** Photo credits. The Unsplash License does not require attribution; we give
 * it anyway, and keep the list generated from the same file the downloader
 * wrote, so it cannot drift from the photos actually shipped. */
export function Credits() {
  const { data } = useQuery({
    queryKey: ['photo-credits'],
    queryFn: async () => (await fetch('/photos/CREDITS.json')).json() as Promise<Credit[]>,
  })
  const { data: illustrations } = useQuery({
    queryKey: ['illustration-credits'],
    queryFn: async () => (await fetch('/illustrations/CREDITS.json')).json() as Promise<{ file: string; title: string; source: string }[]>,
  })
  return (
    <div className="min-h-screen bg-cohab-bg">
      <header className="max-w-[1100px] mx-auto px-5 h-[72px] flex items-center">
        <Link to="/">
          <Logo />
        </Link>
      </header>
      <main className="max-w-[1100px] mx-auto px-5 pb-20">
        <h1 className="poster text-[64px] cohab-desktop:text-[96px]">Photo credits</h1>
        <p className="text-[16px] text-cohab-muted mt-4 max-w-[60ch]">
          All photographs are from Unsplash, used under the Unsplash License. None of them shows a Cohab member.
        </p>
        <ul className="grid sm:grid-cols-2 cohab-desktop:grid-cols-3 gap-5 mt-10">
          {(data ?? []).map((c) => (
            <li key={c.file}>
              <img src={`/${c.file}`} alt="" loading="lazy" className="w-full h-[200px] object-cover rounded-[18px] border border-cohab-border" />
              <p className="text-[14px] font-semibold text-cohab-ink mt-2">{c.photographer}</p>
              <a href={c.source} target="_blank" rel="noreferrer noopener" className="text-[13px] text-cohab-subtle underline underline-offset-2">
                View on Unsplash
              </a>
            </li>
          ))}
        </ul>

        <h2 className="poster text-[44px] cohab-desktop:text-[64px] mt-20">Illustrations</h2>
        <p className="text-[16px] text-cohab-muted mt-4 max-w-[60ch]">
          Illustrations are from unDraw by Katerina Limpitsouni, used under the unDraw License (free for commercial
          use, no attribution required), recoloured to Cohab's palette. The rooftop drawing is our own.
        </p>
        <ul className="grid grid-cols-2 sm:grid-cols-3 cohab-desktop:grid-cols-4 gap-5 mt-10">
          {(illustrations ?? []).map((c) => (
            <li key={c.file} className="surface rounded-[18px] p-4">
              <img src={`/${c.file}`} alt="" loading="lazy" className="w-full h-[120px] object-contain" />
              <a href={c.source} target="_blank" rel="noreferrer noopener" className="block text-[13px] text-cohab-subtle underline underline-offset-2 mt-3 capitalize">
                {c.title}
              </a>
            </li>
          ))}
        </ul>
      </main>
    </div>
  )
}
