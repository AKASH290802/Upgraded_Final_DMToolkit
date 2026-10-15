"""
Screenshot the running app on each screen (to review the background art in place).

    .venv\\Scripts\\python.exe tools\\backgrounds\\screenshot_app.py <out_dir> [slug ...] [--dark]

Starts `streamlit run` on a free port with a small wrapper that opens the page
named in ?page=<slug>, then captures each page with headless Chrome/Edge.
No org is selected, so nothing connects to Salesforce or SQL Server.
"""
import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from render import find_browser  # noqa: E402

WRAPPER = '''
import os, sys
ROOT = {root!r}
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import streamlit as st
import streamlit_app
# streamlit_app sets the page config at import time, which happens only on the
# first session; set it on every run so each captured page gets the wide layout.
st.set_page_config(page_title="DM Toolkit - Data Migration & Validation", page_icon="🔄",
                   layout="wide", initial_sidebar_state="expanded")
from ui_components.page_backgrounds import PAGE_SLUGS
slug = st.query_params.get("page")
page = next((p for p, s in PAGE_SLUGS.items() if s == slug), None)
if page and st.session_state.get("_shot_page") != slug:
    st.session_state["_shot_page"] = slug
    st.session_state["_pending_nav"] = page
streamlit_app.main()
'''


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('out_dir')
    parser.add_argument('slugs', nargs='*')
    parser.add_argument('--dark', action='store_true')
    parser.add_argument('--width', type=int, default=1600)
    parser.add_argument('--height', type=int, default=1000)
    args = parser.parse_args()

    sys.path.insert(0, ROOT)
    from ui_components.page_backgrounds import PAGE_SLUGS
    slugs = args.slugs or list(PAGE_SLUGS.values())
    os.makedirs(args.out_dir, exist_ok=True)

    work = tempfile.mkdtemp(prefix='dm_shots_')
    wrapper = os.path.join(work, 'shot_app.py')
    with open(wrapper, 'w', encoding='utf-8') as handle:
        handle.write(WRAPPER.format(root=ROOT))
    port = free_port()
    python = os.path.join(ROOT, '.venv', 'Scripts', 'python.exe')
    server = subprocess.Popen(
        [python, '-m', 'streamlit', 'run', wrapper, '--server.headless', 'true', '--server.port', str(port),
         '--browser.gatherUsageStats', 'false', '--server.fileWatcherType', 'none'],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    browser = find_browser()
    debug_port = free_port()
    profile = tempfile.mkdtemp(prefix='dm_shot_profile_')
    chrome = subprocess.Popen(
        [browser, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
         f'--remote-debugging-port={debug_port}', '--remote-allow-origins=*', f'--user-data-dir={profile}',
         f'--window-size={args.width},{args.height}', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_http(f'http://127.0.0.1:{port}/_stcore/health')
        _wait_http(f'http://127.0.0.1:{debug_port}/json/version')
        cdp = _Cdp(debug_port)
        cdp.call('Page.enable')
        cdp.call('Emulation.setDeviceMetricsOverride', width=args.width, height=args.height,
                 deviceScaleFactor=1, mobile=False)
        if args.dark:
            cdp.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-color-scheme', 'value': 'dark'}])
        for slug in slugs:
            out = os.path.join(args.out_dir, f"{slug}{'_dark' if args.dark else ''}.png")
            cdp.call('Page.navigate', url=f'http://127.0.0.1:{port}/?page={slug}')
            ready = cdp.wait_for(READY_JS, timeout=60)
            time.sleep(2.0)   # let fonts, images and the last rerun settle
            shot = cdp.call('Page.captureScreenshot', format='png')
            with open(out, 'wb') as handle:
                handle.write(base64.b64decode(shot['data']))
            print(slug, 'ok' if ready else 'captured before ready', out)
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


READY_JS = """(() => {
  const main = document.querySelector('[data-testid="stMainBlockContainer"], .main .block-container');
  const running = document.querySelector('[data-testid="stStatusWidget"]');
  const skeleton = document.querySelector('[data-testid="stSkeleton"]');
  return !!main && main.innerText.trim().length > 40 && !running && !skeleton;
})()"""


def _wait_http(url: str, attempts: int = 90) -> None:
    for _ in range(attempts):
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"not reachable: {url}")


class _Cdp:
    """Minimal Chrome DevTools Protocol client (websocket-client)."""

    def __init__(self, port: int):
        import websocket
        tabs = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list').read())
        page = next(t for t in tabs if t.get('type') == 'page')
        self.ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=90)
        self.next_id = 0

    def call(self, method: str, **params):
        self.next_id += 1
        self.ws.send(json.dumps({'id': self.next_id, 'method': method, 'params': params}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('id') == self.next_id:
                if 'error' in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get('result', {})

    def wait_for(self, expression: str, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self.call('Runtime.evaluate', expression=expression, returnByValue=True)
            if result.get('result', {}).get('value') is True:
                return True
            time.sleep(0.5)
        return False

    def close(self):
        self.ws.close()


if __name__ == '__main__':
    main()
