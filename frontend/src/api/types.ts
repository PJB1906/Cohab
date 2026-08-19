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
