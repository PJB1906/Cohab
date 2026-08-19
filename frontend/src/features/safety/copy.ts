import type { ReportReason } from '@/api/types'

/** Mirrors cohab/models/safety.py REPORT_REASONS / REPORT_STATUSES. Shared
 * between the report-filing dialog and the moderator queue so the display
 * copy can't drift between the two. */
export const REASON_OPTIONS: { value: ReportReason; label: string }[] = [
  { value: 'harassment', label: 'Harassment' },
  { value: 'threats', label: 'Threats' },
  { value: 'sexual_harassment', label: 'Sexual harassment' },
  { value: 'inappropriate_behaviour', label: 'Inappropriate behaviour' },
  { value: 'fake_profile', label: 'Fake profile' },
  { value: 'scam_or_fraud', label: 'Scam or fraud' },
  { value: 'spam', label: 'Spam' },
  { value: 'other', label: 'Something else' },
]

export const REASON_LABELS: Record<string, string> = Object.fromEntries(
  REASON_OPTIONS.map((r) => [r.value, r.label]),
)

export const STATUS_LABELS: Record<string, string> = {
  open: 'Open',
  under_review: 'Under review',
  substantiated: 'Substantiated',
  dismissed: 'Dismissed',
  action_taken: 'Action taken',
}
