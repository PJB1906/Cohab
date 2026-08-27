import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
})

// iOS Safari only evaluates `:active` CSS when it detects the page wants
// touch feedback, which it infers from a touch listener existing anywhere
// on the page. Without one, every `.cohab-press` tap-scale (index.css) —
// baked into every Button — silently never fires on iOS. A known WebKit
// quirk, not a CSS bug; `passive: true` keeps this from affecting scroll.
document.addEventListener('touchstart', () => {}, { passive: true })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
