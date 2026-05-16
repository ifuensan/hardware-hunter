#!/usr/bin/env python3
"""Render prd.md → prd.pdf via Python-Markdown + headless Chrome.

Usage: python3 build_prd_pdf.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
SRC = HERE / "prd.md"
HTML = HERE / "prd.html"
PDF = HERE / "prd.pdf"


def strip_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    fm: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def md_to_html(body: str) -> str:
    md = markdown.Markdown(
        extensions=[
            "tables",
            "fenced_code",
            "codehilite",
            "toc",
            "attr_list",
            "sane_lists",
            "smarty",
        ],
        extension_configs={
            "codehilite": {"guess_lang": False, "noclasses": True},
            "toc": {"permalink": False, "toc_depth": "2-3"},
        },
    )
    return md.convert(body)


CSS = r"""
@page {
  size: A4;
  margin: 18mm 16mm 20mm 16mm;
  @bottom-center {
    content: "salvager PRD · " counter(page) " / " counter(pages);
    font: 9pt 'Inter', 'Helvetica Neue', sans-serif;
    color: #888;
  }
}
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  font: 10.5pt/1.5 'Inter', 'Helvetica Neue', Arial, sans-serif;
  color: #1a1a1a;
  margin: 0;
  padding: 0;
  hyphens: auto;
}
h1 {
  font-size: 24pt;
  font-weight: 700;
  margin: 0 0 4mm 0;
  letter-spacing: -0.02em;
  color: #0a0a0a;
}
h2 {
  font-size: 16pt;
  font-weight: 700;
  margin: 12mm 0 4mm 0;
  padding-bottom: 2mm;
  border-bottom: 1.5pt solid #1a1a1a;
  color: #0a0a0a;
  page-break-after: avoid;
  page-break-before: auto;
}
h3 {
  font-size: 12.5pt;
  font-weight: 600;
  margin: 7mm 0 2.5mm 0;
  color: #1a1a1a;
  page-break-after: avoid;
}
h4 {
  font-size: 10.5pt;
  font-weight: 600;
  margin: 5mm 0 1.5mm 0;
  color: #333;
  page-break-after: avoid;
}
p { margin: 0 0 3mm 0; }
ul, ol { margin: 0 0 3mm 0; padding-left: 6mm; }
li { margin-bottom: 1mm; }
li > p { margin-bottom: 1mm; }
strong { color: #0a0a0a; font-weight: 600; }
em { color: #2a2a2a; }
a { color: #0044aa; text-decoration: none; }
code {
  font: 9pt/1.4 'JetBrains Mono', 'Fira Code', 'Menlo', 'Consolas', monospace;
  background: #f4f4f6;
  padding: 0.5pt 2pt;
  border-radius: 2pt;
  color: #5a2a8a;
  word-break: break-word;
}
pre {
  background: #f7f7f9;
  border: 0.5pt solid #e3e3e6;
  border-radius: 3pt;
  padding: 3mm;
  overflow-x: auto;
  page-break-inside: avoid;
  margin: 0 0 4mm 0;
}
pre code {
  background: transparent;
  padding: 0;
  color: #1a1a1a;
  font-size: 8.8pt;
  line-height: 1.45;
  white-space: pre;
}
blockquote {
  margin: 2mm 0 4mm 0;
  padding: 2mm 4mm;
  background: #fafaf6;
  border-left: 2pt solid #b88a00;
  color: #4a3a00;
  font-style: italic;
  page-break-inside: avoid;
}
blockquote p { margin: 0; }
table {
  width: 100%;
  border-collapse: collapse;
  margin: 0 0 4mm 0;
  font-size: 9.5pt;
  page-break-inside: auto;
}
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
th, td {
  border: 0.5pt solid #d4d4d8;
  padding: 1.5mm 2mm;
  text-align: left;
  vertical-align: top;
}
th {
  background: #f0f0f3;
  font-weight: 600;
  color: #0a0a0a;
}
td code, th code {
  font-size: 8.8pt;
}
hr {
  border: none;
  border-top: 0.5pt solid #c4c4c8;
  margin: 6mm 0;
}

/* Title block */
.cover {
  page-break-after: always;
  padding-top: 25mm;
}
.cover h1 {
  font-size: 36pt;
  margin-bottom: 5mm;
}
.cover .subtitle {
  font-size: 14pt;
  color: #555;
  margin-bottom: 30mm;
}
.cover .meta {
  font-size: 10.5pt;
  color: #555;
  line-height: 1.7;
  border-top: 0.5pt solid #c4c4c8;
  padding-top: 5mm;
}
.cover .meta strong { color: #1a1a1a; }
.cover .scope-banner {
  margin-top: 10mm;
  padding: 4mm 5mm;
  background: #fff8e6;
  border-left: 3pt solid #b88a00;
  font-size: 10.5pt;
  color: #4a3a00;
}
.cover .scope-banner strong { color: #4a3a00; }

/* Subtle FR/NFR markers */
li strong:first-child { color: #0a0a0a; }
"""


COVER_HTML = """
<section class="cover">
  <h1>salvager</h1>
  <div class="subtitle">Product Requirements Document — v1</div>
  <div class="meta">
    <p><strong>Author:</strong> {author}<br>
    <strong>Date:</strong> {date}<br>
    <strong>Project type:</strong> cli_tool · self-hosted agent<br>
    <strong>Domain:</strong> general (marketplace agent / homelab tooling)<br>
    <strong>Complexity:</strong> high<br>
    <strong>Release mode:</strong> {release_mode}<br>
    <strong>License:</strong> MIT<br>
    <strong>Repository:</strong> github.com/ifuensan/salvager</p>
  </div>
  <div class="scope-banner">
    <strong>(c3) scope contract — do not relitigate.</strong>
    Personal homelab tool. Wallapop + eBay.es only for v1; multi-marketplace deferred.
    Arbitrage explicitly out of scope and structurally prevented.
  </div>
</section>
"""


def remove_first_h1(body: str) -> str:
    """Drop the leading H1 (title) since the cover page has its own title."""
    return re.sub(r"^# .*\n", "", body, count=1)


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: {SRC} not found", file=sys.stderr)
        return 1
    if shutil.which("google-chrome") is None:
        print("ERROR: google-chrome not found in PATH", file=sys.stderr)
        return 1

    raw = SRC.read_text(encoding="utf-8")
    fm, body = strip_frontmatter(raw)
    body = remove_first_h1(body)

    # Author / date from the leading metadata block in the document body
    author_m = re.search(r"\*\*Author:\*\*\s*(.+)", body)
    date_m = re.search(r"\*\*Date:\*\*\s*(.+)", body)
    author = author_m.group(1).strip() if author_m else "ifuensan"
    date = date_m.group(1).strip() if date_m else fm.get("date", "")
    # Remove the inline author/date block — cover page carries it.
    body = re.sub(r"\*\*Author:\*\*.*\n\*\*Date:\*\*.*\n", "", body, count=1)

    cover = COVER_HTML.format(
        author=author,
        date=date,
        release_mode=fm.get("releaseMode", "phased"),
    )

    html_body = md_to_html(body)

    full_html = (
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<title>salvager PRD</title>"
        f"<style>{CSS}</style>"
        "</head><body>"
        f"{cover}"
        f"{html_body}"
        "</body></html>"
    )
    HTML.write_text(full_html, encoding="utf-8")
    print(f"wrote {HTML}")

    cmd = [
        "google-chrome",
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF}",
        HTML.as_uri(),
    ]
    print("running:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        print("STDOUT:", res.stdout, file=sys.stderr)
        print("STDERR:", res.stderr, file=sys.stderr)
        return res.returncode
    print(f"wrote {PDF} ({PDF.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
