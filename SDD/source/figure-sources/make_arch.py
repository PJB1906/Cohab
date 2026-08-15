"""Figures 2.1 (layered architecture) and 3.1 (component view), revised.

Both now show the API Gateway as the orchestration boundary rather than the
frontend, plus the Redis cache and WebSocket gateway the chat and performance
sections rely on.
"""
from gvutil import render

# ---------------------------------------------------------------- Figure 2.1
PRES = "#D6E4F5"
APP = "#FBE6C8"
ML = "#E4D9F2"
DATA = "#D5EFDF"
GATE = "#F9D6D0"

arch = f'''digraph Architecture {{
  rankdir=TB; bgcolor="white"; compound=true;
  node [shape=box, style="rounded,filled", fontname="Helvetica",
        fontsize=9.5, height=0.42, margin="0.12,0.06"];
  edge [color="#666666", arrowsize=0.6, penwidth=0.9];
  graph [fontname="Helvetica", fontsize=10.5];
  nodesep=0.22; ranksep=0.45;

  subgraph cluster_pres {{
    label="Presentation Layer  (Responsive Web Portal / Mobile Web)";
    style="rounded,filled"; fillcolor="#EDF4FC"; color="#7FA8D4";
    node [fillcolor="{PRES}", color="#5B87BC"];
    p1 [label="Sign-Up /\\nVerification UI"];
    p2 [label="Preference\\nQuestionnaire UI"];
    p3 [label="Ranked Match &\\nExplanation UI"];
    p4 [label="In-App Chat UI"];
    p5 [label="Safety Report UI"];
    p6 [label="Institutional\\nAnalytics UI"];
  }}

  subgraph cluster_gate {{
    label="API Gateway & Orchestration  (authentication, routing, rate limiting)";
    style="rounded,filled"; fillcolor="#FDEEEB"; color="#D98B7D";
    node [fillcolor="{GATE}", color="#C0705F"];
    g1 [label="REST API Gateway\\n(FastAPI routers)"];
    g2 [label="WebSocket Gateway\\n(chat transport)"];
    g3 [label="AuthN / AuthZ\\nMiddleware"];
  }}

  subgraph cluster_app {{
    label="Application / Business Logic Layer  (FastAPI services)";
    style="rounded,filled"; fillcolor="#FEF6E9"; color="#D8A85E";
    node [fillcolor="{APP}", color="#B8873C"];
    a1 [label="Auth &\\nVerification"];
    a2 [label="Preference\\nService"];
    a3 [label="Eligibility\\nFilter"];
    a4 [label="Compatibility\\nMatching & Scoring"];
    a5 [label="Ranking &\\nExplainability"];
    a6 [label="Communication\\n(Chat) Service"];
    a7 [label="Safety &\\nReporting"];
    a8 [label="Feedback &\\nWeight Refinement"];
    a9 [label="Institutional\\nAnalytics"];
    a10 [label="Consent &\\nData Rights"];
  }}

  subgraph cluster_ml {{
    label="AI / ML & Integration Layer";
    style="rounded,filled"; fillcolor="#F3EDFA"; color="#A98CCB";
    node [fillcolor="{ML}", color="#8B6BB1"];
    m1 [label="scikit-learn\\n(Weighted Similarity)"];
    m2 [label="sentence-transformers\\n(Semantic Similarity)"];
    m3 [label="pandas / NumPy\\n(Weight Refinement)"];
    m4 [label="Email / SMS Notifier\\n(SMTP / SMS gateway)"];
  }}

  subgraph cluster_data {{
    label="Persistence Layer";
    style="rounded,filled"; fillcolor="#E8F7EE"; color="#7FBF9A";
    node [fillcolor="{DATA}", color="#4E9670"];
    d1 [label="PostgreSQL\\n(Users, Verification,\\nMatches, Reports)"];
    d2 [label="MongoDB\\n(Preference Profiles)"];
    d3 [label="Encrypted Chat\\nMessage Store"];
    d4 [label="Redis\\n(Candidate pool &\\nembedding cache)"];
    d5 [label="Object Store\\n(ID documents,\\nrestricted access)"];
    d6 [label="Application /\\nAudit Logs\\n(PII-excluded)"];
  }}

  p1 -> g1 [ltail=cluster_pres, lhead=cluster_gate];
  g1 -> a1 [ltail=cluster_gate, lhead=cluster_app];
  a4 -> m1 [ltail=cluster_app, lhead=cluster_ml];
  m1 -> d1 [ltail=cluster_ml, lhead=cluster_data];

  // Invisible left-edge anchors so the layer bands stack squarely
  // instead of drifting into a staircase.
  p6 -> g3 [style=invis];
  g3 -> a10 [style=invis];
  a10 -> m4 [style=invis];
  m4 -> d6 [style=invis];
}}'''

render(arch, "../images/image2.png", dpi=150)

# ---------------------------------------------------------------- Figure 3.1
comp = '''digraph Components {
  rankdir=TB; bgcolor="white"; compound=true;
  node [shape=component, style=filled, fontname="Helvetica", fontsize=9.5,
        fillcolor="#FBE6C8", color="#B8873C"];
  edge [color="#666666", arrowsize=0.65, penwidth=0.95,
        fontname="Helvetica", fontsize=8.5];
  graph [fontname="Helvetica", fontsize=10.5];
  nodesep=0.30; ranksep=0.50;

  fe [label="Frontend Component\\n(Responsive Web Portal)",
      fillcolor="#D6E4F5", color="#5B87BC"];
  gw [label="API Gateway Component\\n(routing, authN, rate limiting)",
      fillcolor="#F9D6D0", color="#C0705F"];

  subgraph cluster_bl {
    label="Business Logic Components";
    style="rounded,filled"; fillcolor="#FEF6E9"; color="#D8A85E";
    auth  [label="Auth & Verification\\nComponent"];
    pref  [label="Preference Profile\\nComponent"];
    elig  [label="Eligibility Filter\\nComponent"];
    match [label="Compatibility Matching\\nComponent"];
    rank  [label="Ranking & Explainability\\nComponent"];
    chat  [label="In-App Communication\\nComponent"];
    safe  [label="Safety & Reporting\\nComponent"];
    fb    [label="Feedback & Weight\\nRefinement Component"];
    wreg  [label="Weight Registry\\nComponent"];
    notif [label="Notification\\nComponent"];
    ana   [label="Institutional Analytics\\nComponent"];
    cons  [label="Consent & Data Rights\\nComponent"];
  }

  db [label="Database Component\\n(PostgreSQL + MongoDB + Redis)",
      fillcolor="#D5EFDF", color="#4E9670", shape=box3d];

  fe -> gw;
  gw -> auth; gw -> pref; gw -> rank; gw -> chat; gw -> safe;
  gw -> ana;  gw -> cons;

  pref -> elig  [label="profile"];
  elig -> match [label="eligible pool"];
  wreg -> match [label="active weights", style=dashed];
  match -> rank [label="scores + breakdown"];
  rank -> fb    [label="outcomes"];
  fb -> wreg    [label="new weight set"];
  fb -> ana     [label="aggregates"];
  chat -> safe  [label="flagged content"];
  chat -> notif; safe -> notif;
  cons -> auth  [style=dashed, label="erasure"];

  edge [color="#B0B0B0", penwidth=0.7, arrowsize=0.5];
  auth -> db; pref -> db; match -> db; rank -> db; chat -> db;
  safe -> db; fb -> db; wreg -> db; ana -> db; cons -> db;
}'''

render(comp, "../images/image3.png", dpi=150)
