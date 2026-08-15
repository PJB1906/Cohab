import subprocess
from schedule import ACTIVITIES, compute, critical_path

sched, END = compute()
CP = critical_path(sched)
CPSET = set(CP)
CPEDGES = set(zip(CP, CP[1:]))

CRIT_FILL, CRIT_LINE = "#F6C9C2", "#C0392B"
NORM_FILL, NORM_LINE = "#CFE2F3", "#2E6DA4"


def esc(s):
    """Escape text for Graphviz HTML-like labels."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def node(aid):
    v = sched[aid]
    crit = aid in CPSET
    fill, line = (CRIT_FILL, CRIT_LINE) if crit else (NORM_FILL, NORM_LINE)
    hdr = esc(f"{aid}: {v['label']}")
    return (
        f'  "{aid}" [shape=none, margin=0, label=<\n'
        f'    <TABLE BORDER="2" COLOR="{line}" CELLBORDER="1" CELLSPACING="0" '
        f'CELLPADDING="4">\n'
        f'      <TR><TD COLSPAN="3" BGCOLOR="{fill}">'
        f'<B>{hdr}</B></TD></TR>\n'
        f'      <TR><TD>ES={v["es"]}</TD><TD>Dur={v["dur"]}</TD>'
        f'<TD>EF={v["ef"]}</TD></TR>\n'
        f'      <TR><TD>LS={v["ls"]}</TD><TD>Slack={v["slack"]}</TD>'
        f'<TD>LF={v["lf"]}</TD></TR>\n'
        f'    </TABLE>>];\n'
    )


lines = [
    "digraph PERT {",
    '  rankdir=TB;',
    '  bgcolor="white";',
    '  node [fontname="Helvetica", fontsize=10];',
    '  edge [fontname="Helvetica", fontsize=9];',
    '  nodesep=0.45; ranksep=0.42;',
    "",
]

for aid in ACTIVITIES:
    lines.append(node(aid))

lines.append("")
for aid, (_, _, preds) in ACTIVITIES.items():
    for p in preds:
        if (p, aid) in CPEDGES:
            lines.append(f'  "{p}" -> "{aid}" '
                         f'[color="{CRIT_LINE}", penwidth=2.6, arrowsize=0.9];')
        else:
            lines.append(f'  "{p}" -> "{aid}" '
                         f'[color="#8A8A8A", penwidth=1.0, arrowsize=0.7];')

lines.append("")
lines.append(
    f'  legend [shape=none, margin=0, label=<'
    f'<TABLE BORDER="1" COLOR="#666666" CELLBORDER="0" CELLSPACING="2" '
    f'CELLPADDING="3">'
    f'<TR><TD><B>Critical Path ({END} weeks):</B></TD>'
    f'<TD>{" &#8594; ".join(CP)}</TD></TR>'
    f'<TR><TD><B>Project Duration:</B></TD>'
    f'<TD>{END} weeks (Slack = 0 on all critical activities)</TD></TR>'
    f'</TABLE>>];'
)
lines.append('  "N" -> legend [style=invis];')
lines.append("}")

dot = "\n".join(lines)
with open("pert.dot", "w") as f:
    f.write(dot)

subprocess.run(["dot", "-Tpng", "-Gdpi=170", "pert.dot",
                "-o", "../images/image16.png"], check=True)
print(f"PERT written: critical path {' -> '.join(CP)} = {END} weeks")
