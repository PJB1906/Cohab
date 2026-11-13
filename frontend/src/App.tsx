import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthPage } from '@/features/auth/AuthPage'
import { ListingForm } from '@/features/onboarding/ListingForm'
import { RequiredQuestionnaire } from '@/features/onboarding/RequiredQuestionnaire'
import { OptionalQuestionnaire } from '@/features/onboarding/OptionalQuestionnaire'
import { ImportanceWeights } from '@/features/onboarding/ImportanceWeights'
import { OnboardingProvider } from '@/features/onboarding/OnboardingContext'
import { MatchList } from '@/features/matches/MatchList'
import { MatchDetail } from '@/features/matches/MatchDetail'
import { SavedList } from '@/features/matches/SavedList'
import { ChatThread } from '@/features/chat/ChatThread'
import { ChatList } from '@/features/chat/ChatList'
import { ContactShare } from '@/features/chat/ContactShare'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { ModerationQueue } from '@/features/moderation/ModerationQueue'
import { ReportReview } from '@/features/moderation/ReportReview'
import { AnalyticsDashboard } from '@/features/analytics/AnalyticsDashboard'
import { BlockedUsers } from '@/features/safety/BlockedUsers'
import { EvidencePage } from '@/features/evidence/EvidencePage'
import { PlaygroundPage } from '@/features/evidence/Playground'
import { StudyLanding } from '@/features/study/StudyLanding'
import { LabFlow } from '@/features/study/LabFlow'
import { PairFlow } from '@/features/study/PairFlow'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { useSession } from '@/hooks/useSession'

function Onboarding({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <OnboardingProvider>{children}</OnboardingProvider>
    </ProtectedRoute>
  )
}

/** Phase 7 (docs/DECISIONS.md D-7.1): moderator auth is just an
 * `is_moderator` flag on the caller's own session — assumed already
 * resolved by the enclosing `ProtectedRoute`, so this only adds the
 * role check on top. */
function ModeratorGate({ children }: { children: React.ReactNode }) {
  const { data: user } = useSession()
  if (!user?.is_moderator) {
    return <Navigate to="/matches" replace />
  }
  return <>{children}</>
}

function Moderation({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <ModeratorGate>{children}</ModeratorGate>
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

      <Route path="/saved" element={<ProtectedRoute><SavedList /></ProtectedRoute>} />
      <Route path="/chats" element={<ProtectedRoute><ChatList /></ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />

      <Route path="/moderation" element={<Moderation><ModerationQueue /></Moderation>} />
      <Route path="/moderation/reports/:reportId" element={<Moderation><ReportReview /></Moderation>} />

      <Route path="/analytics" element={<Moderation><AnalyticsDashboard /></Moderation>} />
      <Route path="/evidence" element={<Moderation><EvidencePage /></Moderation>} />
      <Route path="/evidence/playground" element={<Moderation><PlaygroundPage /></Moderation>} />

      {/* v2 studies: public, anonymous, no product account (plan W2/W3). */}
      <Route path="/study" element={<StudyLanding />} />
      <Route path="/study/lab" element={<LabFlow />} />
      <Route path="/study/pair" element={<PairFlow />} />

      <Route path="/blocked" element={<ProtectedRoute><BlockedUsers /></ProtectedRoute>} />

      <Route path="/" element={<Navigate to="/matches" replace />} />
      <Route path="*" element={<Navigate to="/matches" replace />} />
    </Routes>
  )
}
