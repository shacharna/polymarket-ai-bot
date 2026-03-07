"""
NotebookLM Agent - Parallel AI Analysis Source

Queries Google NotebookLM notebooks for source-grounded, citation-backed
stock analysis. Runs in parallel with GPT-4o in Phase 2 of the trading pipeline.

Role: Analysis ONLY. Never decides trades. Provides setup_score and risk_score
that are merged with GPT-4o scores in TradingEngine._merge_ai_scores().

Auth: Run once to set up: python scripts/setup_notebooklm_auth.py
      Uses AppData/Local/NotebookLMTrading/ to avoid non-ASCII path issues on
      Windows systems with Hebrew/Unicode usernames (e.g. OneDrive/מסמכים).
"""
import os
import re
import time
import json
from pathlib import Path
from loguru import logger


# Use LOCALAPPDATA (always ASCII on Windows) to avoid Chrome crashing on Hebrew paths.
# Falls back to ~/.notebooklm_trading on Linux/Mac.
_SAFE_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NotebookLMTrading"
_SKILL_STATE_FILE = _SAFE_DATA_DIR / "state.json"
_SKILL_PROFILE_DIR = _SAFE_DATA_DIR / "browser_profile"

# Browser config (mirrors the NotebookLM skill to pass bot detection)
_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
]

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# NotebookLM UI selectors (same as the skill)
_QUERY_INPUT_SELECTORS = [
    "textarea.query-box-input",
    'textarea[aria-label="Input for queries"]',
    'textarea[aria-label="Feld für Anfragen"]',
]

_RESPONSE_SELECTORS = [
    ".to-user-container .message-text-content",
    "[data-message-author='bot']",
    "[data-message-author='assistant']",
]

_CACHE_TTL_SECONDS = 1800  # 30 minutes per symbol


class NotebookLMAgent:
    """
    Queries Google NotebookLM for document-grounded stock analysis.

    Uses headless browser automation (patchright/playwright) with persistent
    Google auth. Reuses auth state from the NotebookLM Claude skill.

    Caches results per symbol for 30 minutes to avoid slow repeated queries.
    All errors return None — engine handles graceful degradation to GPT-4o only.
    """

    def __init__(self, notebook_url):
        # type: (str) -> None
        self.notebook_url = notebook_url
        self._cache = {}  # type: dict  # {symbol: (float, dict)}
        self._state_file = _SKILL_STATE_FILE
        self._profile_dir = _SKILL_PROFILE_DIR
        logger.info(
            "NotebookLMAgent initialized | "
            f"Notebook: {notebook_url[:60]}..."
        )

    def authenticate(self):
        # type: () -> bool
        """
        Check that auth state exists. Interactive login is done by running once:
            python scripts/setup_notebooklm_auth.py

        Returns True if state file exists (does not open a browser).
        """
        if not self._state_file.exists():
            logger.warning(
                "NotebookLM auth state not found at: %s | "
                "Run the NotebookLM skill auth setup: "
                "python auth_manager.py setup",
                self._state_file,
            )
            return False

        age_hours = (time.time() - self._state_file.stat().st_mtime) / 3600
        if age_hours > 168:  # 7 days
            logger.warning(
                "NotebookLM auth state is %.0f hours old — may need refresh",
                age_hours,
            )
        else:
            logger.info(
                "NotebookLM auth state OK (age: %.1f h)", age_hours
            )
        return True

    def analyze_stock(self, symbol, snapshot, strategy_reasoning):
        # type: (str, dict, str) -> dict
        """
        Query NotebookLM notebook for analysis of a stock signal.

        Formats a structured prompt with current price, intraday change,
        and the strategy signal reasoning, then asks the notebook to rate
        setup quality and risk on a 1-10 scale.

        Returns dict: {setup_score, risk_score, reasoning, citations, confidence}
        Returns None on timeout or any error (triggers graceful degradation).
        """
        # Check cache first
        cached = self._get_cached(symbol)
        if cached is not None:
            logger.debug("NotebookLM cache hit for %s", symbol)
            return cached

        price = snapshot.get("price", 0)
        pct_change = snapshot.get(
            "change_pct",
            snapshot.get("daily_change_pct", 0),
        )

        query = (
            f"Based on our research, what is the outlook for {symbol} stock? "
            f"Current price: ${price:.2f}, intraday change: {pct_change:.2f}%. "
            f"Strategy signal: {strategy_reasoning}. "
            f"Rate setup quality 1-10 and risk 1-10."
        )

        logger.info("Querying NotebookLM for %s...", symbol)
        response_text = self._query_notebook(query, timeout=60)

        if response_text is None:
            logger.warning("NotebookLM returned no result for %s", symbol)
            return None

        result = self._parse_scores(response_text)
        result["raw_response"] = response_text[:500]

        self._set_cache(symbol, result)

        logger.info(
            "NotebookLM analysis for %s: setup=%s/10 risk=%s/10",
            symbol,
            result.get("setup_score", "?"),
            result.get("risk_score", "?"),
        )
        return result

    def _query_notebook(self, query, timeout=60):
        # type: (str, int) -> str
        """
        Launch headless browser, navigate to notebook, submit query,
        wait up to `timeout` seconds for a stable response.

        Page load gets a fixed 30s budget; the remaining time is given
        to the response-polling loop (NotebookLM can take 20-40s to reply).

        Returns response text or None on timeout/error.
        """
        try:
            from patchright.sync_api import sync_playwright  # type: ignore
        except ImportError:
            try:
                from playwright.sync_api import sync_playwright  # type: ignore
            except ImportError:
                logger.error(
                    "Neither patchright nor playwright is installed. "
                    "Run: pip install patchright && patchright install chromium"
                )
                return None

        playwright_instance = None
        context = None
        try:
            playwright_instance = sync_playwright().start()

            context = playwright_instance.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir),
                channel="chrome",
                headless=True,
                no_viewport=True,
                ignore_default_args=["--enable-automation"],
                user_agent=_USER_AGENT,
                args=_BROWSER_ARGS,
            )

            # Inject saved session cookies (workaround for Playwright bug #36139)
            self._inject_cookies(context)

            page = context.new_page()
            # Fixed 30s for page load; remaining budget goes to response polling
            page.goto(
                self.notebook_url,
                wait_until="domcontentloaded",
                timeout=30000,
            )
            response_deadline = time.time() + timeout

            # Locate query input box
            query_element = None
            for selector in _QUERY_INPUT_SELECTORS:
                try:
                    query_element = page.wait_for_selector(
                        selector, timeout=10000, state="visible"
                    )
                    if query_element:
                        break
                except Exception:
                    continue

            if not query_element:
                logger.warning("NotebookLM: Could not find query input box")
                return None

            # Dismiss any overlay (file-drop zone, welcome dialog, etc.)
            # that may intercept pointer events on the textarea
            page.keyboard.press("Escape")
            time.sleep(0.5)

            # Click via JavaScript to bypass any residual overlay, then type
            page.evaluate(
                "document.querySelector('textarea.query-box-input').click()"
            )
            time.sleep(0.3)
            page.keyboard.type(query, delay=20)
            page.keyboard.press("Enter")

            # Poll for a stable (non-changing) response
            deadline = response_deadline
            last_text = None
            stable_count = 0

            while time.time() < deadline:
                # Skip while NotebookLM is still generating
                try:
                    thinking = page.query_selector("div.thinking-message")
                    if thinking and thinking.is_visible():
                        time.sleep(1)
                        continue
                except Exception:
                    pass

                for selector in _RESPONSE_SELECTORS:
                    try:
                        elements = page.query_selector_all(selector)
                        if not elements:
                            continue
                        text = elements[-1].inner_text().strip()
                        if not text:
                            continue
                        if text == last_text:
                            stable_count += 1
                            if stable_count >= 3:
                                return text
                        else:
                            stable_count = 0
                            last_text = text
                    except Exception:
                        continue

                time.sleep(1)

            logger.warning("NotebookLM: Timeout waiting for response")
            return None

        except Exception as e:
            logger.warning(f"NotebookLM query error: {e}")
            return None

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

    def _inject_cookies(self, context):
        # type: (object) -> None
        """Inject saved cookies into the browser context."""
        if not self._state_file.exists():
            return
        try:
            with open(str(self._state_file), "r") as f:
                state = json.load(f)
            cookies = state.get("cookies", [])
            if cookies:
                context.add_cookies(cookies)
        except Exception as e:
            logger.warning(f"NotebookLM: Could not inject cookies: {e}")

    def _parse_scores(self, response_text):
        # type: (str) -> dict
        """
        Extract setup_score and risk_score from free-text response using regex.
        Falls back to neutral scores (5/5) if explicit ratings are not found.
        Also extracts source citations and a short reasoning excerpt.
        """
        setup_score = 5
        risk_score = 5
        citations = []
        confidence = 0.5

        # Setup score patterns: "setup: 7/10", "quality 8 out of 10", "setup 7"
        setup_patterns = [
            r"setup[^0-9]{0,20}(\d+)\s*/\s*10",
            r"setup[^0-9]{0,20}(\d+)\s*out\s*of\s*10",
            r"setup[^0-9]{0,15}(\d+)",
            r"quality[^0-9]{0,20}(\d+)\s*/\s*10",
            r"quality[^0-9]{0,15}(\d+)",
        ]
        for pattern in setup_patterns:
            m = re.search(pattern, response_text, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if 1 <= val <= 10:
                    setup_score = val
                    break

        # Risk score patterns: "risk: 4/10", "risk score 6 out of 10", "risk 4"
        risk_patterns = [
            r"risk[^0-9]{0,20}(\d+)\s*/\s*10",
            r"risk[^0-9]{0,20}(\d+)\s*out\s*of\s*10",
            r"risk[^0-9]{0,15}(\d+)",
        ]
        for pattern in risk_patterns:
            m = re.search(pattern, response_text, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if 1 <= val <= 10:
                    risk_score = val
                    break

        # Extract citations — [1] Source title, "Source: ...", "According to ..."
        citation_patterns = [
            r"\[(\d+)\]\s*([^\n]+)",
            r"Source:\s*([^\n]+)",
            r"According to\s+([^\n,\.]+)",
        ]
        for pattern in citation_patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            for match in matches[:3]:
                if isinstance(match, tuple):
                    citations.append(" ".join(match).strip())
                else:
                    citations.append(match.strip())
            if citations:
                break

        # Confidence: higher when we found explicit numeric ratings
        if setup_score != 5 or risk_score != 5:
            confidence = 0.8

        # Reasoning: first 300 chars of the response
        reasoning = response_text[:300].strip() if response_text else ""

        return {
            "setup_score": setup_score,
            "risk_score": risk_score,
            "reasoning": reasoning,
            "citations": citations[:3],
            "confidence": confidence,
        }

    def _get_cached(self, symbol):
        # type: (str) -> dict
        """Return cached analysis if still within TTL, else None."""
        if symbol in self._cache:
            ts, result = self._cache[symbol]
            if time.time() - ts < _CACHE_TTL_SECONDS:
                return result
            del self._cache[symbol]
        return None

    def _set_cache(self, symbol, result):
        # type: (str, dict) -> None
        """Store analysis result for symbol with current timestamp."""
        self._cache[symbol] = (time.time(), result)

    def close(self):
        # type: () -> None
        """Release resources."""
        self._cache.clear()
        logger.info("NotebookLMAgent closed")
