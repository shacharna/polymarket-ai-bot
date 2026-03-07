"""
NotebookLM Auth Setup for Trading Bot

Opens a Chrome window so you can log in to Google once.
After login, saves session cookies to AppData/Local/NotebookLMTrading/
so the trading bot can query NotebookLM without re-authenticating.

Why AppData instead of the project folder?
  The project lives in OneDrive/מסמכים (Hebrew path).
  Chrome refuses to use --user-data-dir with non-ASCII characters.
  AppData/Local is always ASCII-safe on Windows.

Usage:
    python scripts/setup_notebooklm_auth.py

After running, add to .env:
    NOTEBOOKLM_ENABLED=true
    NOTEBOOKLM_NOTEBOOK_URL=https://notebooklm.google.com/notebook/your-id
"""
import os
import sys
import json
import time
import re
from pathlib import Path

# Safe ASCII path for browser profile
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NotebookLMTrading"
PROFILE_DIR = DATA_DIR / "browser_profile"
STATE_FILE = DATA_DIR / "state.json"

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def setup_auth(timeout_minutes=10):
    # type: (int) -> bool
    """Open Chrome for interactive Google login, save session state."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Auth data directory : {DATA_DIR}")
    print(f"Browser profile     : {PROFILE_DIR}")
    print(f"State file          : {STATE_FILE}")
    print()

    try:
        from patchright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError:
            print("ERROR: patchright not installed.")
            print("Run: pip install patchright && patchright install chromium")
            return False

    playwright_instance = None
    context = None
    try:
        playwright_instance = sync_playwright().start()

        print("Opening Chrome... (NOT headless - you need to log in)")
        context = playwright_instance.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            channel="chrome",
            headless=False,   # Visible so you can log in
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
            user_agent=USER_AGENT,
            args=BROWSER_ARGS,
        )

        page = context.new_page()
        page.goto("https://notebooklm.google.com", wait_until="domcontentloaded")

        # Already logged in?
        if ("notebooklm.google.com" in page.url and
                "accounts.google.com" not in page.url):
            print("Already authenticated!")
            _save_state(context)
            return True

        print()
        print("=" * 55)
        print("  Please log in to your Google account in Chrome.")
        print(f"  Waiting up to {timeout_minutes} minutes...")
        print("=" * 55)

        timeout_ms = int(timeout_minutes * 60 * 1000)
        page.wait_for_url(
            re.compile(r"^https://notebooklm\.google\.com/"),
            timeout=timeout_ms,
        )

        print()
        print("Login successful! Saving session...")
        _save_state(context)
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False

    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        if playwright_instance:
            try:
                playwright_instance.stop()
            except Exception:
                pass


def _save_state(context):
    # type: (object) -> None
    """Save browser storage state (cookies + localStorage) to state.json."""
    context.storage_state(path=str(STATE_FILE))
    size = STATE_FILE.stat().st_size
    print(f"Saved state ({size} bytes) -> {STATE_FILE}")


def check_status():
    # type: () -> None
    """Print current auth state."""
    if STATE_FILE.exists():
        age_hours = (time.time() - STATE_FILE.stat().st_mtime) / 3600
        size = STATE_FILE.stat().st_size
        try:
            with open(str(STATE_FILE)) as f:
                state = json.load(f)
            n_cookies = len(state.get("cookies", []))
        except Exception:
            n_cookies = "?"
        print(f"Auth state  : FOUND")
        print(f"Location    : {STATE_FILE}")
        print(f"Age         : {age_hours:.1f} hours")
        print(f"Size        : {size} bytes")
        print(f"Cookies     : {n_cookies}")
        if age_hours > 168:
            print("WARNING: State is over 7 days old - may need refresh")
    else:
        print("Auth state  : NOT FOUND")
        print(f"Expected at : {STATE_FILE}")
        print("Run this script without arguments to set up auth.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        check_status()
    else:
        print("NotebookLM Auth Setup")
        print("=" * 55)
        ok = setup_auth(timeout_minutes=10)
        if ok:
            print()
            print("Auth setup complete!")
            print("You can now start the bot with NOTEBOOKLM_ENABLED=true")
        else:
            print()
            print("Auth setup failed. Check errors above.")
            sys.exit(1)
