/** Third-person wording for Cohab Lab cards. A card describes how another
 * person lives (behaviour fields only: cohab/services/study/instrument.py
 * CARD_FIELDS), so each first-person questionnaire option is restated about
 * "them". Option codes are identical to data/questionnaire.ts. */

export const CARD_ROWS: { field: string; heading: string; text: Record<string, string> }[] = [
  {
    field: 'cleanliness_level',
    heading: 'Tidiness',
    text: { very_tidy: 'Cleans daily, everything put away', moderate: 'Tidies up every few days', relaxed: 'Cleans when it needs it' },
  },
  {
    field: 'chore_approach',
    heading: 'Chores',
    text: {
      rota: 'Wants a fixed rota',
      shared: 'Shares fairly, no schedule',
      hired: 'Prefers hired help, cost split',
      own_mess: 'Cleans up after themselves only',
    },
  },
  {
    field: 'sharing_norm',
    heading: 'Sharing things',
    text: { communal: 'Mostly shared, help yourself', ask_first: 'Asks before using things', separate: 'Keeps their things separate' },
  },
  {
    field: 'sleep_schedule',
    heading: 'Sleep',
    text: { early: 'Asleep before 11pm', regular: 'Asleep 11pm – 1am', night_owl: 'Asleep after 1am', varies: 'Sleep time varies a lot' },
  },
  {
    field: 'noise_behaviour',
    heading: 'Noise',
    text: { quiet: 'Quiet at home', moderate: 'Occasional calls or music', loud: 'Music, calls, friends over' },
  },
  {
    field: 'guest_frequency',
    heading: 'Guests',
    text: { rarely: 'Rarely has guests', occasionally: 'Guests a few times a month', often: 'Guests weekly or more', partner_regular: 'Partner stays over regularly' },
  },
  {
    field: 'payment_reliability',
    heading: 'Rent and bills',
    text: { early: "Always pays before it's due", on_time: 'Pays on time', needs_grace: 'Sometimes needs a few days', needs_reminding: 'Needs reminding to pay' },
  },
  {
    field: 'cost_split_preference',
    heading: 'Splitting costs',
    text: { equal: 'Wants everything split equally', by_room: 'Wants split by room', by_use: 'Wants split by use', flexible: 'Happy either way' },
  },
  {
    field: 'communication_style',
    heading: 'If something bothers them',
    text: { direct_now: 'Says it directly, straight away', calm_later: 'Raises it calmly later', message: 'Messages rather than talks', let_go: 'Usually lets it go' },
  },
  {
    field: 'diet',
    heading: 'Diet',
    text: { veg: 'Vegetarian', nonveg: 'Non-vegetarian', eggetarian: 'Eggetarian', vegan: 'Vegan', jain: 'Jain' },
  },
  {
    field: 'smoking_behaviour',
    heading: 'Smoking',
    text: { none: "Doesn't smoke", outside: 'Smokes, outside only', indoors: 'Smokes indoors' },
  },
  {
    field: 'alcohol_behaviour',
    heading: 'Alcohol',
    text: { none: "Doesn't drink", outside: 'Drinks, not at home', indoors: 'Drinks at home' },
  },
  {
    field: 'life_stage',
    heading: 'Right now',
    text: { coursework: 'Coursework and classes', exam_prep: 'Preparing for a competitive exam', job: 'Working or interning', building: 'Building their own thing', research: 'Research or thesis' },
  },
  {
    field: 'daytime_presence',
    heading: 'Weekdays',
    text: { out: 'Out most of the day', partly: 'Home part of the day', home: 'Home most of the day' },
  },
  {
    field: 'home_orientation',
    heading: 'Time at home',
    text: { homebody: 'A homebody', balanced: 'Balanced', rarely: 'Barely home' },
  },
  {
    field: 'sociability',
    heading: 'Wants from a flatmate',
    text: { friend: 'Someone to spend time with', friendly: 'Friendly, separate lives', independent: 'Polite and independent' },
  },
]

/** Gameable items for the roommate-pair form: "how would your roommate
 * describe you?" asked the other way round. */
export const ROOMMATE_RATING_FIELDS = ['cleanliness_level', 'payment_reliability', 'noise_behaviour', 'guest_frequency', 'chore_approach']
