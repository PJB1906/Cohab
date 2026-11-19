/** Identity tiles (D-14.24): a decorative colour per person, keyed by a hash of
 * their name so it never changes between visits. Colour carries no meaning
 * here (strength, warnings and match moments use their own tokens). `fg` is
 * the ink that keeps AA contrast on that tile. */
const TILES = [
  { bg: 'var(--color-id-1)', fg: '#ffffff' },
  { bg: 'var(--color-id-2)', fg: '#0b1033' },
  { bg: 'var(--color-id-3)', fg: '#0b1033' },
  { bg: 'var(--color-id-4)', fg: '#0b1033' },
  { bg: 'var(--color-id-5)', fg: '#0b1033' },
  { bg: 'var(--color-id-6)', fg: '#0b1033' },
] as const

export function identity(key: string): { bg: string; fg: string } {
  let h = 0
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0
  return TILES[h % TILES.length]
}
