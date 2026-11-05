#!/usr/bin/env python3
"""build_figures.py, edition 1, 2026-11-05.

Builds the site's figures as self-contained SVG files in assets/. Each figure is
laid out in HTML with the site's IBM Plex fonts, printed to PDF by Chromium
(Playwright) and converted by pdftocairo, so every glyph is an outline in the
SVG: no font file ships, no web font is needed, and the figure looks the same in
a page, a PDF or a slide. Every figure has a wide variant (1116 px, the page's
content width) and a narrow one (358 px, a phone's content width).

The words and numbers in the figures are the data blocks below, taken from the
page text they illustrate. Change a number there and rebuild; do not edit the SVG.

Figures
  arc    the engagement, from the tasks you send to support   (offering.html)
  tiers  the three deployment tiers and the routing gate       (offering.html)
  flow   where the plug-ins land in a design flow              (offering.html)

Usage
  python3 build_figures.py --fonts <dir holding IBM-Plex-Sans/ IBM-Plex-Sans-Condensed/ IBM-Plex-Mono/>
                           [--out <assets dir>] [--preview <dir for PNG previews>] [--only arc,tiers,flow]
  The font dir is the unpacked npm package @ibm/plex 6.4.1 (npm pack @ibm/plex@6.4.1).
  Needs Playwright with its Chromium, and pdftocairo (poppler).

Checks it makes, and fails loudly on
  every font face the figures use is loaded before printing;
  the PDF has exactly one page;
  the SVG holds no raster image and no live text (everything is outlined);
  the SVG's size matches the laid-out figure.
"""
import argparse, html, math, pathlib, re, subprocess, sys, tempfile, hashlib

# ---------------------------------------------------------------------------------------------
# data: the words and numbers in each figure
# ---------------------------------------------------------------------------------------------
ARC = [
    # when, title, body, chip, style
    ("Before", "You send the tasks",
     "Twenty to thirty of your team's own, de-identified by you. You name the models it may use.",
     None, ""),
    ("Weeks 1 and 2", "The measured assessment",
     "Each task runs three times through each model, with the predictions written before the first run.",
     "$7,500 fixed, remote", "hi"),
    ("End of week 2", "The report",
     "Accuracy by model and family, the silent-wrong-answer map, one recommendation.",
     "Yours to keep", ""),
    ("About two months", "The follow-on",
     "Kickoff and deploy, integrate, build the curriculum, live training on your own tools.",
     "Priced from the report", ""),
    ("Ongoing, optional", "Support",
     "Release tracking and rebuilds when your tools or your PDK move.",
     "From $1,000 a month", "opt"),
]
ARC_TITLE = "The engagement, from the tasks you send to support"
ARC_DESC = ("Before: you send twenty to thirty of your team's own tasks, de-identified, and name the models it may use. "
            "Weeks 1 and 2: the measured assessment, $7,500 fixed and remote; each task runs three times through each model, "
            "with the predictions written before the first run. End of week 2: the report, with accuracy by model and family, "
            "the silent-wrong-answer map and one recommendation, yours to keep. About two months: the follow-on, kickoff and "
            "deploy, integrate, build the curriculum, live training, priced from the report. Ongoing and optional: "
            "support from $1,000 a month.")

GATE = ("The routing gate",
        "Every task passes it first. Foundry-covered and design-sensitive content stays in tier 1. "
        "Generic tasks can go to tiers 2 and 3.")
TIERS = [
    # zone, tier, title, body, route label, style
    ("Inside your building", "Tier 1", "Full on-prem, open weights",
     "No design data leaves the building. A modest local model, 30B-class, runs on your hardware beside the deterministic tooling.",
     "sensitive", "t1"),
    ("Inside your cloud account", "Tier 2", "Frontier model in your cloud tenancy",
     "Inference runs in your own account, and data does not go to a vendor API. Claude through AWS Bedrock or GCP Vertex, "
     "or OpenAI's models through Azure.",
     "generic", "t2"),
    ("At a vendor, zero retention", "Tier 3", "Vendor API with zero data retention",
     "The least sensitive work: generic tasks with nothing foundry-covered or design-identifying in them.",
     "generic", "t3"),
]
TIER_COSTS = [
    # amount, words, tag, applies to
    ("$42,000", "up front for up to 25 engineers, the cheapest on-site fleet recommended", "ESTIMATE", "Tier 1"),
    ("$28 to $230", "per engineer a year at our measured usage, with no capital", "ESTIMATE", "Tiers 2 and 3"),
]
TIER_FOOT = ("Every tier ships with local retrieval over your PDK docs, design docs and tool manuals. "
             "Your legal team decides which tiers your foundry NDA allows.")
TIERS_TITLE = "Three deployment tiers behind one routing gate"
TIERS_DESC = ("A routing gate comes first: foundry-covered and design-sensitive content stays in tier 1, generic tasks can go "
              "to tiers 2 and 3. Tier 1, inside your building: full on-prem with open weights, a modest 30B-class local model "
              "on your hardware, $42,000 up front for up to 25 engineers (estimate). Tier 2, inside your cloud account: a "
              "frontier model in your tenancy, such as Claude through AWS Bedrock or GCP Vertex, or OpenAI's models through "
              "Azure. Tier 3, at a vendor with zero data retention: generic tasks only. Tiers 2 and 3 need no capital and cost "
              "$28 to $230 per engineer a year at measured usage (estimate). Every tier ships with local retrieval over your "
              "documentation, and your legal team decides which tiers your foundry NDA allows.")

FLOW = [
    ("Requirements and spec",
     "Read-only dumps of the requirements database. Writes by copy-and-patch, behind guards."),
    ("Architecture and models",
     "Behavioural harnesses and models, generated and checked against the simulator."),
    ("Schematic entry",
     "Build scripts that address device terminals by name, so topology is right by construction."),
    ("Simulation and characterisation",
     "One swept test, netlisted once and spread across a farm. Mismatch campaigns rolled up flat."),
    ("Reliability and stress",
     "Stress benches for fresh, stressed and aged parts, in several stress configurations."),
    ("Documentation and review",
     "Decks and figures built by script and checked as rendered images before review."),
    ("Production test handoff",
     "Test procedures staged in the requirements database, guarded and verified."),
]
FLOW_QA = ("Artifact QA, on every output",
           "Render-to-image inspection, checksum before load, integrity greps, and a hard stop on a null result.")
FLOW_DEC = ("At every stage",
            "The decisions stay with the engineer. Limits, waivers, corner acceptance, ship or redesign.")
FLOW_TITLE = "Where the plug-ins land in a design flow"
FLOW_DESC = ("Seven stages of a design flow, each with its plug-in. Requirements and spec: read-only dumps of the requirements "
             "database and guarded copy-and-patch writes. Architecture and models: generated behavioural harnesses checked "
             "against the simulator. Schematic entry: build scripts that address terminals by name. Simulation and "
             "characterisation: one swept test spread across a farm, mismatch campaigns rolled up flat. Reliability and "
             "stress: benches for fresh, stressed and aged parts. Documentation and review: decks and figures built by script "
             "and checked as rendered images. Production test handoff: test procedures staged in the requirements database. "
             "Artifact QA runs on every output. At every stage the decisions stay with the engineer: limits, waivers, corner "
             "acceptance, ship or redesign.")

WIDE, NARROW = 1116, 358

# ---------------------------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------------------------
FACES = [
    ("IBM Plex Sans", 400, "IBM-Plex-Sans/fonts/complete/woff2/IBMPlexSans-Regular.woff2"),
    ("IBM Plex Sans", 500, "IBM-Plex-Sans/fonts/complete/woff2/IBMPlexSans-Medium.woff2"),
    ("IBM Plex Sans", 600, "IBM-Plex-Sans/fonts/complete/woff2/IBMPlexSans-SemiBold.woff2"),
    ("IBM Plex Sans Condensed", 600, "IBM-Plex-Sans-Condensed/fonts/complete/woff2/IBMPlexSansCondensed-SemiBold.woff2"),
    ("IBM Plex Sans Condensed", 700, "IBM-Plex-Sans-Condensed/fonts/complete/woff2/IBMPlexSansCondensed-Bold.woff2"),
    ("IBM Plex Mono", 400, "IBM-Plex-Mono/fonts/complete/woff2/IBMPlexMono-Regular.woff2"),
    ("IBM Plex Mono", 500, "IBM-Plex-Mono/fonts/complete/woff2/IBMPlexMono-Medium.woff2"),
    ("IBM Plex Mono", 600, "IBM-Plex-Mono/fonts/complete/woff2/IBMPlexMono-SemiBold.woff2"),
]

BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#fff}
body{font-family:'IBM Plex Sans';color:#0C1B33;font-size:14px;line-height:1.45;-webkit-print-color-adjust:exact;print-color-adjust:exact}
#fig{background:#fff}
.k{font-family:'IBM Plex Mono';font-weight:600;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:#5B6B7F;line-height:1.3}
.h{font-family:'IBM Plex Sans Condensed';font-weight:600;line-height:1.12;letter-spacing:-0.005em}
.num{font-family:'IBM Plex Mono';font-weight:600;letter-spacing:-0.02em}
.tag{display:inline-block;font-family:'IBM Plex Mono';font-weight:600;font-size:10.5px;letter-spacing:.04em;padding:2px 6px;border-radius:3px;background:#B35900;color:#fff;line-height:1.35;vertical-align:1px;white-space:nowrap}
"""

ARROW_R = ('<svg width="22" height="14" viewBox="0 0 22 14"><path d="M0 7H19" stroke="#5B6B7F" stroke-width="2"/>'
           '<path d="M14 2L20 7L14 12" fill="none" stroke="#5B6B7F" stroke-width="2"/></svg>')
def arrow_d(color="#5B6B7F", w=2):
    return (f'<svg width="14" height="22" viewBox="0 0 14 22"><path d="M7 0V19" stroke="{color}" stroke-width="{w}"/>'
            f'<path d="M2 14L7 20L12 14" fill="none" stroke="{color}" stroke-width="{w}"/></svg>')

E = html.escape

def fig_arc(variant):
    css = """
.arc .row{display:flex;align-items:stretch}
.arc .col{display:flex;flex-direction:column;min-width:0}
.arc .card{flex:1;border:1.5px solid #C9D3DF;border-radius:6px;padding:15px 15px 14px;display:flex;flex-direction:column;background:#fff}
.arc .t{font-size:20px;color:#0C1B33}
.arc .b{margin-top:7px;color:#2A3A52;flex:1}
.arc .chip{margin-top:12px;align-self:flex-start;font-size:12px;letter-spacing:-0.03em;background:#EEF3F8;color:#0C1B33;padding:4px 8px;border-radius:3px;line-height:1.3}
.arc .hi .k{color:#1B4FE8}
.arc .hi .card{background:#1B4FE8;border-color:#1B4FE8}
.arc .hi .t{color:#fff}.arc .hi .b{color:#E3EAFF}.arc .hi .chip{background:#fff;color:#1B4FE8}
.arc .opt .card{border-style:dashed;border-color:#8A99AD}
.arc.wide{width:%dpx}
.arc.wide .col{flex:1 1 0}
.arc.wide .col .k{height:24px}
.arc.wide .arr{flex:0 0 24px;display:flex;align-items:center;justify-content:center;padding-top:24px}
.arc.narrow{width:%dpx}
.arc.narrow .row{flex-direction:column}
.arc.narrow .col .k{margin-bottom:6px}
.arc.narrow .t{font-size:19px}
.arc.narrow .arr{height:30px;display:flex;align-items:center;justify-content:center}
""" % (WIDE, NARROW)
    parts = []
    for i, (when, title, body, chip, style) in enumerate(ARC):
        if i:
            parts.append(f'<div class="arr">{ARROW_R if variant == "wide" else arrow_d()}</div>')
        chip_html = f'<div class="chip num">{E(chip)}</div>' if chip else ""
        parts.append(f'<div class="col {style}"><div class="k">{E(when)}</div><div class="card">'
                     f'<div class="h t">{E(title)}</div><div class="b">{E(body)}</div>{chip_html}</div></div>')
    return css, f'<div id="fig" class="arc {variant}"><div class="row">{"".join(parts)}</div></div>'

def fig_tiers(variant):
    css = """
.tiers .gate{background:#0C1B33;color:#fff;border-radius:6px;padding:15px 20px}
.tiers .gate .k{color:#7FA6FF}
.tiers .gt{font-size:16px;margin-top:5px;line-height:1.4}
.tiers .rt{display:flex;align-items:center;gap:8px;font-family:'IBM Plex Mono';font-size:12px;font-weight:600;color:#5B6B7F}
.tiers .rt.sensitive{color:#1B4FE8}
.tiers .tc{display:flex;flex-direction:column;min-width:0}
.tiers .zl{margin-bottom:6px}
.tiers .card{flex:1;border-radius:6px;padding:15px 17px;background:#fff}
.tiers .t1 .card{border:2px solid #0C1B33}
.tiers .t2 .card{border:2px solid #1B4FE8}
.tiers .t3 .card{border:1.5px dashed #8A99AD}
.tiers .tn{color:#1B4FE8}
.tiers .tt{font-size:21px;margin-top:4px}
.tiers .b{margin-top:7px;color:#2A3A52}
.tiers .c{background:#EEF3F8;border-radius:6px;padding:12px 16px}
.tiers .c .ap{margin-bottom:3px}
.tiers .big{font-size:23px;line-height:1.15}
.tiers .cl{color:#2A3A52;font-size:13.5px;margin-top:3px}
.tiers .foot{margin-top:14px;color:#5B6B7F;font-size:13.5px}
.tiers.wide{width:%dpx}
.tiers.wide .routes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;height:44px}
.tiers.wide .rt{padding-left:26px}
.tiers.wide .tcols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.tiers.wide .costs{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:20px;margin-top:14px}
.tiers.wide .c{display:flex;gap:14px;align-items:baseline}
.tiers.wide .c .ap{display:none}
.tiers.wide .cl{margin-top:0}
.tiers.narrow{width:%dpx}
.tiers.narrow .rt{height:40px;padding-left:16px}
.tiers.narrow .c{margin-top:10px}
""" % (WIDE, NARROW)
    gate = (f'<div class="gate"><div class="k">{E(GATE[0])}</div><div class="gt">{E(GATE[1])}</div></div>')
    def card(z, n, t, b, style):
        return (f'<div class="tc {style}"><div class="k zl">{E(z)}</div><div class="card"><div class="k tn">{E(n)}</div>'
                f'<div class="h tt">{E(t)}</div><div class="b">{E(b)}</div></div></div>')
    def route(label, sens):
        return (f'<div class="rt {"sensitive" if sens else ""}">{arrow_d("#1B4FE8" if sens else "#8A99AD", 2.5 if sens else 2)}'
                f'<span>{E(label)}</span></div>')
    def cost(amount, words, tag, ap):
        return (f'<div class="c"><div class="k ap">{E(ap)}</div><div class="num big">{E(amount)}</div>'
                f'<div class="cl">{E(words)} <span class="tag">{E(tag)}</span></div></div>')
    if variant == "wide":
        routes = "".join(route(t[4], t[5] == "t1") for t in TIERS)
        cards = "".join(card(t[0], t[1], t[2], t[3], t[5]) for t in TIERS)
        costs = "".join(cost(*c) for c in TIER_COSTS)
        body = (f'{gate}<div class="routes">{routes}</div><div class="tcols">{cards}</div>'
                f'<div class="costs">{costs}</div><div class="foot">{E(TIER_FOOT)}</div>')
    else:
        rows = []
        for i, t in enumerate(TIERS):
            rows.append(route(t[4], t[5] == "t1"))
            rows.append(card(t[0], t[1], t[2], t[3], t[5]))
            if i == 0:
                rows.append(cost(*TIER_COSTS[0]))
        rows.append(cost(*TIER_COSTS[1]))
        body = f'{gate}{"".join(rows)}<div class="foot">{E(TIER_FOOT)}</div>'
    return css, f'<div id="fig" class="tiers {variant}">{body}</div>'

def fig_flow(variant):
    css = """
.flow .stages{position:relative}
.flow .stages::before{content:"";position:absolute;background:#C9D3DF}
.flow .dot{width:30px;height:30px;border-radius:50%%;background:#0C1B33;color:#fff;font-size:14px;display:flex;align-items:center;justify-content:center;position:relative;z-index:1;line-height:1}
.flow .sh{font-size:17px}
.flow .sb{color:#2A3A52;font-size:13.5px;line-height:1.42}
.flow .qa{background:#EEF3F8;border-left:4px solid #0A7F4A;border-radius:4px;padding:12px 16px}
.flow .qa .k{color:#0A7F4A}
.flow .qt{margin-top:4px;color:#0C1B33}
.flow .dec{margin-top:10px;background:#0C1B33;color:#fff;border-radius:4px;padding:14px 16px}
.flow .dec .k{color:#7FA6FF}
.flow .dt{font-size:16px;margin-top:4px}
.flow.wide{width:%dpx}
.flow.wide .stages{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:16px;margin-bottom:22px}
.flow.wide .stages::before{left:15px;right:15px;top:14px;height:2px}
.flow.wide .sh{margin-top:12px}
.flow.wide .sb{margin-top:6px}
.flow.narrow{width:%dpx}
.flow.narrow .stages{margin-bottom:18px}
.flow.narrow .stages::before{left:14px;top:15px;bottom:30px;width:2px}
.flow.narrow .sg{display:grid;grid-template-columns:30px minmax(0,1fr);column-gap:12px;padding-bottom:14px}
.flow.narrow .dot{grid-row:1 / span 2}
.flow.narrow .sh{grid-column:2;padding-top:5px}
.flow.narrow .sb{grid-column:2;margin-top:3px}
""" % (WIDE, NARROW)
    stages = "".join(f'<div class="sg"><div class="dot num">{i}</div><div class="h sh">{E(n)}</div><div class="sb">{E(t)}</div></div>'
                     for i, (n, t) in enumerate(FLOW, 1))
    body = (f'<div class="stages">{stages}</div>'
            f'<div class="qa"><div class="k">{E(FLOW_QA[0])}</div><div class="qt">{E(FLOW_QA[1])}</div></div>'
            f'<div class="dec"><div class="k">{E(FLOW_DEC[0])}</div><div class="dt">{E(FLOW_DEC[1])}</div></div>')
    return css, f'<div id="fig" class="flow {variant}">{body}</div>'

FIGS = {
    "arc": (fig_arc, ARC_TITLE, ARC_DESC),
    "tiers": (fig_tiers, TIERS_TITLE, TIERS_DESC),
    "flow": (fig_flow, FLOW_TITLE, FLOW_DESC),
}

# ---------------------------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------------------------
def page_html(fonts, css, body):
    faces = "\n".join(
        f"@font-face{{font-family:'{fam}';font-weight:{wt};font-style:normal;src:url('{(fonts / rel).resolve().as_uri()}') format('woff2')}}"
        for fam, wt, rel in FACES)
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{faces}\n{BASE_CSS}\n{css}</style></head><body>{body}</body></html>"

def shrink(svg):
    """Write cairo's percentage colours as hex, round every other number to 0.001 (the only
    transforms cairo writes are 0.749178 scales on small inline drawings, which 0.001 keeps),
    and drop the whitespace between tags. pdftocairo writes six decimals, which roughly
    triples the file for no visible gain."""
    def hexcol(m):
        return "#" + "".join(f"{max(0, min(255, round(float(v) * 2.55))):02X}" for v in m.groups())
    def r(m):
        v = round(float(m.group(0)), 3)
        s = f"{v:.3f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    head, sep, rest = svg.partition("</desc>")
    rest = re.sub(r"rgb\(\s*([\d.]+)%,\s*([\d.]+)%,\s*([\d.]+)%\s*\)", hexcol, rest)
    rest = re.sub(r"-?\d+\.\d{4,}", r, rest)
    rest = re.sub(r">\s+<", "><", rest)
    return head + sep + rest

def render(pw_page, fonts, name, variant, out_dir, tmp, preview_dir):
    fn, title, desc = FIGS[name]
    css, body = fn(variant)
    src = tmp / f"{name}-{variant}.html"
    src.write_text(page_html(fonts, css, body), encoding="utf-8")
    pw_page.set_viewport_size({"width": (WIDE if variant == "wide" else NARROW) + 40, "height": 1200})
    pw_page.goto(src.as_uri(), wait_until="load")
    status = pw_page.evaluate("""async () => {
        await Promise.all(Array.from(document.fonts).map(f => f.load().catch(() => null)));
        await document.fonts.ready;
        return Array.from(document.fonts).map(f => f.family + ' ' + f.weight + ' ' + f.status);
    }""")
    bad = [s for s in status if not s.endswith("loaded")]
    assert not bad, f"fonts not loaded: {bad}"
    pw_page.emulate_media(media="print")
    wrapped = pw_page.evaluate("""() => Array.from(document.querySelectorAll('.chip, .k, .rt span, .tag')).filter(e => {
        const r = document.createRange(); r.selectNodeContents(e);
        const tops = new Set(Array.from(r.getClientRects()).filter(x => x.width > 0).map(x => Math.round(x.top)));
        return tops.size > 1; }).map(e => e.textContent)""")
    assert not wrapped, f"{name}-{variant}: labels that must stay on one line wrapped: {wrapped}"
    w, h = pw_page.evaluate("() => { const r = document.getElementById('fig').getBoundingClientRect(); return [r.width, r.height]; }")
    w, h = math.ceil(w), math.ceil(h)
    pdf = tmp / f"{name}-{variant}.pdf"
    pw_page.pdf(path=str(pdf), width=f"{w}px", height=f"{h + 1}px", print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
    pages = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    m = re.search(r"Pages:\s+(\d+)", pages)
    assert m and m.group(1) == "1", f"{name}-{variant}: PDF has {m.group(1) if m else '?'} pages, expected 1"
    raw = tmp / f"{name}-{variant}.raw.svg"
    subprocess.run(["pdftocairo", "-svg", "-f", "1", "-l", "1", str(pdf), str(raw)], check=True)
    svg = raw.read_text(encoding="utf-8")
    assert "<image" not in svg, f"{name}-{variant}: SVG holds a raster image"
    assert "<text" not in svg, f"{name}-{variant}: SVG holds live text"
    head = re.search(r'<svg([^>]*?)width="([\d.]+)(?:pt)?" height="([\d.]+)(?:pt)?"', svg)
    assert head, f"{name}-{variant}: unexpected SVG header"
    wpt, hpt = float(head.group(2)), float(head.group(3))
    assert abs(wpt - w * 0.75) < 1.0, f"{name}-{variant}: SVG width {wpt}pt does not match {w}px"
    svg = svg.replace(head.group(0), f'<svg{head.group(1)}width="{w}" height="{h + 1}" role="img" aria-labelledby="t d"', 1)
    svg = re.sub(r"(<svg[^>]*>)", lambda m: m.group(1) + f'\n<title id="t">{E(title)}</title>\n<desc id="d">{E(desc)}</desc>', svg, count=1)
    svg = shrink(svg)
    out = out_dir / f"fig-{name}-{variant}.svg"
    out.write_text(svg, encoding="utf-8")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()[:16]
    print(f"{out.name}: {w}x{h + 1} px, {out.stat().st_size} B, sha256 {sha}")
    if preview_dir:
        prev = tmp / f"prev-{name}-{variant}.html"
        prev.write_text(f"<!doctype html><html><body style='margin:0;background:#fff'><img src='{out.resolve().as_uri()}' "
                        f"style='display:block;width:{w}px'></body></html>", encoding="utf-8")
        pw_page.emulate_media(media="screen")
        pw_page.set_viewport_size({"width": w, "height": h + 1})
        pw_page.goto(prev.as_uri(), wait_until="load")
        pw_page.screenshot(path=str(preview_dir / f"fig-{name}-{variant}.png"), full_page=True)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--out", default=str(pathlib.Path(__file__).resolve().parent.parent / "assets"))
    ap.add_argument("--preview")
    ap.add_argument("--only", default=",".join(FIGS))
    a = ap.parse_args()
    fonts = pathlib.Path(a.fonts)
    for _, _, rel in FACES:
        assert (fonts / rel).is_file(), f"missing font {fonts / rel}"
    out_dir = pathlib.Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = pathlib.Path(a.preview) if a.preview else None
    if preview_dir: preview_dir.mkdir(parents=True, exist_ok=True)
    names = [n for n in a.only.split(",") if n]
    for n in names:
        assert n in FIGS, f"unknown figure {n}"
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        tmp = pathlib.Path(td)
        b = p.chromium.launch()
        pg = b.new_page(device_scale_factor=2)
        made = [render(pg, fonts, n, v, out_dir, tmp, preview_dir) for n in names for v in ("wide", "narrow")]
        b.close()
    print(f"ok, {len(made)} figures built")

if __name__ == "__main__":
    main()
