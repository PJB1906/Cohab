import { Component, type ErrorInfo, type ReactNode } from 'react'

/** Last line of defence: a render error anywhere below this used to unmount
 * the whole app and leave a blank page (React's default without a
 * boundary). Show a plain message and a way back instead. The technical
 * detail goes to the console for whoever is debugging, never to the user. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Cohab render error:', error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="min-h-dvh flex items-center justify-center bg-cohab-bg text-cohab-ink px-6">
        <div className="max-w-[420px] text-center">
          <h1 className="text-xl font-semibold mb-2">Something went wrong on this screen</h1>
          <p className="text-[14px] leading-[1.55] text-cohab-muted mb-5">
            Nothing you entered elsewhere was lost. Reload to try again, or go back to your matches.
          </p>
          <div className="flex justify-center gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="cohab-press btn-raised h-11 px-6 rounded-full bg-cohab-fill text-cohab-on-fill text-[14px] font-bold cursor-pointer"
            >
              Reload
            </button>
            <a
              href="/matches"
              className="h-11 px-5 rounded-xl border border-cohab-border text-[14px] font-medium inline-flex items-center"
            >
              Go to matches
            </a>
          </div>
        </div>
      </div>
    )
  }
}
