import { useLayoutEffect, useRef } from 'react'
import gsap from 'gsap'
import { motion, useMotionValue, useSpring, useTransform, type MotionValue } from 'motion/react'
import { Check } from 'lucide-react'
import { Logo } from '@/components/Logo'
import { Roofline } from '@/components/Roofline'
import { ScoreRing } from '@/components/ScoreRing'

const TICKER = ['Sleep', 'Guests', 'Tidiness', 'Noise', 'Rent on time', 'Cooking', 'Smoking', 'Pets', 'Chores', 'Splitting costs']

/** One layer of the collage, moved by the pointer at its own depth. */
function Layer({
  mx,
  my,
  depth,
  className,
  children,
  float = 0,
}: {
  mx: MotionValue<number>
  my: MotionValue<number>
  depth: number
  className?: string
  children: React.ReactNode
  /** Seconds for one slow up-and-down drift; 0 for none. */
  float?: number
}) {
  const x = useTransform(mx, (v) => v * depth * 28)
  const y = useTransform(my, (v) => v * depth * 20)
  return (
    <motion.div style={{ x, y }} className={className}>
      {float ? (
        <motion.div
          animate={{ y: [0, -10, 0] }}
          transition={{ duration: float, repeat: Infinity, ease: 'easeInOut' }}
        >
          {children}
        </motion.div>
      ) : (
        children
      )}
    </motion.div>
  )
}

/** The sign-in poster panel (D-14.27): the headline set line by line (GSAP),
 * a collage of a real photo, an example match card and a chat exchange that
 * drift with the pointer at different depths (Motion), the rooftop drawing
 * with lit windows, and a ticker of the habits Cohab asks about. The match
 * card is labelled as an example: it is not a member. */
export function AuthStage() {
  const root = useRef<HTMLDivElement>(null)
  const mxRaw = useMotionValue(0)
  const myRaw = useMotionValue(0)
  const mx = useSpring(mxRaw, { stiffness: 60, damping: 18 })
  const my = useSpring(myRaw, { stiffness: 60, damping: 18 })

  useLayoutEffect(() => {
    const el = root.current
    if (!el) return
    const mm = gsap.matchMedia()
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from(el.querySelectorAll('[data-line] > span'), {
        yPercent: 115,
        duration: 1.1,
        ease: 'power4.out',
        stagger: 0.09,
        delay: 0.05,
      })
      gsap.from(el.querySelectorAll('[data-rise]'), {
        y: 26,
        opacity: 0,
        duration: 0.9,
        ease: 'power3.out',
        stagger: 0.08,
        delay: 0.35,
      })
    })
    return () => mm.revert()
  }, [])

  return (
    <div
      ref={root}
      onPointerMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect()
        mxRaw.set((e.clientX - r.left) / r.width - 0.5)
        myRaw.set((e.clientY - r.top) / r.height - 0.5)
      }}
      onPointerLeave={() => {
        mxRaw.set(0)
        myRaw.set(0)
      }}
      className="hidden cohab-desktop:flex cohab-desktop:flex-col relative isolate grain overflow-hidden bg-[#0d0f14] text-white"
    >
      <Roofline tone="panel" seed={11} className="absolute inset-x-0 bottom-[58px] h-[150px] w-full -z-10" />

      <div className="px-12 pt-10">
        <Logo onDark pilot={false} size="lg" />
        <h1 className="poster text-white text-[clamp(64px,6.6vw,108px)] mt-10" aria-label="Find the one you can live with.">
          {['Find the', 'one you can', 'live with.'].map((line) => (
            <span key={line} data-line="" className="block overflow-hidden pb-[0.04em]" aria-hidden>
              <span className="block">{line}</span>
            </span>
          ))}
        </h1>
      </div>

      <div className="relative flex-1 min-h-[330px] mx-12 mt-8 mb-6">
        <Layer mx={mx} my={my} depth={0.6} className="absolute left-0 top-0 w-[66%] h-[86%]">
          <div data-rise="" className="w-full h-full rotate-[-2deg] rounded-[28px] overflow-hidden shadow-[0_30px_60px_-20px_rgb(0_0_0/0.8)] ring-1 ring-white/10">
            <img src="/photos/cooking-together.webp" alt="Two flatmates cooking together in a shared kitchen" className="kenburns w-full h-full object-cover" />
          </div>
        </Layer>

        <Layer mx={mx} my={my} depth={1.1} className="absolute right-0 bottom-0 w-[42%] h-[50%]">
          <div data-rise="" className="w-full h-full rotate-[3deg] rounded-[24px] overflow-hidden shadow-[0_30px_60px_-20px_rgb(0_0_0/0.8)] ring-[5px] ring-[#0d0f14]">
            <img src="/photos/room-sunlight.webp" alt="" className="w-full h-full object-cover" />
          </div>
        </Layer>

        <Layer mx={mx} my={my} depth={1.8} float={7} className="absolute right-[2%] top-[2%] w-[288px]">
          <div data-rise="" className="rounded-[24px] bg-white text-[#0d0f14] p-4 shadow-[0_30px_60px_-18px_rgb(0_0_0/0.85)]">
            <div className="flex items-center justify-between">
              <span className="label text-[9.5px] text-[#6b707d]">Example match</span>
              <span className="label text-[9.5px] rounded-full bg-[#ffc933] px-2 py-[3px]">Mutual</span>
            </div>
            <div className="flex items-center gap-3 mt-3">
              <span className="w-14 h-14 rounded-[16px] grid place-items-center poster text-[26px] bg-[#ff7a66]">AR</span>
              <div className="min-w-0 flex-1">
                <p className="poster text-[24px]">Asha R.</p>
                <p className="text-[12px] text-[#6b707d]">Has a place · Koramangala</p>
              </div>
              <ScoreRing pct={92} size={58} stroke={6} track="#e7e9ef">
                <span className="poster-num text-[22px]">92</span>
              </ScoreRing>
            </div>
            <div className="flex flex-col gap-1.5 mt-3">
              {['Both early risers', 'Split bills evenly'].map((t) => (
                <span key={t} className="inline-flex items-center gap-1.5 self-start rounded-full bg-[#eef1ff] text-[#2a4bff] text-[12px] font-bold px-2.5 py-1">
                  <Check className="size-3" strokeWidth={3} aria-hidden />
                  {t}
                </span>
              ))}
            </div>
          </div>
        </Layer>

        <Layer mx={mx} my={my} depth={2.4} float={5.5} className="absolute left-[6%] bottom-[2%]">
          <div data-rise="" className="flex flex-col items-start gap-2">
            <span className="bg-white text-[#0d0f14] rounded-[18px] rounded-bl-[5px] px-4 py-2.5 text-[14px] font-semibold shadow-[0_14px_30px_-12px_rgb(0_0_0/0.7)]">
              you cook on weekdays?
            </span>
            <span className="bg-[#ffc933] text-[#0d0f14] rounded-[18px] rounded-bl-[5px] px-4 py-2.5 text-[14px] font-semibold shadow-[0_14px_30px_-12px_rgb(0_0_0/0.7)] ml-8">
              every night. you do the dishes?
            </span>
          </div>
        </Layer>
      </div>

      <div className="relative border-t border-white/10 bg-[#0d0f14]/80 backdrop-blur-sm overflow-hidden" aria-hidden>
        <div className="flex w-max animate-[cohab-marquee_42s_linear_infinite] motion-reduce:animate-none py-4">
          {[...TICKER, ...TICKER].map((w, i) => (
            <span key={i} className="label text-[11px] text-white/70 px-5 flex items-center gap-5">
              {w}
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#ffc933]" />
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
