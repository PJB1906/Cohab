"""Figure 7.1 - Class Diagram (revised: no false chain, closed weight loop)."""
from gvutil import uml_class, render

CORE = "#DCE9F7"
MATCH = "#FDEBD0"
SUPPORT = "#E8F6EF"
GOV = "#F4E3F7"

CLASSES = [
    ("AuthService", [
        "- user_id: int", "- institutional_email: str",
        "- verification_status: str",
    ], [
        "+ register(): bool", "+ verify_identity(): bool",
        "+ authenticate(): bool", "+ issue_session_token(): str",
    ], CORE),

    ("PreferenceService", [
        "- user_id: int", "- profile: dict", "- importance_weights: dict",
    ], [
        "+ save_profile(): bool", "+ get_profile(): dict",
        "+ encode_lifestyle_notes(): vector",
    ], CORE),

    ("EligibilityFilter", [
        "- hard_constraints: dict",
    ], [
        "+ filter_candidates(): list", "+ is_eligible(): bool",
        "+ explain_exclusion(): str",
    ], MATCH),

    ("WeightRegistry", [
        "- active_set: WeightSet", "- version: int",
    ], [
        "+ get_active_weights(): dict", "+ get_weights_for(score_id): dict",
        "+ publish_weight_set(): int",
    ], MATCH),

    ("CompatibilityMatcher", [
        "- profile_a: dict", "- profile_b: dict", "- weights: dict",
    ], [
        "+ compute_directional_score(): float",
        "+ compute_combined_score(): float",
        "+ compute_attribute_breakdown(): dict",
    ], MATCH),

    ("MatchRanker", [
        "- scores: list", "- exploration_rate: float",
    ], [
        "+ rank_matches(): list", "+ generate_explanation(): str",
    ], MATCH),

    ("ChatService", [
        "- match_id: int", "- sender_id: int", "- content: str",
    ], [
        "+ send_message(): bool", "+ get_thread(): list",
        "+ flag_message(): bool",
    ], SUPPORT),

    ("SafetyReportService", [
        "- report_id: int", "- reporter_id: int", "- reported_id: int",
        "- reason: str",
    ], [
        "+ file_report(): bool", "+ review_report(): str",
        "+ block_user(): bool",
    ], SUPPORT),

    ("NotificationService", [
        "- channel: str",
    ], [
        "+ send_match_alert(): bool", "+ send_report_update(): bool",
        "+ send_offline_digest(): bool",
    ], SUPPORT),

    ("FeedbackEngine", [
        "- match_outcomes: list",
    ], [
        "+ log_outcome(): bool", "+ recompute_weights(): dict",
    ], MATCH),

    ("AnalyticsService", [
        "- institution_id: int",
    ], [
        "+ generate_usage_report(): dict",
        "+ generate_match_success_report(): dict",
    ], SUPPORT),

    ("ConsentService", [
        "- policy_version: str",
    ], [
        "+ record_consent(): bool", "+ withdraw_consent(): bool",
        "+ erase_user_data(): bool",
    ], GOV),
]

# (from, to, label, style)
EDGES = [
    ("AuthService", "PreferenceService", "verified user", "solid"),
    ("AuthService", "ConsentService", "records consent", "solid"),
    ("PreferenceService", "EligibilityFilter", "profile +\\nhard constraints",
     "solid"),
    ("EligibilityFilter", "CompatibilityMatcher", "eligible pool", "solid"),
    ("WeightRegistry", "CompatibilityMatcher", "active weights", "dashed"),
    ("PreferenceService", "CompatibilityMatcher", "importance weights",
     "dashed"),
    ("CompatibilityMatcher", "MatchRanker", "scores +\\nbreakdown", "solid"),
    ("MatchRanker", "ChatService", "selected match", "solid"),
    ("MatchRanker", "FeedbackEngine", "shown / pursued\\noutcomes", "solid"),
    ("FeedbackEngine", "WeightRegistry", "publishes new\\nweight set",
     "solid"),
    ("FeedbackEngine", "AnalyticsService", "aggregated outcomes", "solid"),
    ("ChatService", "SafetyReportService", "flagged content", "solid"),
    ("ChatService", "NotificationService", "offline alert", "dashed"),
    ("SafetyReportService", "NotificationService", "report status", "dashed"),
    ("ConsentService", "SafetyReportService", "erasure /\\nsuspension",
     "dashed"),
]

lines = [
    "digraph ClassDiagram {",
    '  rankdir=TB; bgcolor="white"; splines=spline;',
    '  node [fontname="Helvetica", fontsize=10];',
    '  edge [fontname="Helvetica", fontsize=8, color="#4A4A4A", '
    'arrowsize=0.75, penwidth=1.1];',
    "  nodesep=0.55; ranksep=0.65;",
    "",
]

for name, attrs, methods, fill in CLASSES:
    lines.append(uml_class(name, attrs, methods, fill=fill))

lines.append("")
for src, dst, lbl, style in EDGES:
    lines.append(f'  "{src}" -> "{dst}" [label="{lbl}", style={style}];')

lines += [
    "",
    '  {rank=same; "EligibilityFilter"; "WeightRegistry";}',
    '  {rank=same; "ChatService"; "FeedbackEngine";}',
    '  {rank=same; "SafetyReportService"; "AnalyticsService";}',
    "}",
]

render("\n".join(lines), "../images/image8.png", dpi=150)
print(f"Class diagram: {len(CLASSES)} classes, {len(EDGES)} relationships")
