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
