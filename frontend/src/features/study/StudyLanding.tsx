import { Link } from 'react-router-dom'
import { StudyShell } from './StudyShell'

/** Public entry to both v2 studies. Linked from posters and class groups;
 * needs no Cohab account. */
export function StudyLanding() {
  return (
    <StudyShell>
      <h1 className="poster text-[52px] cohab-desktop:text-[72px] mb-3 max-w-[16ch]">Help Cohab learn what makes roommates work</h1>
      <p className="text-[15px] leading-[1.6] text-cohab-muted max-w-[680px] mb-8">
        Cohab ranks possible roommates by how their habits fit together. Its weights came from published conflict
        statistics. These two short studies replace that guess with evidence from real people. Both are anonymous:
        no name, email, phone or account.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Link to="/study/lab" className="block surface rounded-[22px] p-5 hover:border-cohab-primary transition-colors cohab-lift">
          <p className="text-[12px] uppercase tracking-wide text-cohab-subtle mb-1">About 20 minutes · anyone</p>
          <h2 className="text-lg font-semibold mb-1.5">Cohab Lab</h2>
          <p className="text-[14px] text-cohab-muted">Compare pairs of made-up roommates and pick who you'd rather live with.</p>
        </Link>
        <Link to="/study/pair" className="block surface rounded-[22px] p-5 hover:border-cohab-primary transition-colors cohab-lift">
          <p className="text-[12px] uppercase tracking-wide text-cohab-subtle mb-1">About 10 minutes each · two roommates</p>
          <h2 className="text-lg font-semibold mb-1.5">Roommate pairs</h2>
          <p className="text-[14px] text-cohab-muted">You and someone you live with each answer separately about home life.</p>
        </Link>
      </div>
    </StudyShell>
  )
}
