/** Mirrors cohab/api/schemas.py — kept in sync by hand, this project has no
 * OpenAPI codegen step. */

export type Gender = 'male' | 'female' | 'non_binary'
export type SeekerType = 'needs_place' | 'has_place'
export type GenderPreference = 'male' | 'female' | 'any'
export type PetTolerance = 'comfortable' | 'cannot_live_with_pets'
export type RoomType = 'private' | 'shared'

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
  gender: Gender
  seeker_type: SeekerType
  course?: string | null
  phone_number?: string | null
}

export interface RegisterResponse {
  user_id: string
}

export interface VerifyOtpRequest {
  user_id: string
  code: string
}

export interface ResendOtpRequest {
  email: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface UserOut {
  id: string
  email: string
  full_name: string
  gender: string
  seeker_type: string
  verification_status: string
  account_status: string
  course?: string | null
  avatar_url?: string | null
  phone_number?: string | null
  is_moderator: boolean
}

/** PATCH /auth/me — only the keys present are applied (D-13.9). An empty
 * string clears `phone_number`; omitting a key leaves it untouched. */
export interface AccountUpdateRequest {
  full_name?: string
  course?: string
  phone_number?: string
}

export interface ProfileUpsertRequest {
  city?: string
  budget_min: number
  budget_max: number
  move_in_date: string
  gender_preference?: GenderPreference
  severe_allergy?: string[]
  kitchen_allergens?: string[]
  has_pet?: boolean
  pet_tolerance?: PetTolerance
  smoking_dealbreaker?: boolean
  questionnaire: Record<string, unknown>
  important_attributes: string[]
}

export interface ProfileOut {
  city: string
  budget_min: number
  budget_max: number
  move_in_date: string
  gender_preference: string
  severe_allergy: string[]
  kitchen_allergens: string[]
  has_pet: boolean
  pet_tolerance: string
  smoking_dealbreaker: boolean
  questionnaire: Record<string, unknown>
  important_attributes: string[]
}

export interface ListingUpsertRequest {
  locality: string
  rent_per_person: number
  deposit: number
  room_type: RoomType
  available_from: string
  amenities: string[]
  photos: string[]
  current_housemates?: number
}

export interface ListingOut extends ListingUpsertRequest {}

export interface MatchListItem {
  match_id: string
  candidate_id: string
  candidate_name: string
  combined_score: number
  agreements: string[]
  divergence: string | null
  seeker_type: string
  city: string
  budget_min: number
  budget_max: number
  avatar_url: string | null
  state: string
  // Sent by the API (schemas.py::MatchListItem) but previously not declared
  // here, so the values arrived and were discarded. These back the Locality,
  // Room type and Move-in window filters (D-13.14). The three `listing_*`
  // fields are null for a needs_place candidate, who has no listing.
  course?: string | null
  move_in_date?: string | null
  listing_room_type?: string | null
  listing_available_from?: string | null
  listing_locality?: string | null
  // v2 taste learning: places this person moved because of your learned taste.
  taste_rank_change?: number | null
  // v2: present only while a calibration model is active (services/insights.py).
  would_message_probability?: number | null
  confidence_tier?: 'strong' | 'good' | 'possible' | null
  calibration_version?: number | null
  calibration_source?: string | null
}

export interface ExplanationCard {
  attribute: string
  kind: 'agreement' | 'divergence'
  text: string
  score: number
}

export interface MatchListingSummary {
  locality: string
  rent_per_person: number
  deposit: number
  room_type: string
  available_from: string
  amenities: string[]
  photos: string[]
}

export interface AttributeBreakdownCell {
  sim_a: number
  sim_b: number
}

export interface MatchExplanationResponse {
  match_id: string
  candidate_id: string
  candidate_name: string
  combined_score: number
  score_towards_candidate: number
  score_from_candidate: number
  breakdown: Record<string, AttributeBreakdownCell>
  agreements: ExplanationCard[]
  divergence: ExplanationCard | null
  state: string
  you_expressed_interest: boolean
  candidate_course?: string | null
  candidate_avatar_url?: string | null
  listing?: MatchListingSummary | null
}

export interface ExpressInterestResponse {
  state: string
}

// --- saved matches ------------------------------------------------------

export interface SavedMatchOut {
  saved_at: string
  match: MatchListItem
}

export interface UploadImageResponse {
  url: string
}

// --- chat -------------------------------------------------------------

export interface ChatMessage {
  id: string
  sender_id: string
  body: string
  created_at: string
  is_read: boolean
}

export interface SendMessageRequest {
  body: string
  confirm?: boolean
}

/** Shape of the 422 response body when a send is interrupted for PII
 * (cohab/api/chat.py: `{"detail": "pii_detected", "message": "..."}`). */
export interface PiiWarning {
  detail: 'pii_detected'
  message: string
}

export interface ContactStatus {
  you_consented: boolean
  other_consented: boolean
  other_phone: string | null
}

// --- reports & blocks ---------------------------------------------------

/** Mirrors cohab/models/safety.py REPORT_REASONS. */
export type ReportReason =
  | 'harassment'
  | 'threats'
  | 'sexual_harassment'
  | 'spam'
  | 'scam_or_fraud'
  | 'fake_profile'
  | 'inappropriate_behaviour'
  | 'other'

export interface ReportRequest {
  reported_user_id: string
  reason: ReportReason
  details?: string | null
}

export interface ReportOut {
  id: string
  status: string
  escalated: boolean
}

export interface BlockRequest {
  blocked_id: string
}

export interface BlockedUserOut {
  id: string
  full_name: string
  avatar_url: string | null
}

// --- moderation -----------------------------------------------------------

export type ReportSanction = 'warn' | 'suspend' | 'ban'

export interface ReportSummaryOut {
  id: string
  reporter_name: string
  reported_user_name: string
  reason: string
  status: string
  escalated: boolean
  created_at: string
}

export interface FlaggedMessageOut {
  id: string
  sender_id: string
  body: string
  created_at: string
}

export interface ReportDetailOut {
  id: string
  reporter_id: string
  reporter_name: string
  reported_user_id: string
  reported_user_name: string
  reason: string
  details: string | null
  status: string
  escalated: boolean
  resolution_note: string | null
  sanction: string | null
  created_at: string
  resolved_at: string | null
  evidence: FlaggedMessageOut[]
}

export interface ResolveReportRequest {
  finding: 'substantiated' | 'dismissed'
  sanction?: ReportSanction | null
  note?: string | null
}

// --- feedback (Phase 8) -----------------------------------------------

/** Mirrors cohab/models/feedback.py REJECTED_OUTCOMES/COHABITING_OUTCOMES.
 * Which subset is actually valid depends on the match's state — the server
 * is the source of truth for that, this union only rules out values never
 * valid for either. */
export type FeedbackOutcome = 'not_pursued' | 'incompatible' | 'other' | 'still_together' | 'moved_out'

export interface FeedbackRequest {
  outcome: FeedbackOutcome
  cohabitation_duration_days?: number | null
}

export interface FeedbackOut {
  id: string
  outcome: string
  cohabitation_duration_days: number | null
  submitted_at: string
}

export interface PendingFeedbackOut {
  match_id: string
  other_user_id: string
  other_user_name: string
  state: string
}

// --- analytics (Phase 8) -----------------------------------------------

export interface AnalyticsSummaryOut {
  members_by_verification_status: Record<string, number>
  members_by_account_status: Record<string, number>
  matches_by_state: Record<string, number>
  reports_by_status: Record<string, number>
}
