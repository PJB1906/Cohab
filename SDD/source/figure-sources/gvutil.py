"""Shared Graphviz helpers for the Cohab SDD figures."""
import subprocess

FONT = "Helvetica"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(dot_source, out_png, dpi=170, engine="dot"):
    tmp = out_png.rsplit("/", 1)[-1].replace(".png", ".dot")
    with open(tmp, "w") as f:
        f.write(dot_source)
    subprocess.run([engine, "-Tpng", f"-Gdpi={dpi}", tmp, "-o", out_png],
                   check=True)
    print(f"  wrote {out_png}")


# ---------------------------------------------------------------- ER entity
def er_entity(name, fields, header_bg="#2E5C8A", new=False):
    """fields: list of (field_name, kind) where kind in {pk, fk, pkfk, ''}."""
    border = "#C0392B" if new else "#2E5C8A"
    rows = []
    for fname, kind in fields:
        if kind == "pk":
            cell = f'<B><FONT COLOR="#B03A2E">{esc(fname)}</FONT></B>'
        elif kind == "fk":
            cell = f'<I><FONT COLOR="#1F6FB2">{esc(fname)}</FONT></I>'
        elif kind == "pkfk":
            cell = (f'<B><FONT COLOR="#B03A2E">{esc(fname)}</FONT></B>'
                    f' <I><FONT COLOR="#1F6FB2">(FK)</FONT></I>')
        else:
            cell = esc(fname)
        rows.append(f'<TR><TD ALIGN="LEFT" PORT="{esc(fname)}">{cell}</TD></TR>')
    return (
        f'  "{name}" [shape=none, margin=0, label=<\n'
        f'    <TABLE BORDER="2" COLOR="{border}" CELLBORDER="1" '
        f'CELLSPACING="0" CELLPADDING="3">\n'
        f'      <TR><TD BGCOLOR="{header_bg}" ALIGN="CENTER">'
        f'<B><FONT COLOR="white" POINT-SIZE="11">{esc(name)}</FONT></B>'
        f'</TD></TR>\n'
        + "\n".join("      " + r for r in rows) + "\n"
        f'    </TABLE>>];\n'
    )


# ------------------------------------------------------------- UML class box
def uml_class(name, attrs, methods, fill="#F2F2F2", border="#444444",
              stereotype=None):
    head = esc(name)
    if stereotype:
        head = f'&#171;{esc(stereotype)}&#187;<BR/>{head}'
    rows = [f'<TR><TD BGCOLOR="{fill}" ALIGN="CENTER">'
            f'<B>{head}</B></TD></TR>']
    arow = "".join(f'{esc(a)}<BR ALIGN="LEFT"/>' for a in attrs)
    mrow = "".join(f'{esc(m)}<BR ALIGN="LEFT"/>' for m in methods)
    rows.append(f'<TR><TD ALIGN="LEFT" BALIGN="LEFT">'
                f'<FONT POINT-SIZE="9">{arow}</FONT></TD></TR>')
    rows.append(f'<TR><TD ALIGN="LEFT" BALIGN="LEFT">'
                f'<FONT POINT-SIZE="9">{mrow}</FONT></TD></TR>')
    return (
        f'  "{name}" [shape=none, margin=0, label=<\n'
        f'    <TABLE BORDER="1.5" COLOR="{border}" CELLBORDER="0" '
        f'CELLSPACING="0" CELLPADDING="4">\n'
        + "\n".join("      " + r for r in rows) + "\n"
        f'    </TABLE>>];\n'
    )
