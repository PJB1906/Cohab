"""Figure 6.1 - Entity Relationship Diagram (revised)."""
from gvutil import er_entity, render

ENTITIES = [
    ("INSTITUTION", [
        ("institution_id (PK)", "pk"), ("name", ""), ("type", ""),
        ("contact_email", ""),
    ]),
    ("MODERATOR", [
        ("moderator_id (PK)", "pk"), ("name", ""), ("email", ""),
        ("role", ""), ("institution_id (FK)", "fk"),
    ]),
    ("USER", [
        ("user_id (PK)", "pk"), ("institutional_email", ""), ("name", ""),
        ("phone", ""), ("verification_status", ""), ("account_status", ""),
        ("institution_id (FK)", "fk"), ("created_at", ""),
    ]),
    ("VERIFICATION_RECORD", [
        ("verification_id (PK)", "pk"), ("user_id (FK)", "fk"),
        ("id_document_type", ""), ("id_document_ref", ""),
        ("verified_by (FK)", "fk"), ("verified_at", ""),
        ("document_purge_at", ""),
    ]),
    ("CONSENT_RECORD", [
        ("consent_id (PK)", "pk"), ("user_id (FK)", "fk"), ("purpose", ""),
        ("policy_version", ""), ("granted", ""), ("granted_at", ""),
        ("withdrawn_at", ""),
    ]),
    ("PREFERENCE_PROFILE", [
        ("profile_id (PK)", "pk"), ("user_id (FK)", "fk"),
        ("profile_doc_id", ""), ("sleep_schedule", ""),
        ("cleanliness_level", ""), ("social_habits", ""),
        ("budget_min", ""), ("budget_max", ""), ("city", ""),
        ("locality_preference", ""), ("food_preference", ""),
        ("smoking", ""), ("pets", ""), ("gender_preference", ""),
        ("move_in_date", ""), ("lease_duration_months", ""),
        ("lifestyle_notes", ""), ("embedding_ref", ""), ("updated_at", ""),
    ]),
    ("USER_ATTRIBUTE_WEIGHT", [
        ("user_weight_id (PK)", "pk"), ("user_id (FK)", "fk"),
        ("attribute", ""), ("importance", ""),
    ]),
    ("WEIGHT_SET", [
        ("weight_set_id (PK)", "pk"), ("version", ""), ("weights_json", ""),
        ("source", ""), ("feedback_count", ""), ("effective_from", ""),
        ("effective_to", ""),
    ]),
    ("MATCH_SCORE", [
        ("score_id (PK)", "pk"), ("user_id_a (FK)", "fk"),
        ("user_id_b (FK)", "fk"), ("weight_set_id (FK)", "fk"),
        ("score_a_to_b", ""), ("score_b_to_a", ""), ("combined_score", ""),
        ("attribute_breakdown", ""), ("status", ""), ("created_at", ""),
    ]),
    ("MESSAGE", [
        ("message_id (PK)", "pk"), ("score_id (FK)", "fk"),
        ("sender_id (FK)", "fk"), ("content_encrypted", ""),
        ("moderation_flag", ""), ("is_read", ""), ("sent_at", ""),
    ]),
    ("CONTACT_SHARE", [
        ("share_id (PK)", "pk"), ("score_id (FK)", "fk"),
        ("user_id (FK)", "fk"), ("consented_at", ""),
    ]),
    ("FEEDBACK", [
        ("feedback_id (PK)", "pk"), ("score_id (FK)", "fk"),
        ("submitted_by (FK)", "fk"), ("outcome", ""),
        ("cohabitation_days", ""), ("submitted_at", ""),
    ]),
    ("REPORT", [
        ("report_id (PK)", "pk"), ("reporter_id (FK)", "fk"),
        ("reported_id (FK)", "fk"), ("reason", ""), ("details", ""),
        ("status", ""), ("reviewed_by (FK)", "fk"), ("reviewed_at", ""),
    ]),
    ("USER_BLOCK", [
        ("block_id (PK)", "pk"), ("blocker_id (FK)", "fk"),
        ("blocked_id (FK)", "fk"), ("created_at", ""),
    ]),
]

# (from, to, tail_card, head_card, label)
RELS = [
    ("INSTITUTION", "USER", "1", "N", "affiliates"),
    ("INSTITUTION", "MODERATOR", "1", "N", "employs"),
    ("USER", "VERIFICATION_RECORD", "1", "1", "has"),
    ("MODERATOR", "VERIFICATION_RECORD", "1", "N", "verifies"),
    ("USER", "CONSENT_RECORD", "1", "N", "grants"),
    ("USER", "PREFERENCE_PROFILE", "1", "1", "has"),
    ("USER", "USER_ATTRIBUTE_WEIGHT", "1", "N", "sets"),
    ("USER", "MATCH_SCORE", "1", "N", "is paired in"),
    ("WEIGHT_SET", "MATCH_SCORE", "1", "N", "scored under"),
    ("MATCH_SCORE", "MESSAGE", "1", "N", "enables"),
    ("MATCH_SCORE", "CONTACT_SHARE", "1", "0..2", "unlocks"),
    ("MATCH_SCORE", "FEEDBACK", "1", "0..2", "generates"),
    ("USER", "MESSAGE", "1", "N", "sends"),
    ("USER", "REPORT", "1", "N", "files / is named in"),
    ("MODERATOR", "REPORT", "1", "N", "reviews"),
    ("USER", "USER_BLOCK", "1", "N", "blocks"),
]

lines = [
    "digraph ERD {",
    '  rankdir=TB; bgcolor="white"; splines=spline; overlap=false;',
    '  node [fontname="Helvetica", fontsize=10];',
    '  edge [fontname="Helvetica", fontsize=8.5, color="#555555", '
    'arrowsize=0.7, penwidth=1.0];',
    "  nodesep=0.40; ranksep=0.60;",
    '  label=<<FONT POINT-SIZE="13"><B>Cohab &#8211; Entity Relationship '
    'Diagram (with attributes and cardinalities)</B></FONT>>;',
    "  labelloc=t; labeljust=c;",
    "",
]

for name, fields in ENTITIES:
    lines.append(er_entity(name, fields))

lines.append("")
for src, dst, tc, hc, lbl in RELS:
    lines.append(
        f'  "{src}" -> "{dst}" [taillabel="{tc}", headlabel="{hc}", '
        f'label="{lbl}", labeldistance=1.6, labelangle=18, '
        f'arrowhead=none];'
    )

# Rank hints to keep the layout readable
lines += [
    "",
    '  {rank=same; "INSTITUTION"; "MODERATOR";}',
    '  {rank=same; "VERIFICATION_RECORD"; "USER"; "CONSENT_RECORD";}',
    '  {rank=same; "PREFERENCE_PROFILE"; "USER_ATTRIBUTE_WEIGHT"; '
    '"WEIGHT_SET";}',
    '  {rank=same; "MESSAGE"; "CONTACT_SHARE"; "FEEDBACK"; "REPORT"; '
    '"USER_BLOCK";}',
    "}",
]

render("\n".join(lines), "../image7.png", dpi=150)
print(f"ERD: {len(ENTITIES)} entities, {len(RELS)} relationships")
