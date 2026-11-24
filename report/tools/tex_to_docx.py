"""Convert report/main.tex into an IEEE-style two-column Word document.

Purpose-built for this report: it understands the LaTeX subset used in
main.tex (sections, itemize, figures, tables, lstlisting, bibliography and
inline formatting) so the .docx carries exactly the same text as the PDF.

Usage: python tex_to_docx.py main.tex main.docx
"""
import pathlib
import re
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

REPORT = pathlib.Path(__file__).resolve().parent.parent
FIG_SRC = REPORT.parent / "vm-vs-container" / "results" / "figures"
FONT = "Times New Roman"
MONO = "Courier New"
COL_W = Inches(3.45)
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

# ------------------------------------------------------------------ helpers
SIMPLE = {
    r"\i ": "ı", r"\i": "ı", r'\"a': "ä", r"\ldots": "…", r"\%": "%", r"\$": "$",
    r"\_": "_", r"\&": "&", r"\#": "#", r"\,": "\u2009", r"\quad": "  ",
    r"\hfill": "", r"\centering": "", r"\footnotesize": "", r"\scriptsize": "",
    r"\noindent": "", r"\IEEEauthorblockN": "", r"\IEEEauthorblockA": "",
}
MATH = {r"\pm": "±", r"\times": "×", r"\approx": "≈", r"\rightarrow": "→",
        r"\Rightarrow": "⇒", r"\sim": "~"}


def clean_text(s):
    s = s.replace("{,}", ",").replace("---", "—").replace("--", "–")
    s = s.replace("``", "“").replace("''", "”").replace("~", "\u00a0")
    s = re.sub(r"\\vs\.\\ ", "vs. ", s)
    s = s.replace(r"\ ", " ")
    for k, v in sorted(SIMPLE.items(), key=lambda kv: -len(kv[0])):
        s = s.replace(k, v)
    return s


def math_to_text(m):
    for k, v in MATH.items():
        m = m.replace(k, v)
    m = m.replace("{", "").replace("}", "").replace("\\", "")
    return m


class Ctx:
    def __init__(self, tex):
        self.cites = {k: i + 1 for i, k in enumerate(re.findall(r"\\bibitem\{([^}]+)\}", tex))}
        self.labels = {}
        counters = {"fig": 0, "tab": 0, "lst": 0, "sec": 0}
        # walk the document in order and number labels
        for m in re.finditer(r"\\(section\*?|begin\{figure\*?\}|begin\{table\}|begin\{lstlisting\}|label)\{?([^}\]]*)", tex):
            kind, arg = m.group(1), m.group(2)
            if kind == "section":
                counters["sec"] += 1
                last = ("sec", ROMAN[counters["sec"] - 1])
            elif kind.startswith("begin{figure"):
                counters["fig"] += 1
                last = ("fig", str(counters["fig"]))
            elif kind == "begin{table}":
                counters["tab"] += 1
                last = ("tab", ROMAN[counters["tab"] - 1])
            elif kind == "begin{lstlisting}":
                counters["lst"] += 1
                last = ("lst", str(counters["lst"]))
            elif kind == "label":
                pass
        # second pass: label -> number of the closest preceding numbered item
        counters = {"fig": 0, "tab": 0, "lst": 0, "sec": 0}
        current = {}
        pattern = re.compile(r"\\section\{|\\begin\{figure\*?\}|\\begin\{table\}|\\begin\{lstlisting\}|label[=\{]\{?([A-Za-z_:]+)\}?")
        for m in pattern.finditer(tex):
            tok = m.group(0)
            if tok.startswith("\\section"):
                counters["sec"] += 1
                current["sec"] = ROMAN[counters["sec"] - 1]
            elif tok.startswith("\\begin{figure"):
                counters["fig"] += 1
                current["fig"] = str(counters["fig"])
            elif tok.startswith("\\begin{table"):
                counters["tab"] += 1
                current["tab"] = ROMAN[counters["tab"] - 1]
            elif tok.startswith("\\begin{lst"):
                counters["lst"] += 1
                current["lst"] = str(counters["lst"])
            else:
                lab = m.group(1)
                if lab.startswith("fig:"):
                    self.labels[lab] = current.get("fig", "?")
                elif lab.startswith("tab:"):
                    self.labels[lab] = current.get("tab", "?")
                elif lab.startswith("lst:"):
                    self.labels[lab] = current.get("lst", "?")
                elif lab.startswith("sec:"):
                    self.labels[lab] = current.get("sec", "?")
                elif lab.startswith("app:"):
                    self.labels[lab] = "A"


def read_group(s, i):
    """s[i] == '{'; return (content, index after closing brace)."""
    depth, j = 0, i
    while j < len(s):
        if s[j] == "{" and (j == 0 or s[j - 1] != "\\"):
            depth += 1
        elif s[j] == "}" and s[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def parse_inline(s, ctx, style=None):
    """Return list of (text, style-dict) runs."""
    style = dict(style or {})
    runs, buf, i = [], "", 0

    def flush():
        nonlocal buf
        if buf:
            runs.append((clean_text(buf), dict(style)))
            buf = ""

    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] in "$%&_#{},":
            buf += s[i + 1] if s[i + 1] in "{}" else s[i:i + 2]
            i += 2
            continue
        if c == "$":
            j = s.index("$", i + 1)
            flush()
            runs.append((math_to_text(s[i + 1:j]), dict(style)))
            i = j + 1
            continue
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+)\*?", s[i:])
            if m:
                cmd = m.group(1)
                k = i + len(m.group(0))
                fmt = {"textbf": {"bold": True}, "textit": {"italic": True}, "emph": {"italic": True},
                       "texttt": {"mono": True}, "textsc": {"smallcaps": True}}
                if cmd in fmt and k < len(s) and s[k] == "{":
                    inner, k2 = read_group(s, k)
                    flush()
                    runs += parse_inline(inner, ctx, {**style, **fmt[cmd]})
                    i = k2
                    continue
                if cmd in ("cite", "ref", "url") and s[k] == "{":
                    inner, k2 = read_group(s, k)
                    flush()
                    if cmd == "cite":
                        runs.append(("[" + "], [".join(str(ctx.cites.get(x.strip(), "?")) for x in inner.split(",")) + "]", dict(style)))
                    elif cmd == "ref":
                        runs.append((ctx.labels.get(inner, "?"), dict(style)))
                    else:
                        runs.append((inner, {**style, "url": True}))
                    i = k2
                    continue
                if cmd in ("label", "setlength", "vspace", "hspace") and k < len(s) and s[k] == "{":
                    _, k2 = read_group(s, k)
                    if cmd == "setlength" and k2 < len(s) and s[k2] == "{":
                        _, k2 = read_group(s, k2)
                    i = k2
                    continue
                if cmd == "\\":
                    pass
            if s[i:i + 2] == "\\\\":
                flush()
                runs.append(("\n", dict(style)))
                i += 2
                if i < len(s) and s[i] == "[":
                    i = s.index("]", i) + 1
                continue
        if c in "{}":
            i += 1
            continue
        buf += c
        i += 1
    flush()
    return runs


def add_runs(p, runs, size=10, base=None):
    base = base or {}
    for text, st in runs:
        st = {**base, **st}
        parts = text.split("\n")
        for n, part in enumerate(parts):
            if n:
                p.add_run().add_break()
            if not part:
                continue
            r = p.add_run(part)
            r.font.name = MONO if st.get("mono") else FONT
            r.font.size = Pt(size - 1 if st.get("mono") else size)
            r.bold = st.get("bold")
            r.italic = st.get("italic")
            r.font.small_caps = st.get("smallcaps", False)
            if st.get("url"):
                r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x99)


def para(doc, runs, size=10, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=True, before=0, after=2, base=None):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.first_line_indent = Cm(0.35) if indent else None
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    pf.line_spacing = 1.0
    add_runs(p, runs, size, base)
    return p


def set_columns(section, num):
    sectPr = section._sectPr
    cols = sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sectPr.append(cols)
    cols.set(qn("w:num"), str(num))
    cols.set(qn("w:space"), "360")


def shade(cell_or_par, fill="F2F2F2"):
    el = cell_or_par._tc.get_or_add_tcPr() if hasattr(cell_or_par, "_tc") else cell_or_par._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    el.append(shd)


def border_paragraph(p):
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    for side in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        e.set(qn("w:space"), "2")
        e.set(qn("w:color"), "999999")
        bdr.append(e)
    pPr.append(bdr)


def caption(doc, text_runs, kind):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if kind == "table" else WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = kind == "table"
    add_runs(p, text_runs, 8)
    return p


# ------------------------------------------------------------------ blocks
def figure(doc, body, ctx):
    imgs = re.findall(r"\\includegraphics\[width=([^\]]+)\]\{([^}]+)\}", body)
    cap = re.search(r"\\caption\{", body)
    cap_text, _ = read_group(body, cap.end() - 1)
    lab = re.search(r"\\label\{([^}]+)\}", body).group(1)
    for _, path in imgs:
        name = pathlib.Path(path).stem
        png = FIG_SRC / f"{name}.png"
        if not png.exists():
            png = REPORT / "figures" / f"{name}.png"
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(4)
        width = COL_W if "crop" not in name or "hang" in name else Inches(1.9)
        p.add_run().add_picture(str(png), width=width)
    # sub-captions inside minipages
    for sub in re.findall(r"\\footnotesize ([^}]*)\}", body):
        pass
    caption(doc, [(f"Fig. {ctx.labels[lab]}. ", {})] + parse_inline(cap_text, ctx), "figure")


def table(doc, body, ctx):
    cap = re.search(r"\\caption\{", body)
    cap_text, _ = read_group(body, cap.end() - 1)
    lab = re.search(r"\\label\{([^}]+)\}", body).group(1)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.keep_with_next = True
    add_runs(p, [(f"TABLE {ctx.labels[lab]}", {})], 8)
    p2 = caption(doc, [(clean_text(cap_text).upper().replace("$\\PM$", "±"), {"smallcaps": False})], "table")
    p2.runs[0].text = p2.runs[0].text.replace("$\\PM$", "±")
    tab = re.search(r"\\begin\{tabular\}\{(?:[^{}]|\{[^{}]*\})*\}\s*(.*?)\\end\{tabular\}", body, re.S).group(1)
    rows = [r.strip() for r in re.split(r"\\\\", tab.replace("\\hline", "")) if r.strip()]
    cells = [[c.strip() for c in r.split("&")] for r in rows]
    ncol = max(len(r) for r in cells)
    t = doc.add_table(rows=len(cells), cols=ncol)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    size = 7 if ncol >= 5 else 8
    total = 3.4
    shares = {2: [0.36, 0.64], 3: [0.40, 0.12, 0.48], 5: [0.38, 0.11, 0.21, 0.15, 0.15]}
    widths = [total * f for f in shares.get(ncol, [1 / ncol] * ncol)]
    if ncol == 3 and "Cost item" in cells[0][0]:
        widths = [total * f for f in (0.42, 0.29, 0.29)]
    grid = t._tbl.tblGrid
    for j, gc in enumerate(grid.findall(qn("w:gridCol"))):
        gc.set(qn("w:w"), str(int(widths[j] * 1440)))
    for j, col in enumerate(t.columns):
        col.width = Inches(widths[j])
    for i, row in enumerate(cells):
        for j in range(ncol):
            c = t.cell(i, j)
            c.width = Inches(widths[j])
            c.paragraphs[0].paragraph_format.space_after = Pt(0)
            add_runs(c.paragraphs[0], parse_inline(row[j] if j < len(row) else "", ctx), size,
                     {"bold": True} if i == 0 else None)
            if i == 0:
                shade(c)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def listing(doc, opts, code, ctx):
    cap = re.search(r"caption=\{(.*?)\}, label", opts)
    lab = re.search(r"label=\{([^}]+)\}", opts).group(1)
    lines = code.strip("\n").split("\n")
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(0)
    border_paragraph(p)
    shade(p, "F7F7F7")
    for n, line in enumerate(lines):
        if n:
            p.add_run().add_break()
        r = p.add_run(line.replace("\t", "    ").rstrip() or " ")
        r.font.name, r.font.size = MONO, Pt(6.5)
    caption(doc, [(f"Listing {ctx.labels[lab]}. ", {})] + parse_inline(cap.group(1), ctx), "figure")


def itemize(doc, body, ctx):
    for item in re.split(r"\\item\s*", body)[1:]:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(1)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_runs(p, parse_inline(item.strip(), ctx), 10)


def heading(doc, text, level, number):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.keep_with_next = True
    if level == 1:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before, pf.space_after = Pt(8), Pt(4)
        r = p.add_run(f"{number}. {text}" if number else text)
        r.font.small_caps = True
    else:
        pf.space_before, pf.space_after = Pt(4), Pt(2)
        r = p.add_run(f"{number}. {text}")
        r.italic = True
    r.font.name, r.font.size = FONT, Pt(10)


# ------------------------------------------------------------------ main
def build(tex_path, out_path):
    tex = pathlib.Path(tex_path).read_text(encoding="utf-8")
    ctx = Ctx(tex)
    body = tex.split("\\begin{document}", 1)[1].split("\\end{document}", 1)[0]
    body = re.sub(r"(?m)^\s*%.*$", "", body)

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(1.6)
    sec.top_margin, sec.bottom_margin = Cm(1.9), Cm(2.5)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(10)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    # title block (single column)
    title = re.search(r"\\title\{(.*?)\\\\\s*\{\\footnotesize(.*?)\}\s*\}", body, re.S)
    para(doc, parse_inline(title.group(1), ctx), 22, WD_ALIGN_PARAGRAPH.CENTER, False, 0, 2)
    para(doc, parse_inline(title.group(2).replace("\\\\", " — "), ctx), 8, WD_ALIGN_PARAGRAPH.CENTER, False, 0, 10)
    author = re.search(r"\\author\{(.*)\}\s*\\maketitle", body, re.S).group(1)
    name = re.search(r"\\IEEEauthorblockN\{(.*?)\}", author).group(1)
    para(doc, parse_inline(name, ctx), 11, WD_ALIGN_PARAGRAPH.CENTER, False, 0, 0)
    aff = " ".join(re.search(r"\\IEEEauthorblockA\{(.*)\}", author, re.S).group(1).split())
    para(doc, parse_inline(aff, ctx), 10, WD_ALIGN_PARAGRAPH.CENTER, False, 0, 12)

    new = doc.add_section(WD_SECTION.CONTINUOUS)
    set_columns(new, 2)

    rest = body.split("\\maketitle", 1)[1]
    absm = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", rest, re.S)
    p = para(doc, [("Abstract—", {"bold": True, "italic": True})] + parse_inline(absm.group(1).strip(), ctx), 9,
             indent=False, base={"bold": True})
    kw = re.search(r"\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}", rest, re.S).group(1).strip()
    para(doc, [("Index Terms—", {"bold": True, "italic": True})] + parse_inline(kw, ctx), 9, indent=False,
         base={"bold": True}, after=6)
    rest = rest[kw and rest.index("\\end{IEEEkeywords}") + len("\\end{IEEEkeywords}"):]

    sec_n, sub_n, in_appendix = 0, 0, False
    token = re.compile(
        r"\\section\*?\{|\\subsection\{|\\begin\{(figure\*?|table|itemize|lstlisting|thebibliography)\}|\\appendix|\n\s*\n")
    pos = 0
    pending = ""

    def flush_par():
        nonlocal pending
        text = " ".join(re.sub(r"\\label\{[^}]*\}", "", pending).split())
        if text:
            para(doc, parse_inline(text, ctx))
        pending = ""

    while True:
        m = token.search(rest, pos)
        if not m:
            pending += rest[pos:]
            flush_par()
            break
        pending += rest[pos:m.start()]
        tok = m.group(0)
        if tok.strip() == "":
            flush_par()
            pos = m.end()
            continue
        flush_par()
        if tok.startswith("\\section"):
            text, end = read_group(rest, m.end() - 1)
            starred = tok.startswith("\\section*")
            if starred:
                heading(doc, clean_text(text), 1, None)
            elif in_appendix:
                sub_n += 1
                heading(doc, clean_text(text), 2, chr(64 + sub_n))
            else:
                sec_n += 1
                sub_n = 0
                heading(doc, clean_text(text), 1, ROMAN[sec_n - 1])
            pos = end
        elif tok.startswith("\\subsection"):
            text, end = read_group(rest, m.end() - 1)
            sub_n += 1
            heading(doc, clean_text(text), 2, chr(64 + sub_n))
            pos = end
        elif tok == "\\appendix":
            in_appendix, sub_n = True, 0
            heading(doc, "Appendix", 1, None)
            pos = m.end()
        else:
            env = m.group(1)
            end_tok = f"\\end{{{env}}}"
            end = rest.index(end_tok, m.end())
            inner = rest[m.end():end]
            if env.startswith("figure"):
                figure(doc, inner, ctx)
            elif env == "table":
                table(doc, inner, ctx)
            elif env == "itemize":
                itemize(doc, inner, ctx)
            elif env == "lstlisting":
                opts_m = re.match(r"\[(.*?)\]\n", inner, re.S)
                listing(doc, opts_m.group(1), inner[opts_m.end():], ctx)
            elif env == "thebibliography":
                heading(doc, "References", 1, None)
                for n, item in enumerate(re.split(r"\\bibitem\{[^}]+\}", inner)[1:], 1):
                    p = para(doc, [(f"[{n}] ", {})] + parse_inline(" ".join(item.split()), ctx), 8, indent=False)
                    p.paragraph_format.left_indent = Cm(0.6)
                    p.paragraph_format.first_line_indent = Cm(-0.6)
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pos = end + len(end_tok)

    doc.save(out_path)
    print("written", out_path)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
