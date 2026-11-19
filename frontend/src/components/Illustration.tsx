import { cn } from '@/lib/utils'

export type IllustrationName = 'breakfast' | 'saved' | 'chat' | 'searching' | 'moving' | 'say-hi' | 'neighbors'

/** unDraw illustrations (unDraw License: free for commercial use, no
 * attribution required), recoloured to cobalt, each with a dark version.
 * Both render; CSS shows the one that matches the theme (index.css). Pass
 * `forceDark` on panels that are dark in both themes. Size with width/height
 * classes only; display is controlled by the theme rule. */
export function Illustration({
  name,
  className,
  forceDark = false,
}: {
  name: IllustrationName
  className?: string
  forceDark?: boolean
}) {
  if (forceDark) {
    return <img src={`/illustrations/${name}-dark.svg`} alt="" aria-hidden draggable={false} className={cn('object-contain select-none', className)} />
  }
  return (
    <>
      <img src={`/illustrations/${name}.svg`} alt="" aria-hidden draggable={false} className={cn('ill-light object-contain select-none', className)} />
      <img src={`/illustrations/${name}-dark.svg`} alt="" aria-hidden draggable={false} className={cn('ill-dark object-contain select-none', className)} />
    </>
  )
}
