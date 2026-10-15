"""
Browser check: switching the theme in ⋮ > Settings recolours every screen at once.

    .venv\\Scripts\\python.exe tools\\backgrounds\\theme_check.py <out_dir> [slug ...]

For each screen: open it in Light, choose Dark in the main menu (Streamlit does NOT
rerun the script for this), then check in the live page that
  * <html data-dm-theme> says "dark",
  * the content panel is dark and the headings / body text / captions on it reach
    4.5:1 contrast,
and the same back in Light. Saves a screenshot of each state and exits 1 on a failure.
This is the case that used to show light text on a light page (theme chosen on the
server, which only hears about a menu switch on the next rerun).
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import screenshot_app as sa  # noqa: E402
from render import find_browser  # noqa: E402

MEASURE_JS = r"""(() => {
  const parse = c => { const n = (c.match(/[\d.]+/g) || []).map(Number); return [n[0], n[1], n[2], n.length > 3 ? n[3] : 1]; };
  const over = (top, base) => top.map((v, i) => i < 3 ? v * top[3] + base[i] * (1 - top[3]) : 1);
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
                     return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const app = document.querySelector('[data-testid="stApp"]');
  const panelEl = document.querySelector('[data-testid="stMainBlockContainer"]');
  const paper = parse(getComputedStyle(app).backgroundColor);
  const panel = over(parse(getComputedStyle(panelEl).backgroundColor), paper);
  // Only text that sits directly on the panel (not on a tab pill, button, message box or card).
  const OWN_BACKGROUND = '[role="tab"], [data-baseweb="tab"], button, [data-testid="stAlert"], .dm-hero, .dm-step, '
                       + '.metric-card, [data-testid="stSidebar"]';
  const check = sel => { const el = [...document.querySelectorAll(sel)].find(e => !e.closest(OWN_BACKGROUND) && e.offsetParent !== null);
    if (!el) return null;
    return Math.round(ratio(parse(getComputedStyle(el).color), panel) * 100) / 100; };
  return JSON.stringify({
    mark: document.documentElement.dataset.dmTheme || null,
    panel_luminance: Math.round(lum(panel) * 1000) / 1000,
    heading: check('[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3'),
    body: check('[data-testid="stMain"] [data-testid="stMarkdownContainer"] p'),
    caption: check('[data-testid="stMain"] [data-testid="stCaptionContainer"]'),
  });
})()"""


def _theme(cdp, name):
    """Pick Light / Dark in the ⋮ menu with real mouse clicks (no rerun happens)."""
    def click(selector):
        pos = cdp.call('Runtime.evaluate', returnByValue=True, expression=f"""(() => {{
            const e = document.querySelector({selector!r}); if (!e) return null;
            const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }})()""")['result'].get('value')
        if not pos:
            raise RuntimeError(f"not found: {selector}")
        for kind in ('mouseMoved', 'mousePressed', 'mouseReleased'):
            cdp.call('Input.dispatchMouseEvent', type=kind, x=pos[0], y=pos[1], button='left', clickCount=1)
    click('[data-testid="stMainMenu"] button, [data-testid="stMainMenu"]')
    time.sleep(1.0)
    click(f'[data-testid="stMainMenuItem-theme-{name}"]')
    time.sleep(0.4)
    for kind in ('keyDown', 'keyUp'):
        cdp.call('Input.dispatchKeyEvent', type=kind, key='Escape')
    time.sleep(0.8)


def _verdict(theme, m):
    problems = []
    if m['mark'] != theme:
        problems.append(f"page marked {m['mark']!r}")
    if (m['panel_luminance'] > 0.5) != (theme == 'light'):
        problems.append(f"panel is {'light' if m['panel_luminance'] > 0.5 else 'dark'}")
    for part in ('heading', 'body', 'caption'):
        if m[part] is not None and m[part] < 4.5:
            problems.append(f"{part} contrast {m[part]}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('out_dir')
    parser.add_argument('slugs', nargs='*')
    args = parser.parse_args()
    sys.path.insert(0, ROOT)
    from ui_components.page_backgrounds import PAGE_SLUGS
    slugs = args.slugs or list(PAGE_SLUGS.values())
    os.makedirs(args.out_dir, exist_ok=True)

    work = tempfile.mkdtemp(prefix='dm_theme_check_')
    wrapper = os.path.join(work, 'shot_app.py')
    with open(wrapper, 'w', encoding='utf-8') as handle:
        handle.write(sa.WRAPPER.format(root=ROOT))
    port, debug_port = sa.free_port(), sa.free_port()
    server = subprocess.Popen(
        [os.path.join(ROOT, '.venv', 'Scripts', 'python.exe'), '-m', 'streamlit', 'run', wrapper,
         '--server.headless', 'true', '--server.port', str(port), '--browser.gatherUsageStats', 'false',
         '--server.fileWatcherType', 'none'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    profile = tempfile.mkdtemp(prefix='dm_theme_profile_')
    chrome = subprocess.Popen(
        [find_browser(), '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
         f'--remote-debugging-port={debug_port}', '--remote-allow-origins=*', f'--user-data-dir={profile}',
         '--window-size=1600,1000', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    failures = 0
    try:
        sa._wait_http(f'http://127.0.0.1:{port}/_stcore/health')
        sa._wait_http(f'http://127.0.0.1:{debug_port}/json/version')
        cdp = sa._Cdp(debug_port)
        cdp.call('Page.enable')
        cdp.call('Emulation.setDeviceMetricsOverride', width=1600, height=1000, deviceScaleFactor=1, mobile=False)
        cdp.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-color-scheme', 'value': 'light'}])
        for slug in slugs:
            cdp.call('Page.navigate', url=f'http://127.0.0.1:{port}/?page={slug}')
            cdp.wait_for(sa.READY_JS, timeout=60)
            time.sleep(1.5)
            _theme(cdp, 'Light')
            for theme in ('dark', 'light'):
                _theme(cdp, theme.capitalize())
                m = json.loads(cdp.call('Runtime.evaluate', expression=MEASURE_JS, returnByValue=True)['result']['value'])
                shot = cdp.call('Page.captureScreenshot', format='png')['data']
                with open(os.path.join(args.out_dir, f"{slug}_{theme}.png"), 'wb') as handle:
                    handle.write(base64.b64decode(shot))
                problems = _verdict(theme, m)
                failures += bool(problems)
                print(f"{'FAIL' if problems else 'ok  '} {slug:20} {theme:5}  heading {m['heading']}  body {m['body']}  "
                      f"caption {m['caption']}  {'; '.join(problems)}")
        cdp.close()
    finally:
        chrome.terminate()
        server.terminate()
        for proc in (chrome, server):
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)
    print(f"\n{len(slugs) * 2 - failures} of {len(slugs) * 2} screen states pass")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
