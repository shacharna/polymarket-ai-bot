"""Diagnostic: submit a short query and dump response selectors."""
import os, json, time, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from config.settings import get_settings
s = get_settings()
from pathlib import Path
from patchright.sync_api import sync_playwright  # type: ignore

PROFILE = Path(os.environ['LOCALAPPDATA']) / 'NotebookLMTrading' / 'browser_profile'
STATE   = Path(os.environ['LOCALAPPDATA']) / 'NotebookLMTrading' / 'state.json'
ARGS = ['--disable-blink-features=AutomationControlled','--disable-dev-shm-usage',
        '--no-sandbox','--no-first-run','--no-default-browser-check']

pw = sync_playwright().start()
ctx = pw.chromium.launch_persistent_context(
    user_data_dir=str(PROFILE), channel='chrome', headless=True,
    no_viewport=True, ignore_default_args=['--enable-automation'],
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    args=ARGS,
)
with open(str(STATE)) as f:
    state = json.load(f)
ctx.add_cookies(state.get('cookies', []))

page = ctx.new_page()
page.goto(s.notebooklm_notebook_url, wait_until='domcontentloaded', timeout=30000)

page.keyboard.press('Escape')
time.sleep(0.5)
page.evaluate("document.querySelector('textarea.query-box-input').click()")
time.sleep(0.3)
page.keyboard.type('What sources do you have? List them briefly.', delay=20)
page.keyboard.press('Enter')

print('Waiting 50s for response...')
time.sleep(50)

print()
print('=== Checking selectors ===')
for sel in [
    '.to-user-container .message-text-content',
    '[data-message-author]',
    '.message-text-content',
    '.response-container',
    'message-turn',
    '.chat-message',
    '[role="article"]',
    '.query-response',
    '.model-response',
    '.response-text',
    '.answer',
]:
    els = page.query_selector_all(sel)
    if els:
        txt = els[-1].inner_text()[:120].replace('\n', ' ')
        print(f'FOUND {len(els)}x [{sel}]: {txt!r}')
    else:
        print(f'  none  [{sel}]')

print()
print('=== Classes containing message/response/answer ===')
classes = page.evaluate("""(function() {
    var seen = {};
    document.querySelectorAll('*').forEach(function(el) {
        el.className.toString().split(' ').forEach(function(c) {
            if (c.length > 3 && (c.indexOf('message') >= 0 || c.indexOf('response') >= 0 || c.indexOf('answer') >= 0))
                seen[c] = 1;
        });
    });
    return Object.keys(seen);
})()""")
for c in sorted(classes)[:40]:
    print(' ', c)

print()
print('=== Body text (first 800 chars) ===')
body = page.inner_text('body')
print(body[:800])

ctx.close()
pw.stop()
