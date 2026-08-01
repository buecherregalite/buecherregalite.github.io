#!/usr/bin/env python3
"""Drive every interactive widget on every built page and report failures.

Rendering correctly and working correctly are different things: a single null
dereference once killed every quiz and scenario on a page while the screenshot
still looked perfect. This exercises the widgets for real.

    python3 tools/test_widgets.py [lesson-glob]
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT
HARNESS = (Path(__file__).parent / "widget-test.js").read_text(encoding="utf-8")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def run_page(html: Path):
    tmp = html.with_name("_wt_" + html.name)
    src = html.read_text(encoding="utf-8")
    tmp.write_text(src.replace("</body>", f"<script>{HARNESS}</script></body>"),
                   encoding="utf-8")
    try:
        p = subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--allow-file-access-from-files",
             "--virtual-time-budget=20000", "--enable-logging=stderr", "--v=0",
             "--dump-dom", f"file://{tmp}"],
            capture_output=True, text=True, timeout=180)
        err = p.stderr or ""
    finally:
        tmp.unlink(missing_ok=True)

    m = re.search(r"WTEST>>(.*?)<<WTEST", err, re.S)
    results = [r.strip() for r in m.group(1).split(";;")] if m else []

    crashes = [l for l in err.splitlines()
               if "CONSOLE" in l
               and not re.search(r"Failed to load resource|net::ERR|WTEST>>", l)]
    return results, crashes, bool(m)


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else "*.html"
    pages = sorted((OUT / "lessons").glob(pat))
    n_pass = n_fail = 0
    failures, silent = [], []

    for html in pages:
        results, crashes, ran = run_page(html)
        if not ran:
            silent.append((html.name, crashes))
            continue
        for r in results:
            if r.startswith("PASS"):
                n_pass += 1
            else:
                n_fail += 1
                failures.append((html.name, r))
        for c in crashes:
            failures.append((html.name, "JS ERROR " + c.split("CONSOLE:")[-1][:150]))

    print(f"\n{'='*72}\n{n_pass} passed, {n_fail} failed, across {len(pages)} pages")
    if silent:
        print(f"\n{len(silent)} page(s) produced no test output (harness did not finish):")
        for name, cr in silent:
            print(f"  {name}")
            for c in cr[:2]:
                print(f"      {c.split('CONSOLE:')[-1][:150]}")
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for name, r in failures:
            print(f"  {name[:52]:<54} {r}")
    else:
        print("\nAll widget interactions behave correctly.")
    return 1 if (failures or silent) else 0


if __name__ == "__main__":
    sys.exit(main())
