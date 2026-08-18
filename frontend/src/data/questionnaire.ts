/** Verbatim from COHAB_MATCHING_SPEC.md §3 (Q1–Q18) — question text, option
 * codes and labels, and the spec's own blockquote commentary (used as the
 * `sub` line where the spec provides one; `null` where it doesn't, rather
 * than inventing connective copy — docs/DECISIONS.md D-5.1).
 *
 * The alcohol sub-question (part of Q12) has no spec-given labels — the spec
 * only says "same structure for alcohol", and `matrices.py`'s `alcohol`
 * tolerance matrix already reuses smoking's exact option codes. The labels
 * below are proposed, parallel wording for those same codes applied to
 * drinking rather than smoking (docs/DECISIONS.md D-5.1, item 4).
 */

export interface QuestionOption {
  value: string
  label: string
}

export interface QuestionPart {
  key: string
  label: string | null
  options: QuestionOption[]
}

export interface Question {
  id: string
  theme: string
  title: string
  sub: string | null
  parts: QuestionPart[]
}

export const REQUIRED_QUESTIONS: Question[] = [
  {
    id: 'q1',
    theme: 'Sleep',
    title: 'When do you usually go to sleep?',
    sub: null,
    parts: [
      {
        key: 'sleep_schedule',
        label: null,
        options: [
          { value: 'early', label: 'Before 11pm' },
          { value: 'regular', label: '11pm – 1am' },
          { value: 'night_owl', label: 'After 1am' },
          { value: 'varies', label: 'It varies a lot' },
        ],
      },
    ],
  },
  {
    id: 'q2',
    theme: 'Noise',
    title: 'Noise expectation at home',
    sub: "Noise generates more residence-hall mediation than any other single issue, which is why it is asked separately from sleep schedule rather than inferred from it. Two night owls can still conflict if one works in silence and the other takes 1am calls.",
    parts: [
      {
        key: 'noise_preference',
        label: 'What you need',
        options: [
          { value: 'strict', label: 'Quiet after 10pm' },
          { value: 'moderate', label: 'Quiet after midnight' },
          { value: 'flexible', label: 'Noise rarely bothers me' },
        ],
      },
      {
        key: 'noise_behaviour',
        label: 'What you do',
        options: [
          { value: 'quiet', label: "I'm quiet at home" },
          { value: 'moderate', label: 'Normal, occasional calls or music' },
          { value: 'loud', label: 'Music, calls, friends over' },
        ],
      },
    ],
  },
  {
    id: 'q3',
    theme: 'Cleanliness',
    title: 'How tidy do you keep shared spaces?',
    sub: null,
    parts: [
      {
        key: 'cleanliness_level',
        label: null,
        options: [
          { value: 'very_tidy', label: 'Cleaned daily, everything put away' },
          { value: 'moderate', label: 'Tidy up every few days' },
          { value: 'relaxed', label: 'Clean when it needs it' },
        ],
      },
    ],
  },
  {
    id: 'q4',
    theme: 'Chores',
    title: 'How should cleaning get done?',
    sub: 'Asked separately from cleanliness standard because two people can share a cleanliness standard and still fight bitterly about who does the work.',
    parts: [
      {
        key: 'chore_approach',
        label: null,
        options: [
          { value: 'rota', label: 'Fixed rota, everyone knows their job' },
          { value: 'shared', label: 'Share fairly, no formal schedule' },
          { value: 'hired', label: 'Hire help and split the cost' },
          { value: 'own_mess', label: 'Everyone cleans up after themselves only' },
        ],
      },
    ],
  },
  {
    id: 'q5',
    theme: 'Sharing',
    title: 'How do you treat things in a shared flat?',
    sub: 'Sharing food and belongings accounts for roughly 27% of reported disputes, and is independent of cleanliness and chores: a person can keep shared spaces spotless, follow the rota, pay early, and still finish your milk.',
    parts: [
      {
        key: 'sharing_norm',
        label: null,
        options: [
          { value: 'communal', label: 'Mostly shared — help yourself' },
          { value: 'ask_first', label: 'Ask before using my things' },
          { value: 'separate', label: 'I keep my things separate' },
        ],
      },
    ],
  },
  {
    id: 'q6',
    theme: 'Guests',
    title: 'How often do you have guests over?',
    sub: null,
    parts: [
      {
        key: 'guest_frequency',
        label: null,
        options: [
          { value: 'rarely', label: 'Rarely' },
          { value: 'occasionally', label: 'A few times a month' },
          { value: 'often', label: 'Weekly or more' },
          { value: 'partner_regular', label: 'A partner stays over regularly' },
        ],
      },
    ],
  },
  {
    id: 'q7',
    theme: 'Guests',
    title: "How do you feel about a roommate's guests?",
    sub: 'This and the previous question form a pair. Guests appear in roughly a third of reported conflicts — the friction is one person’s frequency against the other’s comfort, not the similarity of their habits.',
    parts: [
      {
        key: 'guest_tolerance',
        label: null,
        options: [
          { value: 'anytime', label: 'Fine anytime' },
          { value: 'with_notice', label: 'Fine with notice' },
          { value: 'weekends', label: 'Weekends only' },
          { value: 'prefer_none', label: "I'd rather not" },
        ],
      },
    ],
  },
  {
    id: 'q8',
    theme: 'Communication',
    title: 'If something bothered you at home, what would you do?',
    sub: 'The roommate-breakup literature finds communication style among the strongest predictors of people actually ending the arrangement — stronger than lifestyle logistics.',
    parts: [
      {
        key: 'communication_style',
        label: null,
        options: [
          { value: 'direct_now', label: 'Say it directly, straight away' },
          { value: 'calm_later', label: 'Bring it up calmly at a good moment' },
          { value: 'message', label: 'Message rather than talk face to face' },
          { value: 'let_go', label: 'Usually let it go' },
        ],
      },
    ],
  },
  {
    id: 'q9',
    theme: 'Money',
    title: 'How do you handle your share of rent and bills?',
    sub: 'Over 20% of renters call non-payment immediately terminable, and 22% report financial arguments — nobody wants a match on shared unreliability, so this is scored on your answer alone.',
    parts: [
      {
        key: 'payment_reliability',
        label: null,
        options: [
          { value: 'early', label: "Always before it's due" },
          { value: 'on_time', label: 'On time' },
          { value: 'needs_grace', label: 'Sometimes need a few days' },
          { value: 'needs_reminding', label: "I'd rather someone reminded me" },
        ],
      },
    ],
  },
  {
    id: 'q10',
    theme: 'Money',
    title: 'How should rent and bills be divided?',
    sub: 'A different argument from when you pay. Two people who both pay early can still deadlock over whether the smaller bedroom pays less.',
    parts: [
      {
        key: 'cost_split_preference',
        label: null,
        options: [
          { value: 'equal', label: 'Everything split equally' },
          { value: 'by_room', label: 'By room size or what each room has' },
          { value: 'by_use', label: 'By what each person actually uses' },
          { value: 'flexible', label: 'Happy either way' },
        ],
      },
    ],
  },
  {
    id: 'q11',
    theme: 'Kitchen',
    title: 'Diet and the shared kitchen',
    sub: 'Diet is scored, never filtered. The kitchen-tolerance question below captures the genuine practical friction without the proxy effect.',
    parts: [
      {
        key: 'diet',
        label: 'Your diet',
        options: [
          { value: 'veg', label: 'Vegetarian' },
          { value: 'nonveg', label: 'Non-vegetarian' },
          { value: 'eggetarian', label: 'Eggetarian' },
          { value: 'vegan', label: 'Vegan' },
          { value: 'jain', label: 'Jain' },
        ],
      },
      {
        key: 'nonveg_cooking_tolerance',
        label: 'Non-vegetarian cooking in a shared kitchen',
        options: [
          { value: 'fine', label: 'No problem' },
          { value: 'prefer_not', label: "I'd prefer not" },
          { value: 'not_at_all', label: 'Not at all' },
        ],
      },
    ],
  },
  {
    id: 'q12',
    theme: 'Habits',
    title: 'Smoking and alcohol',
    sub: null,
    parts: [
      {
        key: 'smoking_behaviour',
        label: 'You — smoking',
        options: [
          { value: 'none', label: "Don't smoke" },
          { value: 'outside', label: 'Smoke, outside only' },
          { value: 'indoors', label: 'Smoke indoors' },
        ],
      },
      {
        key: 'smoking_tolerance',
        label: 'A roommate who smokes',
        options: [
          { value: 'fine', label: 'Fine' },
          { value: 'outside_ok', label: 'Outside only' },
          { value: 'smoke_free', label: 'I want a smoke-free home' },
        ],
      },
      // Proposed labels (spec §3: "same structure for alcohol"; codes are
      // matrices.py's existing `alcohol` matrix, reused as-is).
      {
        key: 'alcohol_behaviour',
        label: 'You — alcohol',
        options: [
          { value: 'none', label: "Don't drink" },
          { value: 'outside', label: "Drink, but not at home" },
          { value: 'indoors', label: 'Drink at home' },
        ],
      },
      {
        key: 'alcohol_tolerance',
        label: 'A roommate who drinks',
        options: [
          { value: 'fine', label: 'Fine' },
          { value: 'outside_ok', label: 'Only outside the home' },
          { value: 'smoke_free', label: 'I want an alcohol-free home' },
        ],
      },
    ],
  },
]

export const OPTIONAL_TIER2_QUESTIONS: Question[] = [
  {
    id: 'q13',
    theme: 'Life stage',
    title: 'What are you working towards right now?',
    sub: 'Not about shared ambition. Aspiration is a proxy for daily rhythm, and rhythm is what creates friction — "night owl" alone doesn’t distinguish someone who games late from someone who works late and resents noise at 9am.',
    parts: [
      {
        key: 'life_stage',
        label: null,
        options: [
          { value: 'coursework', label: 'Coursework and classes' },
          { value: 'exam_prep', label: 'Competitive exam preparation' },
          { value: 'job', label: 'Working or interning' },
          { value: 'building', label: 'Building something of my own' },
          { value: 'research', label: 'Research or thesis' },
        ],
      },
    ],
  },
  {
    id: 'q14',
    theme: 'Life stage',
    title: 'Typical weekday',
    sub: null,
    parts: [
      {
        key: 'daytime_presence',
        label: null,
        options: [
          { value: 'out', label: 'Out most of the day' },
          { value: 'partly', label: 'Home part of the day' },
          { value: 'home', label: 'Home most of the day' },
        ],
      },
    ],
  },
  {
    id: 'q15',
    theme: 'Life stage',
    title: 'Time at home',
    sub: null,
    parts: [
      {
        key: 'home_orientation',
        label: null,
        options: [
          { value: 'homebody', label: "I'm a homebody" },
          { value: 'balanced', label: 'Balanced' },
          { value: 'rarely', label: "I'm barely home" },
        ],
      },
    ],
  },
  {
    id: 'q16',
    theme: 'Life stage',
    title: 'What do you want from a flatmate?',
    sub: 'This asks what you want to happen while you’re home, not how much you’re home — whoever wants company reads distance as rejection, and whoever wants independence reads warmth as intrusion.',
    parts: [
      {
        key: 'sociability',
        label: null,
        options: [
          { value: 'friend', label: "Someone I'd spend time with" },
          { value: 'friendly', label: 'Friendly, but we live our own lives' },
          { value: 'independent', label: 'Polite and independent' },
        ],
      },
    ],
  },
]

export const INTEREST_TAGS: QuestionOption[] = [
  { value: 'sports', label: 'Sports and fitness' },
  { value: 'music', label: 'Music' },
  { value: 'gaming', label: 'Gaming' },
  { value: 'cooking', label: 'Cooking' },
  { value: 'reading', label: 'Reading' },
  { value: 'film', label: 'Film and series' },
  { value: 'travel', label: 'Travel' },
  { value: 'art', label: 'Art and design' },
  { value: 'tech', label: 'Technology' },
  { value: 'volunteering', label: 'Volunteering' },
  { value: 'photo', label: 'Photography' },
  { value: 'outdoors', label: 'Outdoors' },
]

export const LIFESTYLE_NOTES_PROMPT =
  'What are you working towards, and what do you do outside it? What kind of home do you want to come back to?'

export interface WeightTileDef {
  id: string
  title: string
  sub: string
}

/** Tiles for screen 6 ("pick the three that matter most to you", spec §3).
 * Ids are real `weight_set` attribute names (attributes.py's ATTRIBUTES
 * registry) — every id here is a value `PUT /profile` will accept. Covers
 * all of Tier 1 except `budget_proximity` (already enforced as a hard
 * constraint, not a meaningful "priority" to weight) plus `life_stage` and
 * `sociability` from Tier 2. docs/DECISIONS.md D-5.4. */
export const WEIGHT_TILES: WeightTileDef[] = [
  { id: 'cleanliness_level', title: 'Cleanliness', sub: 'Tidiness of shared space' },
  { id: 'sleep_schedule', title: 'Sleep schedule', sub: 'When you wind down and wake up' },
  { id: 'noise', title: 'Noise', sub: 'Quiet hours, calls, music' },
  { id: 'guests', title: 'Guests', sub: 'Who comes over, how often' },
  { id: 'payment_reliability', title: 'Paying on time', sub: 'Rent and bills when due' },
  { id: 'sharing_norm', title: 'Sharing things', sub: 'Food, belongings, borrowing' },
  { id: 'chore_approach', title: 'Chore approach', sub: 'Rota, split, hired help' },
  { id: 'communication_style', title: 'Communication', sub: 'How problems get raised' },
  { id: 'cost_split_preference', title: 'Splitting costs', sub: 'Equal, by room, by use' },
  { id: 'diet', title: 'Diet and kitchen', sub: 'What gets cooked at home' },
  { id: 'nonveg_cooking', title: 'Non-veg cooking', sub: 'In a shared kitchen' },
  { id: 'smoking', title: 'Smoking', sub: 'Inside the flat' },
  { id: 'alcohol', title: 'Alcohol', sub: 'Inside the flat' },
  { id: 'life_stage', title: 'Life stage', sub: 'Exams, work, research rhythm' },
  { id: 'sociability', title: 'Sociability', sub: 'Flatmate or friend' },
]

export const REQUIRED_QUESTIONNAIRE_KEYS: string[] = REQUIRED_QUESTIONS.flatMap((q) =>
  q.parts.map((p) => p.key),
)
