"""
AI Stock Scanner Agent
Scans Yahoo Finance, news sources, and market data to discover trading opportunities.
Uses real web data + AI to dynamically build a daily watchlist.
"""
from typing import Dict, List, Any, Optional
from openai import OpenAI
from loguru import logger
from config.settings import get_settings
import json
import requests
from datetime import datetime, timedelta

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
    logger.warning("yfinance not installed - run: pip install yfinance")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    logger.warning("beautifulsoup4 not installed - run: pip install beautifulsoup4")


class StockScannerAgent:
    """AI-powered stock scanner that searches the web for trading opportunities"""

    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = self.settings.openai_model

        # Dynamic watchlist built by the scanner
        self.dynamic_watchlist = []  # type: List[str]
        self.scan_results = []  # type: List[Dict[str, Any]]
        self.last_scan_time = None  # type: Optional[datetime]
        self.scan_interval_minutes = 30  # Pi: scan every 30min to reduce load

        logger.info("Stock Scanner Agent initialized (Yahoo Finance + Web + AI)")

    def needs_rescan(self):
        # type: () -> bool
        """Check if we need a fresh scan"""
        if not self.last_scan_time:
            return True
        elapsed = (datetime.now() - self.last_scan_time).total_seconds() / 60
        return elapsed >= self.scan_interval_minutes

    def full_market_scan(self, alpaca_movers=None):
        # type: (Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]
        """
        Full market scan combining multiple data sources:
        1. Yahoo Finance trending/most active
        2. Yahoo Finance gainers/losers (SKIPPED if we have enough from trending+alpaca)
        3. Yahoo Finance news headlines
        4. Alpaca market movers (if provided)
        5. AI analysis to select the best opportunities

        Pi optimizations: Skip expensive API calls if we have enough candidates
        """
        logger.info("Starting full market scan...")

        # Gather data from multiple sources
        yahoo_trending = self._get_yahoo_trending()
        yahoo_news = self._get_yahoo_news()

        # Combine all stock candidates
        all_candidates = {}  # type: Dict[str, Dict[str, Any]]

        # Add Yahoo trending stocks
        for stock in yahoo_trending:
            symbol = stock.get("symbol", "")
            if symbol:
                all_candidates[symbol] = stock

        # Add Alpaca movers
        if alpaca_movers:
            for stock in alpaca_movers:
                symbol = stock.get("symbol", "")
                if symbol and symbol not in all_candidates:
                    all_candidates[symbol] = stock

        # Pi optimization: Only scrape Yahoo gainers/losers if we don't have enough candidates
        # This saves 3 HTTP requests and BeautifulSoup parsing
        if len(all_candidates) < 20:
            logger.info("< 20 candidates, fetching Yahoo gainers/losers...")
            yahoo_gainers = self._get_yahoo_gainers_losers()
            for stock in yahoo_gainers:
                symbol = stock.get("symbol", "")
                if symbol and symbol not in all_candidates:
                    all_candidates[symbol] = stock
                elif symbol:
                    all_candidates[symbol].update(stock)
        else:
            logger.info(f"Skipping Yahoo gainers/losers (already have {len(all_candidates)} candidates)")

        # Also always include the fixed watchlist
        for symbol in self.settings.get_watchlist_symbols():
            if symbol not in all_candidates:
                all_candidates[symbol] = {"symbol": symbol, "source": "watchlist"}

        logger.info(
            f"Collected {len(all_candidates)} unique stocks from all sources"
        )

        # Enrich candidates with Yahoo Finance data
        enriched = self._enrich_with_yfinance(list(all_candidates.values()))

        # Send everything to AI for analysis (no sector data - Pi optimization)
        picks = self._ai_select_stocks(enriched, yahoo_news, [])

        # Update state
        self.dynamic_watchlist = [p.get("symbol", "") for p in picks if p.get("symbol")]
        self.scan_results = picks
        self.last_scan_time = datetime.now()

        logger.info(
            f"AI Scanner selected {len(picks)} stocks: "
            f"{', '.join(self.dynamic_watchlist)}"
        )
        return picks

    def get_dynamic_watchlist(self):
        # type: () -> List[str]
        """Get the current AI-selected watchlist"""
        return self.dynamic_watchlist

    @staticmethod
    def _escape_md(text):
        # type: (str) -> str
        """Escape Telegram Markdown v1 special characters in free-text fields."""
        for ch in ("*", "_", "`", "["):
            text = text.replace(ch, "\\" + ch)
        return text

    def get_scan_summary(self):
        # type: () -> str
        """Get a human-readable scan summary for Telegram"""
        if not self.scan_results:
            return "No scan results yet. Run /scan to scan the market."

        lines = ["*AI Market Scan Results*\n"]
        lines.append(
            f"Scanned at: {self.last_scan_time.strftime('%H:%M:%S') if self.last_scan_time else '?'}"
        )
        lines.append(f"Stocks selected: {len(self.scan_results)}\n")

        for i, pick in enumerate(self.scan_results, 1):
            conv = pick.get("conviction", "?")
            action = pick.get("action", "?")
            symbol = pick.get("symbol", "?")
            setup = self._escape_md(str(pick.get("setup_type", "?")))
            reason = self._escape_md(pick.get("reason", "")[:80])
            lines.append(
                f"{i}. *{symbol}* - {action} ({setup})\n"
                f"   Conviction: {conv}/10\n"
                f"   {reason}"
            )

        return "\n".join(lines)

    # ── Data Sources ──

    def _get_yahoo_trending(self):
        # type: () -> List[Dict[str, Any]]
        """Get trending tickers from Yahoo Finance"""
        results = []
        try:
            url = "https://query1.finance.yahoo.com/v1/finance/trending/US"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                quotes = data.get("finance", {}).get("result", [])
                if quotes:
                    for q in quotes[0].get("quotes", [])[:20]:
                        symbol = q.get("symbol", "")
                        if symbol and symbol.isalpha() and symbol.isupper() and len(symbol) <= 5:
                            results.append({
                                "symbol": symbol,
                                "source": "yahoo_trending",
                            })
                logger.info(f"Yahoo trending: found {len(results)} tickers")
            else:
                logger.debug(f"Yahoo trending API returned {resp.status_code}")

        except Exception as e:
            logger.debug(f"Error fetching Yahoo trending: {e}")

        return results

    def _get_yahoo_gainers_losers(self):
        # type: () -> List[Dict[str, Any]]
        """Get top gainers and losers from Yahoo Finance"""
        results = []

        if not HAS_BS4:
            return results

        try:
            headers = {"User-Agent": "Mozilla/5.0"}

            # Gainers
            for page_url, tag in [
                ("https://finance.yahoo.com/gainers/", "gainer"),
                ("https://finance.yahoo.com/losers/", "loser"),
                ("https://finance.yahoo.com/most-active/", "most_active"),
            ]:
                try:
                    resp = requests.get(page_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")

                        # Look for stock symbols in the page
                        links = soup.find_all("a", {"data-test": "quoteLink"})
                        if not links:
                            # Fallback: try finding links that look like ticker symbols
                            links = soup.find_all(
                                "a", href=lambda h: h and "/quote/" in str(h)
                            )

                        for link in links[:15]:
                            text = link.get_text(strip=True)
                            if (
                                text
                                and text.isalpha()
                                and len(text) <= 5
                                and text.isupper()
                            ):
                                results.append({
                                    "symbol": text,
                                    "source": f"yahoo_{tag}",
                                    "category": tag,
                                })
                except Exception as e:
                    logger.debug(f"Error fetching Yahoo {tag}: {e}")

            logger.info(f"Yahoo gainers/losers/active: found {len(results)} tickers")

        except Exception as e:
            logger.debug(f"Error in Yahoo scraping: {e}")

        return results

    def _get_yahoo_news(self):
        # type: () -> List[Dict[str, str]]
        """Get latest market news headlines from Yahoo Finance"""
        news = []

        try:
            url = "https://query1.finance.yahoo.com/v1/finance/search"
            params = {
                "q": "stock market today",
                "newsCount": 10,
                "quotesCount": 0,
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("news", [])[:10]:
                    title = item.get("title", "")
                    publisher = item.get("publisher", "")
                    if title:
                        news.append({
                            "title": title,
                            "publisher": publisher,
                        })

            logger.info(f"Yahoo news: found {len(news)} headlines")

        except Exception as e:
            logger.debug(f"Error fetching Yahoo news: {e}")

        # Also try to get news for specific hot sectors
        try:
            for query in ["tech stocks", "AI stocks", "earnings today"]:
                resp = requests.get(
                    "https://query1.finance.yahoo.com/v1/finance/search",
                    headers={"User-Agent": "Mozilla/5.0"},
                    params={"q": query, "newsCount": 5, "quotesCount": 0},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("news", [])[:3]:
                        title = item.get("title", "")
                        if title:
                            news.append({
                                "title": title,
                                "publisher": item.get("publisher", ""),
                            })
        except Exception as e:
            logger.debug(f"Error fetching sector news: {e}")

        return news

    def _get_sector_performance(self):
        # type: () -> List[Dict[str, Any]]
        """Get sector ETF performance to understand market context"""
        sectors = []
        sector_etfs = {
            "Technology": "XLK",
            "Healthcare": "XLV",
            "Finance": "XLF",
            "Energy": "XLE",
            "Consumer": "XLY",
            "Industrial": "XLI",
            "S&P 500": "SPY",
            "Nasdaq": "QQQ",
            "Small Cap": "IWM",
        }

        if not HAS_YFINANCE:
            return sectors

        try:
            tickers_str = " ".join(sector_etfs.values())
            data = yf.download(
                tickers_str, period="2d", interval="1d", progress=False
            )

            if data is not None and not data.empty:
                close = data.get("Close")
                if close is not None and len(close) >= 2:
                    for name, etf in sector_etfs.items():
                        try:
                            if etf in close.columns:
                                today = float(close[etf].iloc[-1])
                                yesterday = float(close[etf].iloc[-2])
                                change = ((today - yesterday) / yesterday) * 100
                                sectors.append({
                                    "sector": name,
                                    "etf": etf,
                                    "change_pct": round(change, 2),
                                })
                        except Exception:
                            continue

            logger.info(f"Sector data: {len(sectors)} sectors")

        except Exception as e:
            logger.debug(f"Error fetching sector data: {e}")

        return sectors

    def _enrich_with_yfinance(self, candidates):
        # type: (List[Dict[str, Any]]) -> List[Dict[str, Any]]
        """Enrich stock candidates with Yahoo Finance data (price, volume, etc.)"""
        if not HAS_YFINANCE:
            return candidates

        enriched = []
        symbols = [c.get("symbol", "") for c in candidates if c.get("symbol")]

        # Only enrich stocks that don't already have price data
        needs_data = [s for s in symbols if s]

        if not needs_data:
            return candidates

        try:
            # Batch download - much faster than individual calls
            # Pi optimization: Limit to 30 stocks to reduce memory and CPU
            tickers_str = " ".join(needs_data[:30])
            data = yf.download(
                tickers_str, period="5d", interval="1d", progress=False
            )

            if data is None or data.empty:
                return candidates

            close = data.get("Close")
            volume = data.get("Volume")
            high = data.get("High")
            low = data.get("Low")
            open_prices = data.get("Open")

            for c in candidates:
                symbol = c.get("symbol", "")
                if not symbol:
                    continue

                enriched_stock = dict(c)

                try:
                    if close is not None and symbol in close.columns and len(close) >= 2:
                        price = float(close[symbol].iloc[-1])
                        prev = float(close[symbol].iloc[-2])
                        enriched_stock["price"] = price
                        enriched_stock["prev_close"] = prev
                        enriched_stock["change_pct"] = round(
                            ((price - prev) / prev) * 100, 2
                        ) if prev > 0 else 0

                    if volume is not None and symbol in volume.columns:
                        vol = int(volume[symbol].iloc[-1])
                        avg_vol = int(volume[symbol].mean())
                        enriched_stock["day_volume"] = vol
                        enriched_stock["avg_volume"] = avg_vol
                        enriched_stock["volume_ratio"] = (
                            round(vol / avg_vol, 2) if avg_vol > 0 else 1
                        )

                    if high is not None and symbol in high.columns:
                        enriched_stock["day_high"] = float(high[symbol].iloc[-1])

                    if low is not None and symbol in low.columns:
                        enriched_stock["day_low"] = float(low[symbol].iloc[-1])

                    if open_prices is not None and symbol in open_prices.columns:
                        day_open = float(open_prices[symbol].iloc[-1])
                        enriched_stock["day_open"] = day_open
                        if enriched_stock.get("price") and day_open > 0:
                            enriched_stock["intraday_change_pct"] = round(
                                ((enriched_stock["price"] - day_open) / day_open) * 100,
                                2,
                            )

                except Exception:
                    pass

                # Pi optimization: Skip individual ticker.info and ticker.news calls
                # These are slow and memory-intensive. We have enough data without them.

                enriched.append(enriched_stock)

        except Exception as e:
            logger.debug(f"Error enriching with yfinance: {e}")
            return candidates

        logger.info(f"Enriched {len(enriched)} stocks with Yahoo Finance data")
        return enriched

    # ── AI Analysis ──

    def _ai_select_stocks(
        self,
        candidates,  # type: List[Dict[str, Any]]
        news,  # type: List[Dict[str, str]]
        sectors,  # type: List[Dict[str, Any]]
    ):
        # type: (...) -> List[Dict[str, Any]]
        """Use AI to analyze all data and select the best stocks to trade"""
        if not candidates:
            return []

        try:
            prompt = self._build_full_prompt(candidates, news, sectors)

            # Pi optimization: Reduce max_tokens to save cost and reduce response time
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1200,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
            )

            result = self._parse_response(response.choices[0].message.content)

            if isinstance(result, dict) and "picks" in result:
                picks = result["picks"]
            elif isinstance(result, list):
                picks = result
            else:
                picks = []

            return picks

        except Exception as e:
            logger.error(f"Error in AI stock selection: {e}")
            return []

    def _system_prompt(self):
        # type: () -> str
        return (
            "You are an elite stock trader and market analyst at a top hedge fund. "
            "You have access to real-time market data, news, and sector performance. "
            "Your job is to analyze ALL available data and select the TOP stocks "
            "with the highest probability of making a significant move TODAY. "
            "\n\n"
            "You search for:\n"
            "- Momentum plays with volume confirmation\n"
            "- Breakout setups above key resistance\n"
            "- Oversold bounces (RSI-style reversals)\n"
            "- Gap plays with continuation potential\n"
            "- News/catalyst driven moves\n"
            "- Unusual volume suggesting institutional activity\n"
            "- Sector rotation plays\n"
            "\n"
            "You are AGGRESSIVE and action-oriented. You look for asymmetric "
            "risk/reward setups where the potential upside is 2-3x the downside. "
            "You MUST respond with valid JSON only."
        )

    def _build_full_prompt(self, candidates, news, sectors):
        # type: (List[Dict[str, Any]], List[Dict[str, str]], List[Dict[str, Any]]) -> str
        """Build a comprehensive prompt with all market data"""

        # Market context (Pi: removed sector performance to save tokens)
        sector_text = ""
        if sectors:
            sector_text = "\n**Sector Performance Today:**\n"
            for s in sectors:
                sector_text += f"  {s['sector']} ({s['etf']}): {s['change_pct']:+.2f}%\n"

        # News (Pi optimization: reduced from 15 to 8 headlines)
        news_text = ""
        if news:
            news_text = "\n**Latest Market News:**\n"
            for n in news[:8]:
                news_text += f"  - {n['title']} ({n.get('publisher', '')})\n"

        # Stock data (Pi optimization: reduced from 40 to 25 stocks to save tokens)
        stocks_text = "\n**Stock Candidates:**\n"
        for s in candidates[:25]:
            symbol = s.get("symbol", "?")
            price = s.get("price", 0)
            change = s.get("change_pct", 0)
            volume = s.get("day_volume", 0)
            vol_ratio = s.get("volume_ratio", 0)
            source = s.get("source", "market")
            sector = s.get("sector", "")
            mcap = s.get("market_cap", 0)
            headlines = s.get("recent_headlines", [])

            line = f"- {symbol}"
            if price:
                line += f": ${price:.2f}"
            if change:
                line += f" | Chg: {change:+.1f}%"
            if volume:
                line += f" | Vol: {volume:,}"
            if vol_ratio and vol_ratio > 1.2:
                line += f" | VolRatio: {vol_ratio:.1f}x"
            if sector:
                line += f" | {sector}"
            if mcap:
                if mcap > 1e9:
                    line += f" | MCap: ${mcap/1e9:.1f}B"
                elif mcap > 1e6:
                    line += f" | MCap: ${mcap/1e6:.0f}M"
            if headlines:
                line += f" | News: {headlines[0][:60]}"

            stocks_text += line + "\n"

        # Pi optimization: Reduced from 15 to 10 picks to save tokens
        max_picks = 10
        return f"""Analyze the market and select the TOP {max_picks} stocks to trade TODAY.

{sector_text}
{news_text}
{stocks_text}

**Your Task:**
1. Analyze sector trends to understand what's hot today
2. Cross-reference news with stock movements
3. Identify the BEST setups considering price action, volume, news catalysts, and sector momentum
4. Select {max_picks} stocks ranked by conviction

**Respond in JSON:**
{{"picks": [
  {{
    "symbol": "TICKER",
    "action": "BUY or SELL",
    "reason": "1-2 sentence explanation citing specific data (price, volume, news, sector)",
    "setup_type": "momentum|breakout|reversal|gap|news_catalyst|sector_rotation|volume_spike",
    "conviction": 1-10,
    "priority": 1-{max_picks},
    "entry_strategy": "brief entry plan",
    "risk_note": "key risk to watch"
  }},
  ...
]}}

**Rules:**
- Select up to {max_picks} stocks (fewer if not enough quality setups)
- Conviction 8-10 = must trade, 6-7 = strong, 5 = borderline, below 5 = skip
- Prefer stocks $5-$500 with good liquidity (>100k volume)
- Mix of setup types and both BUY and SELL opportunities
- Reference specific news or data in your reasoning
- Consider sector momentum when making picks"""

    def _parse_response(self, response_text):
        # type: (str) -> Any
        """Parse AI JSON response"""
        try:
            text = response_text.strip()
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()

            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scanner response: {e}")
            return {"picks": []}
