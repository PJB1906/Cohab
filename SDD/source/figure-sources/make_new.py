"""New figures: two-stage matching pipeline and the match/report state models."""
from gvutil import render

# ------------------------------------------- Fig 10.1: two-stage match pipeline
def stage_box(title, items, fill, header, border):
    rows = "".join(
        f'<TR><TD ALIGN="LEFT">&#8226; {it}</TD></TR>' for it in items)
    return (
        f'<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="1" CELLPADDING="2">'
        f'<TR><TD BGCOLOR="{header}" ALIGN="CENTER">'
        f'<B><FONT POINT-SIZE="10">{title}</FONT></B></TD></TR>'
        f'{rows}</TABLE>'
    )


HARD = ["City / locality overlap",
        "Budget bands intersect",
        "Move-in date within tolerance window",
        "Gender preference mutually satisfied",
        "Smoking / pets deal-breakers respected",
        "Neither party blocked or suspended"]

SOFT = ["Categorical similarity (sleep, cleanliness, social, food)",
        "Continuous similarity (budget proximity)",
        "Semantic similarity (lifestyle-notes embedding cosine)"]

pipeline = f'''digraph Pipeline {{
  rankdir=TB; bgcolor="white";
  node [shape=box, style="rounded,filled", fontname="Helvetica",
        fontsize=9.5, margin="0.16,0.10"];
  edge [color="#5A5A5A", fontname="Helvetica", fontsize=9,
        arrowsize=0.75, penwidth=1.1];
  nodesep=0.40; ranksep=0.40;

  pool [label="All verified, active users\\n(full candidate pool, N)",
        fillcolor="#E8E8E8", color="#888888"];

  stage1 [shape=none, margin=0, fillcolor="none", label=<
    <TABLE BORDER="2" COLOR="#C0705F" CELLBORDER="0" CELLSPACING="0"
           CELLPADDING="6" BGCOLOR="#FDECEA">
      <TR><TD>{stage_box("Stage 1 &#8212; Hard Constraints (eligibility)",
                          HARD, "#FDECEA", "#F9D6D0", "#C0705F")}</TD></TR>
    </TABLE>>];

  elig [label="Eligible pool  (n &#8810; N)\\nscoring cost falls with the pool",
        fillcolor="#FBE6C8", color="#B8873C"];

  stage2 [shape=none, margin=0, fillcolor="none", label=<
    <TABLE BORDER="2" COLOR="#8B6BB1" CELLBORDER="0" CELLSPACING="0"
           CELLPADDING="6" BGCOLOR="#F3EDFA">
      <TR><TD>{stage_box("Stage 2 &#8212; Soft Scoring (weighted, explainable)",
                          SOFT, "#F3EDFA", "#E4D9F2", "#8B6BB1")}</TD></TR>
    </TABLE>>];

  dir [label="Directional scores S(a&#8594;b) and S(b&#8594;a)\\n"
             + "each computed with that user's own importance weights",
       fillcolor="#D6E4F5", color="#5B87BC"];
  comb [label="Combined score = harmonic mean of the two\\n"
              + "(penalises matches that suit only one side)",
        fillcolor="#D6E4F5", color="#5B87BC"];
  rank [label="Ranked, explainable match list",
        fillcolor="#D5EFDF", color="#4E9670"];

  excl [shape=note, style=filled, fillcolor="#FAFAFA", color="#999999",
        label="Excluded, with the failed\\nconstraint stored to answer\\n"
              + "\\"why was this profile not shown?\\""];

  pool -> stage1;
  stage1 -> elig [label="  passes every constraint"];
  stage1 -> excl [label="  fails any constraint", style=dashed,
                  color="#AAAAAA"];
  elig -> stage2;
  stage2 -> dir;
  dir -> comb;
  comb -> rank;

  {{rank=same; elig; excl;}}
}}'''

render(pipeline, "../images/image17.png", dpi=170)

# ------------------------------------------------- Fig 8.2: match state model
states = '''digraph States {
  rankdir=TB; bgcolor="white";
  node [shape=box, style="rounded,filled", fontname="Helvetica",
        fontsize=10, fillcolor="#D6E4F5", color="#5B87BC",
        margin="0.16,0.09"];
  edge [color="#5A5A5A", fontname="Helvetica", fontsize=8.5,
        arrowsize=0.7, penwidth=1.0];
  graph [fontname="Helvetica", fontsize=11];
  nodesep=0.35; ranksep=0.40;

  subgraph cluster_match {
    label="(a) MATCH_SCORE lifecycle";
    style="rounded"; color="#999999";

    mstart [shape=circle, label="", width=0.22, fillcolor="#4E9670",
            color="#4E9670"];
    Suggested; Viewed;
    Interested [label="Interested\\n(one side)"];
    Mutual [label="Mutual\\n(both sides)", fillcolor="#D5EFDF",
            color="#4E9670"];
    Chatting;
    ContactShared [label="Contact Shared", fillcolor="#D5EFDF",
                   color="#4E9670"];
    Cohabiting;
    Rejected [label="Rejected", fillcolor="#F9D6D0", color="#C0705F"];
    Expired [label="Expired", fillcolor="#EFEFEF", color="#999999"];
    mend [shape=doublecircle, label="", width=0.20, fillcolor="#C0392B",
          color="#C0392B"];

    mstart -> Suggested [label="score computed"];
    Suggested -> Viewed [label="user opens\\nmatch card"];
    Viewed -> Interested [label="express interest"];
    Viewed -> Rejected [label="dismiss"];
    Interested -> Mutual [label="other side\\nreciprocates"];
    Interested -> Expired [label="no response\\nin 14 days"];
    Mutual -> Chatting [label="chat thread\\ncreated"];
    Chatting -> ContactShared [label="both opt in"];
    Chatting -> Rejected [label="either withdraws"];
    ContactShared -> Cohabiting [label="move-in\\nconfirmed"];
    Cohabiting -> mend [label="outcome logged\\n(30 / 90-day survey)"];
    Rejected -> mend [label="outcome logged"];
    Expired -> mend;
  }

  subgraph cluster_report {
    label="(b) REPORT lifecycle";
    style="rounded"; color="#999999";
    node [fillcolor="#FBE6C8", color="#B8873C"];

    rstart [shape=circle, label="", width=0.22, fillcolor="#4E9670",
            color="#4E9670"];
    Open; UnderReview [label="Under Review"];
    Substantiated [label="Substantiated", fillcolor="#F9D6D0",
                   color="#C0705F"];
    Dismissed;
    ActionTaken [label="Account Action\\n(warn / suspend / ban)",
                 fillcolor="#F9D6D0", color="#C0705F"];
    rend [shape=doublecircle, label="", width=0.20, fillcolor="#C0392B",
          color="#C0392B"];

    rstart -> Open [label="user files report"];
    Open -> UnderReview [label="moderator claims\\n(SLA: 24 h)"];
    UnderReview -> Substantiated [label="evidence\\nsupports claim"];
    UnderReview -> Dismissed [label="no basis"];
    Substantiated -> ActionTaken;
    ActionTaken -> rend [label="reporter notified"];
    Dismissed -> rend [label="reporter notified"];
  }
}'''

render(states, "../images/image18.png", dpi=170)
