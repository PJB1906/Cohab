import { useNavigate } from 'react-router-dom'

const NO_BACK_ROUTES = new Set(['/matches', '/login'])

/** Browser-history back, top-left of the shell. Hidden on the app's root
 * screens (the main match list, the login/signup screen) where there's
 * nothing meaningful to go back to. */
export function BackButton({ pathname }: { pathname: string }) {
  const navigate = useNavigate()

  if (NO_BACK_ROUTES.has(pathname)) return null

  return (
    <button
      type="button"
      onClick={() => navigate(-1)}
      aria-label="Back"
      className="cohab-press flex items-center justify-center w-8 h-8 -ml-1.5 rounded-full text-cohab-ink hover:bg-cohab-tint transition-colors"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M15 18l-6-6 6-6" />
      </svg>
    </button>
  )
}
