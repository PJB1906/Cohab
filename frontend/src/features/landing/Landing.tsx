import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { motion, useScroll, useSpring, useTransform } from 'motion/react'
import { ButtonArrow } from '@/components/ui/button'
import { Chemistry, type ChemistryRow } from '@/components/Chemistry'
import { Logo } from '@/components/Logo'
import { Roofline } from '@/components/Roofline'
import { ThemeToggle } from '@/components/ThemeToggle'
import { cn } from '@/lib/utils'

/** Public landing page (D-14.23). Poster direction: one huge condensed
 * headline, real photography in bold frames, a black marquee, and the match
 * chemistry chart as the proof. Every claim on this page is something the
 * product actually does; the one number about learning is labelled as a
 * simulation result, because that is what it is. */

const MARQUEE = ['Sleep', 'Tidiness', 'Guests', 'Noise', 'Rent on time', 'Cooking', 'Smoking', 'Sharing', 'Budget', 'Chores']

const DEMO: ChemistryRow[] = [
  { key: 'clean', label: 'Tidiness', you: 0.95, them: 0.92 },
  { key: 'sleep', label: 'Sleep', you: 0.88, them: 0.84 },
  { key: 'guests', label: 'Guests', you: 1.0, them: 0.62 },
  { key: 'pay', label: 'Rent on time', you: 0.95, them: 1.0 },
  { key: 'noise', label: 'Noise', you: 0.6, them: 0.85 },
  { key: 'comms', label: 'When things bug you', you: 0.45, them: 0.45 },
]

const STEPS = [
  {
    n: '01',
    title: 'Prove you are a student',
    body: 'Your institutional email and a one-time code. Unverified accounts never appear in anyone’s list.',
    img: '/photos/students-hall.webp',
    alt: 'Students talking in a lecture hall',
  },
  {
    n: '02',
    title: 'Twelve honest questions',
    body: 'How you sleep, clean, host and pay. The things people only find out after they sign a lease.',
    img: '/photos/kitchen-prep.webp',
    alt: 'Someone chopping vegetables in a home kitchen',
  },
  {
    n: '03',
    title: 'A shortlist, with reasons',
    body: 'Ranked both ways: how they suit you and how you suit them. Every card names the one thing you disagree on.',
    img: '/photos/flatmates-talking.webp',
    alt: 'Two flatmates talking on a sofa',
  },
]

function Marquee() {
  const words = [...MARQUEE, ...MARQUEE]
  return (
    <div className="bg-cohab-dark-bg text-white overflow-hidden" aria-hidden>
      <div className="flex w-max animate-[cohab-marquee_38s_linear_infinite] motion-reduce:animate-none py-5">
        {words.map((w, i) => (
          <span key={i} className="poster text-[46px] cohab-desktop:text-[64px] px-6 flex items-center gap-6">
            {w}
            <span className="inline-block w-3 h-3 rounded-[3px] bg-cohab-sun" />
          </span>
        ))}
      </div>
    </div>
  )
}

function Sticker({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        'absolute rounded-[18px] px-4 py-2.5 text-[14px] font-semibold shadow-[0_10px_30px_-12px_rgba(0,0,0,.45)]',
        className,
      )}
    >
      {children}
    </span>
  )
}

/** Scroll progress along the top edge (Motion). */
function ScrollBar() {
  const { scrollYProgress } = useScroll()
  const scaleX = useSpring(scrollYProgress, { stiffness: 140, damping: 30, restDelta: 0.001 })
  return <motion.div aria-hidden style={{ scaleX }} className="fixed top-0 inset-x-0 h-[3px] origin-left bg-cohab-sun z-50" />
}

/** The hero collage: photos, the score card and the chat stickers drift
 * apart at different speeds as the page scrolls (Motion), and the stickers
 * bob gently. */
function HeroStack() {
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] })
  const back = useTransform(scrollYProgress, [0, 1], [0, -70])
  const mid = useTransform(scrollYProgress, [0, 1], [0, -20])
  const front = useTransform(scrollYProgress, [0, 1], [0, -140])
  const card = useTransform(scrollYProgress, [0, 1], [0, -220])
  const cardTurn = useTransform(scrollYProgress, [0, 1], [-4, -12])
  return (
    <div ref={ref} className="relative h-[460px] sm:h-[540px] cohab-desktop:h-[620px]">
      <motion.img
        style={{ y: back }}
        src="/photos/friends-couch.webp"
        alt="A group of friends on a sofa in a shared flat"
        className="absolute right-0 top-0 w-[78%] h-[62%] object-cover rounded-[22px] border-[5px] border-white shadow-[var(--shadow-lift)]"
      />
      <motion.img
        style={{ y: mid }}
        src="/photos/cooking-together.webp"
        alt="Two flatmates cooking together"
        className="absolute left-0 bottom-0 w-[64%] h-[54%] object-cover rounded-[22px] border-[5px] border-white shadow-[var(--shadow-lift)] -rotate-2"
      />
      <motion.img
        style={{ y: front }}
        src="/photos/room-plants.webp"
        alt="A bright room with plants"
        className="absolute right-[4%] bottom-[2%] w-[30%] h-[30%] object-cover rounded-[18px] border-[5px] border-white shadow-[var(--shadow-lift)] rotate-3"
      />
      <motion.div
        style={{ y: card, rotate: cardTurn }}
        className="absolute left-[6%] top-[8%] bg-cohab-dark-bg text-white rounded-[20px] px-5 pt-3 pb-3 shadow-[0_14px_40px_-14px_rgba(0,0,0,.6)]"
      >
        <span className="label text-[10px] text-white/60 block">Compatibility</span>
        <span className="poster-num text-[76px] text-cohab-sun block">92</span>
        <span className="label text-[10px] text-cohab-sun">Strong both ways</span>
      </motion.div>
      <motion.div style={{ y: front }} className="absolute left-[38%] top-[56%]">
        <motion.div animate={{ y: [0, -8, 0] }} transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}>
          <Sticker className="relative bg-white text-cohab-on-sun rounded-bl-[4px] block">you’re up before 7?</Sticker>
        </motion.div>
        <motion.div animate={{ y: [0, -6, 0] }} transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 0.6 }}>
          <Sticker className="relative ml-10 mt-2 bg-cohab-sun text-cohab-on-sun rounded-bl-[4px] block">6:30. coffee’s on me</Sticker>
        </motion.div>
      </motion.div>
    </div>
  )
}

export function Landing() {
  return (
    <div className="min-h-screen bg-cohab-bg text-cohab-ink">
      <ScrollBar />
      {/* Top bar */}
      <header className="max-w-[1400px] mx-auto px-5 cohab-desktop:px-10 h-[72px] flex items-center gap-4">
        <Logo />
        <div className="flex-1" />
        <ThemeToggle iconOnly className="hidden sm:flex" />
        <Link to="/login" className="text-[14px] font-semibold underline-offset-4 hover:underline">
          Log in
        </Link>
        <Link
          to="/login?mode=signup"
          className="cohab-press h-11 px-5 rounded-full btn-ink text-[14px] font-bold inline-flex items-center"
        >
          Join free
        </Link>
      </header>

      {/* Hero */}
      <section className="max-w-[1400px] mx-auto px-5 cohab-desktop:px-10 pt-6 pb-16 cohab-desktop:pt-10 cohab-desktop:pb-24 grid cohab-desktop:grid-cols-[1.15fr_1fr] gap-10 cohab-desktop:gap-12 items-center">
        <div>
          <span className="label text-cohab-subtle">Roommate matching for verified students</span>
          <h1 className="poster text-[clamp(64px,9.2vw,138px)] mt-4">
            Find the one you can live with.
          </h1>
          <p className="text-[18px] cohab-desktop:text-[20px] leading-[1.45] text-cohab-muted mt-6 max-w-[34ch]">
            Rent and location are easy. Sleep, mess, guests and money are where flats fall apart. Cohab asks first.
          </p>
          <div className="flex flex-wrap items-center gap-3 mt-8">
            <Link
              to="/login?mode=signup"
              className="cohab-press h-14 pl-8 pr-6 rounded-full btn-ink text-[16px] font-bold inline-flex items-center gap-4"
            >
              Start in four minutes <ButtonArrow />
            </Link>
            <Link
              to="/study"
              className="cohab-press h-14 px-6 rounded-full border border-cohab-border bg-cohab-card shadow-[var(--shadow-soft)] text-[15px] font-bold inline-flex items-center"
            >
              Help with the research
            </Link>
          </div>
        </div>

        <HeroStack />
      </section>

      <Marquee />

      {/* How it works: three big rows, not a card grid */}
      <section className="max-w-[1400px] mx-auto px-5 cohab-desktop:px-10 py-16 cohab-desktop:py-24">
        <h2 className="poster text-[clamp(48px,7vw,104px)] max-w-[20ch]">Four minutes now. A year that works.</h2>
        <ol className="mt-12 border-t border-cohab-border">
          {STEPS.map((s, i) => (
            <li
              key={s.n}
              className={cn(
                'grid gap-6 cohab-desktop:gap-10 py-8 cohab-desktop:py-10 border-b border-cohab-border items-center',
                'cohab-desktop:grid-cols-[140px_1fr_380px]',
              )}
            >
              <span className="poster-num text-[84px] cohab-desktop:text-[120px]">{s.n}</span>
              <div>
                <h3 className="poster text-[34px] cohab-desktop:text-[48px]">{s.title}</h3>
                <p className="text-[16.5px] leading-[1.5] text-cohab-muted mt-3 max-w-[48ch]">{s.body}</p>
              </div>
              <img
                src={s.img}
                alt={s.alt}
                className={cn('w-full h-[220px] object-cover rounded-[22px] border-[5px] border-white shadow-[var(--shadow-lift)]', i % 2 ? 'rotate-1' : '-rotate-1')}
                loading="lazy"
              />
            </li>
          ))}
        </ol>
      </section>

      {/* The proof: chemistry chart */}
      <section className="bg-cohab-dark-bg text-white">
        <div className="max-w-[1400px] mx-auto px-5 cohab-desktop:px-10 py-16 cohab-desktop:py-24 grid cohab-desktop:grid-cols-[1fr_1.1fr] gap-12 items-center">
          <div>
            <span className="label text-cohab-sun">Every match, explained</span>
            <h2 className="poster text-white text-[clamp(48px,6.5vw,96px)] mt-4">Not a vibe. A reason.</h2>
            <p className="text-[17px] leading-[1.55] text-white/75 mt-6 max-w-[42ch]">
              Each habit is scored twice: how they suit you, and how you suit them. A match that only works for one of
              you sinks, because the lower side counts more. And every card tells you the one thing you’ll need to talk
              about.
            </p>
          </div>
          <div className="bg-[#161616] rounded-[22px] p-6 cohab-desktop:p-8 border border-white/10">
            <div className="flex items-end justify-between mb-6">
              <div>
                <span className="label text-white/50 text-[10px]">Example</span>
                <p className="poster text-white text-[40px] mt-1">You × Asha</p>
              </div>
              <span className="poster-num text-[64px] text-cohab-sun">86</span>
            </div>
            <Chemistry rows={DEMO} dark />
            <p className="mt-5 text-[14px] text-white/80 border-t border-white/10 pt-4">
              <span className="text-[#ff6a43] font-semibold">Worth talking about:</span> you say things straight away;
              Asha would rather let it go.
            </p>
          </div>
        </div>
      </section>

      {/* ML: learns your taste */}
      <section className="max-w-[1400px] mx-auto px-5 cohab-desktop:px-10 py-16 cohab-desktop:py-24 grid cohab-desktop:grid-cols-[1fr_1fr] gap-12 items-center">
        <div className="order-2 cohab-desktop:order-1 relative">
          <img
            src="/photos/students-table.webp"
            alt="A group of students working together around a laptop"
            className="w-full h-[420px] object-cover rounded-[22px] border-[5px] border-white shadow-[var(--shadow-lift)]"
            loading="lazy"
          />
          <div className="absolute -bottom-5 right-5 cohab-desktop:-right-6 surface rounded-[18px] px-5 py-4 max-w-[300px] shadow-[0_14px_40px_-16px_rgba(0,0,0,.45)]">
            <span className="label text-[10px] text-cohab-subtle">Learned from your choices</span>
            <p className="text-[14.5px] font-semibold leading-[1.35] mt-1.5">
              “You keep choosing people who fit you on tidiness, more than your answers said.”
            </p>
          </div>
        </div>
        <div className="order-1 cohab-desktop:order-2">
          <span className="label text-cohab-subtle">It learns</span>
          <h2 className="poster text-[clamp(48px,6.5vw,96px)] mt-4">Say yes. Say no. It gets you.</h2>
          <p className="text-[17px] leading-[1.55] text-cohab-muted mt-6 max-w-[44ch]">
            What you say matters and what you pick matters. Every interest and every pass teaches your list a little
            more, starting from your own answers and moving only as far as your choices justify. You can see exactly
            what it learned, and switch it off.
          </p>
          <div className="mt-8 flex items-baseline gap-4">
            <span className="poster-num text-[88px]">
              53<span className="text-[44px]">%</span>
            </span>
            <span className="poster text-[40px]">→</span>
            <span className="poster-num text-[88px] sun px-2 rounded-[10px]">
              67<span className="text-[44px]">%</span>
            </span>
          </div>
          <p className="text-[13px] text-cohab-subtle mt-2 max-w-[46ch]">
            Share of each person’s true top ten that their list shows, before learning and after about 45 decisions.
            Simulation with 150 synthetic members, not yet measured on real people.
          </p>
        </div>
      </section>

      {/* Safety on black */}
      <section className="bg-cohab-dark-bg text-white">
        <div className="max-w-[1400px] mx-auto px-5 cohab-desktop:px-10 py-16 cohab-desktop:py-24">
          <h2 className="poster text-white text-[clamp(52px,8vw,128px)] max-w-[16ch]">Your number stays yours.</h2>
          <div className="grid cohab-desktop:grid-cols-3 gap-px bg-white/15 mt-12 rounded-[22px] overflow-hidden">
            {[
              ['Verified only', 'Nobody sees you until their student email is confirmed. Nobody unverified appears in your list.'],
              ['Two yeses', 'Phone numbers are released only after you both agree, separately. Typing one into chat gets stopped.'],
              ['One tap out', 'Report or block from any match or chat. Reports are reviewed by a person before anything happens.'],
            ].map(([t, b]) => (
              <div key={t} className="bg-cohab-dark-bg p-7 cohab-desktop:p-9">
                <span className="inline-block w-4 h-4 rounded-[4px] bg-cohab-sun mb-6" />
                <h3 className="poster text-white text-[36px]">{t}</h3>
                <p className="text-[15.5px] leading-[1.55] text-white/70 mt-3">{b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Rooms strip + final CTA */}
      <section className="py-16 cohab-desktop:py-24 overflow-hidden">
        <div className="flex gap-4 px-5 cohab-desktop:px-10 pb-8 overflow-x-auto snap-x [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {['living-bright', 'bedroom-lights', 'balcony-plants', 'living-balcony', 'bedroom-warm', 'room-sunlight'].map((n, i) => (
            <img
              key={n}
              src={`/photos/${n}.webp`}
              alt=""
              loading="lazy"
              className={cn(
                'snap-start shrink-0 w-[240px] h-[300px] cohab-desktop:w-[300px] cohab-desktop:h-[380px] object-cover rounded-[22px] border-[5px] border-white shadow-[var(--shadow-lift)]',
                i % 2 ? 'translate-y-6' : '',
              )}
            />
          ))}
        </div>
        <div className="max-w-[1400px] mx-auto px-5 cohab-desktop:px-10 mt-20 text-center">
          <h2 className="poster text-[clamp(56px,10vw,156px)]">
            Ready? Four minutes.
          </h2>
          <Link
            to="/login?mode=signup"
            className="cohab-press mt-10 h-16 pl-10 pr-7 rounded-full btn-ink text-[18px] font-bold inline-flex items-center gap-5"
          >
            Find my roommate <ButtonArrow />
          </Link>
        </div>
      </section>

      <Roofline seed={3} className="block w-full h-[120px] cohab-desktop:h-[170px] -mb-px" />
      <footer className="border-t border-cohab-border">
        <div className="max-w-[1400px] mx-auto px-5 cohab-desktop:px-10 py-8 flex flex-wrap gap-x-6 gap-y-2 items-center text-[13px] text-cohab-subtle">
          <Logo pilot={false} />
          <span>A CHRIST University M.Sc. Data Science project.</span>
          <span>Cohab never handles rent, deposits or payments.</span>
          <div className="flex-1" />
          <Link to="/study" className="font-semibold text-cohab-ink hover:underline">
            Research study
          </Link>
          <Link to="/credits" className="font-semibold text-cohab-ink hover:underline">
            Photo credits
          </Link>
        </div>
      </footer>
    </div>
  )
}
