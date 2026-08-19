import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthPage } from '@/features/auth/AuthPage'
import { ListingForm } from '@/features/onboarding/ListingForm'
import { RequiredQuestionnaire } from '@/features/onboarding/RequiredQuestionnaire'
import { OptionalQuestionnaire } from '@/features/onboarding/OptionalQuestionnaire'
import { ImportanceWeights } from '@/features/onboarding/ImportanceWeights'
import { OnboardingProvider } from '@/features/onboarding/OnboardingContext'
import { MatchList } from '@/features/matches/MatchList'
import { MatchDetail } from '@/features/matches/MatchDetail'
import { ChatThread } from '@/features/chat/ChatThread'
import { ContactShare } from '@/features/chat/ContactShare'
import { ProtectedRoute } from '@/components/ProtectedRoute'

function Onboarding({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <OnboardingProvider>{children}</OnboardingProvider>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />

      <Route path="/onboarding/listing" element={<Onboarding><ListingForm /></Onboarding>} />
      <Route path="/onboarding/questionnaire" element={<Onboarding><RequiredQuestionnaire /></Onboarding>} />
      <Route path="/onboarding/optional" element={<Onboarding><OptionalQuestionnaire /></Onboarding>} />
      <Route path="/onboarding/weights" element={<Onboarding><ImportanceWeights /></Onboarding>} />

      <Route path="/matches" element={<ProtectedRoute><MatchList /></ProtectedRoute>} />
      <Route path="/matches/:matchId" element={<ProtectedRoute><MatchDetail /></ProtectedRoute>} />
      <Route path="/matches/:matchId/chat" element={<ProtectedRoute><ChatThread /></ProtectedRoute>} />
      <Route path="/matches/:matchId/contact-share" element={<ProtectedRoute><ContactShare /></ProtectedRoute>} />

      <Route path="/" element={<Navigate to="/matches" replace />} />
      <Route path="*" element={<Navigate to="/matches" replace />} />
    </Routes>
  )
}
