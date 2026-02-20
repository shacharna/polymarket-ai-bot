"""
AI Stock Scanner Agent
Scans the entire market to discover the best trading opportunities.
Uses market data + AI to dynamically build a daily watchlist.
"""
from typing import Dict, List, Any
from openai import OpenAI
from loguru import logger
from config.settings import get_settings
import json


class StockScannerAgent:
    """AI-powered stock scanner that discovers trading opportunities across the market"""

    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = self.settings.openai_model

        # Dynamic watchlist built by the scanner
        self.dynamic_watchlist: List[str] = []
        self.scan_results: List[Dict[str, Any]] = []

        logger.info("Stock Scanner Agent initialized")

    def scan_and_select(
        self, movers: List[Dict[str, Any]], max_picks: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Analyze market movers with AI and select the best stocks to trade today.

        Args:
            movers: List of active stocks from Alpaca (sorted by biggest moves)
            max_picks: Maximum number of stocks to select

        Returns:
            List of selected stocks with AI reasoning
        """
        if not movers:
            logger.warning("No movers data to scan")
            return []

        try:
            # Phase 1: Pre-filter to top 30 movers for AI analysis
            candidates = movers[:30]

            # Phase 2: AI selects the best opportunities
            prompt = self._build_scanner_prompt(candidates, max_picks)

            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1500,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
            )

            result = self._parse_response(response.choices[0].message.content)

            # Extract selected stocks
            if isinstance(result, dict) and "picks" in result:
                picks = result["picks"]
            elif isinstance(result, list):
                picks = result
            else:
                picks = []

            # Update dynamic watchlist
            self.dynamic_watchlist = [p.get("symbol", "") for p in picks if p.get("symbol")]
            self.scan_results = picks

            logger.info(
                f"Scanner selected {len(picks)} stocks: "
                f"{', '.join(self.dynamic_watchlist)}"
            )
            return picks

        except Exception as e:
            logger.error(f"Error in AI stock scan: {e}")
            return []

    def get_dynamic_watchlist(self) -> List[str]:
        """Get the current AI-selected watchlist"""
        return self.dynamic_watchlist

    def _system_prompt(self) -> str:
        return (
            "You are an elite stock scanner at a quantitative trading firm. "
            "Your job is to analyze market data and select the TOP stocks with "
            "the highest probability of making a significant move today. "
            "You look for: momentum plays, breakout setups, oversold bounces, "
            "gap plays, unusual volume, and catalyst-driven moves. "
            "You are aggressive and action-oriented. "
            "You MUST respond with valid JSON only."
        )

    def _build_scanner_prompt(
        self, candidates: List[Dict[str, Any]], max_picks: int
    ) -> str:
        stocks_data = ""
        for s in candidates:
            stocks_data += (
                f"- {s['symbol']}: ${s['price']:.2f} | "
                f"Change: {s['change_pct']:+.1f}% | "
                f"Gap: {s['gap_pct']:+.1f}% | "
                f"Intraday: {s['intraday_change_pct']:+.1f}% | "
                f"Vol: {s['day_volume']:,} | "
                f"Range: ${s['day_low']:.2f}-${s['day_high']:.2f}\n"
            )

        return f"""Scan these {len(candidates)} stocks and select the TOP {max_picks} best trading opportunities for today.

**Market Movers:**
{stocks_data}

**Selection Criteria (aggressive trader mindset):**
1. Strong momentum with volume confirmation
2. Clean breakout above resistance or breakdown below support
3. Oversold bounce candidates (down big but showing reversal signs)
4. Gap plays with continuation potential
5. Unusual volume suggesting institutional activity
6. Prefer stocks $5-$500 with high liquidity

**Respond in JSON:**
{{"picks": [
  {{
    "symbol": "TICKER",
    "action": "BUY|SELL",
    "reason": "brief 1-line explanation",
    "setup_type": "momentum|breakout|reversal|gap|volume_spike",
    "conviction": 1-10,
    "priority": 1-{max_picks}
  }},
  ...
]}}

**Rules:**
- Select exactly {max_picks} stocks (or fewer if not enough good setups)
- Rank by conviction (highest first)
- Mix of setups: don't pick all momentum or all reversals
- Include both BUY and SELL opportunities
- Conviction 7+ = high priority, 5-6 = medium, below 5 = skip"""

    def _parse_response(self, response_text: str) -> Any:
        """Parse AI JSON response"""
        try:
            text = response_text.strip()
            if "```json" in text:
                text = text[text.find("```json") + 7:text.find("```", text.find("```json") + 7)].strip()
            elif "```" in text:
                text = text[text.find("```") + 3:text.find("```", text.find("```") + 3)].strip()

            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scanner response: {e}")
            return {"picks": []}
