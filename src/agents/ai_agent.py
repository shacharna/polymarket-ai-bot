"""
AI Trading Agent - Aggressive Stock Trading
Uses OpenAI GPT for stock analysis and high-conviction trading decisions
"""
from typing import Dict, List, Optional, Any
from openai import OpenAI
from loguru import logger
from config.settings import get_settings
import json


class AITradingAgent:
    """AI agent for aggressive stock trading decisions using OpenAI GPT"""

    def __init__(self):
        """Initialize AI agent"""
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = self.settings.openai_model
        self.system_prompt = (
            "You are an aggressive stock trader and market analyst seeking alpha. "
            "You analyze technical setups, momentum, catalysts, volume patterns, and "
            "market sentiment to find high-conviction trade opportunities. "
            "You are willing to take calculated risks for outsized returns. "
            "You think like a professional day trader at a prop trading firm. "
            "You prioritize expected value over certainty - a 60% edge is tradeable. "
            "Always respond with valid JSON only, no other text."
        )
        logger.info(f"AI Trading Agent initialized (OpenAI {self.model})")

    def _chat(self, user_prompt: str, max_tokens: int = 512) -> str:
        """Send a chat completion request to OpenAI"""
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    def analyze_stock(
        self,
        symbol: str,
        snapshot: Dict[str, Any],
        bars: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a single stock for trading opportunity

        Args:
            symbol: Stock ticker
            snapshot: Current market snapshot
            bars: Recent OHLCV bars (optional)

        Returns:
            Analysis with action, confidence, reasoning
        """
        try:
            prompt = self._build_stock_analysis_prompt(symbol, snapshot, bars)
            response_text = self._chat(prompt, max_tokens=512)
            result = self._parse_response(response_text)

            logger.info(
                f"AI analysis for {symbol}: {result.get('action', 'HOLD')} "
                f"({result.get('confidence', 0)}% confidence)"
            )
            return result

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return {
                "action": "HOLD",
                "confidence": 0,
                "reasoning": f"Error: {str(e)}",
                "position_size": 0,
            }

    def analyze_watchlist(
        self, snapshots: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Quick-scan entire watchlist for opportunities (batch analysis).
        Uses a single AI call to evaluate all stocks and rank them.

        Args:
            snapshots: Dict of symbol -> snapshot data

        Returns:
            List of top opportunities ranked by conviction
        """
        try:
            prompt = self._build_watchlist_prompt(snapshots)
            response_text = self._chat(prompt, max_tokens=1024)
            result = self._parse_response(response_text)

            # Handle both list and dict responses
            if isinstance(result, list):
                opportunities = result
            elif isinstance(result, dict) and "opportunities" in result:
                opportunities = result["opportunities"]
            else:
                opportunities = [result] if result.get("action") != "HOLD" else []

            logger.info(f"Watchlist scan found {len(opportunities)} opportunities")
            return opportunities

        except Exception as e:
            logger.error(f"Error in watchlist scan: {e}")
            return []

    def should_exit_position(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        pnl_pct: float,
        holding_minutes: int,
    ) -> Dict[str, Any]:
        """Determine if we should exit an existing position"""
        try:
            prompt = f"""Analyze this open position and decide if we should EXIT or HOLD:

**Position:** {symbol}
- Entry: ${entry_price:.2f}
- Current: ${current_price:.2f}
- P&L: {pnl_pct:+.2f}%
- Holding time: {holding_minutes} minutes

**Decision:** Should we take profit, cut losses, or hold?

Respond in JSON:
{{"exit": true/false, "reasoning": "brief explanation", "urgency": "LOW|MEDIUM|HIGH"}}"""

            response_text = self._chat(prompt, max_tokens=256)
            return self._parse_response(response_text)

        except Exception as e:
            logger.error(f"Error in exit analysis for {symbol}: {e}")
            return {"exit": False, "reasoning": str(e), "urgency": "LOW"}

    def _build_stock_analysis_prompt(
        self,
        symbol: str,
        snapshot: Dict[str, Any],
        bars: List[Dict[str, Any]] = None,
    ) -> str:
        """Build prompt for individual stock analysis"""

        price = snapshot.get("price", 0)
        change_pct = snapshot.get("change_pct", 0)
        intraday_pct = snapshot.get("intraday_change_pct", 0)
        gap_pct = snapshot.get("gap_pct", 0)
        day_volume = snapshot.get("day_volume", 0)
        day_high = snapshot.get("day_high", 0)
        day_low = snapshot.get("day_low", 0)

        bars_summary = ""
        if bars and len(bars) >= 5:
            recent = bars[-5:]
            bars_summary = "\n**Recent 15-min bars (last 5):**\n"
            for b in recent:
                bars_summary += (
                    f"  O:{b['open']:.2f} H:{b['high']:.2f} "
                    f"L:{b['low']:.2f} C:{b['close']:.2f} V:{b['volume']:,}\n"
                )

        return f"""Analyze {symbol} for an aggressive intraday trade:

**{symbol} Current Data:**
- Price: ${price:.2f}
- Daily Change: {change_pct:+.1f}%
- Intraday Change: {intraday_pct:+.1f}%
- Gap from prev close: {gap_pct:+.1f}%
- Day Range: ${day_low:.2f} - ${day_high:.2f}
- Volume: {day_volume:,}
{bars_summary}
**Respond in JSON:**
{{"action": "BUY|SELL|HOLD", "confidence": 0-100, "reasoning": "brief explanation", "position_size": 1-10, "stop_loss_pct": -2 to -15, "take_profit_pct": 2 to 30, "hold_duration": "minutes|hours|days"}}

**Aggressive Trading Rules:**
- BUY if strong momentum, breakout, oversold bounce, or catalyst-driven
- SELL if overbought, breakdown, fading momentum, or negative catalyst
- HOLD only if no clear edge exists
- Confidence 55%+ is tradeable. 70%+ is high conviction
- Position 1-4 small, 5-7 medium, 8-10 aggressive
- Think like a prop trader: find the edge and size up"""

    def _build_watchlist_prompt(
        self, snapshots: Dict[str, Dict[str, Any]]
    ) -> str:
        """Build prompt for batch watchlist analysis"""

        stocks_info = ""
        for symbol, snap in snapshots.items():
            stocks_info += (
                f"- {symbol}: ${snap.get('price', 0):.2f} "
                f"({snap.get('change_pct', 0):+.1f}% daily, "
                f"{snap.get('intraday_change_pct', 0):+.1f}% intraday, "
                f"gap {snap.get('gap_pct', 0):+.1f}%, "
                f"vol {snap.get('day_volume', 0):,})\n"
            )

        return f"""Quick-scan these stocks and identify the TOP 3 trading opportunities:

**Watchlist:**
{stocks_info}
**Respond in JSON:**
{{"opportunities": [
  {{"symbol": "TICKER", "action": "BUY|SELL", "confidence": 0-100, "reasoning": "brief", "position_size": 1-10}},
  ...
]}}

**Rules:**
- Only include stocks with 55%+ confidence
- Rank by conviction (highest first)
- Maximum 5 opportunities
- Be aggressive - look for momentum, gaps, volume spikes
- Prefer stocks with clear directional setups"""

    def _parse_response(self, response_text: str) -> Any:
        """Parse GPT's JSON response"""
        try:
            text = response_text.strip()

            # Extract JSON from markdown code blocks if present
            if "```json" in text:
                json_start = text.find("```json") + 7
                json_end = text.find("```", json_start)
                text = text[json_start:json_end].strip()
            elif "```" in text:
                json_start = text.find("```") + 3
                json_end = text.find("```", json_start)
                text = text[json_start:json_end].strip()

            result = json.loads(text)

            # Ensure required fields for single analysis
            if isinstance(result, dict) and "action" in result:
                for field in ["action", "confidence", "reasoning", "position_size"]:
                    if field not in result:
                        result[field] = self._get_default(field)

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.debug(f"Response: {response_text[:200]}")
            return {
                "action": "HOLD",
                "confidence": 0,
                "reasoning": "Failed to parse AI response",
                "position_size": 0,
            }

    def _get_default(self, field: str) -> Any:
        """Get default value for missing field"""
        defaults = {
            "action": "HOLD",
            "confidence": 0,
            "reasoning": "Missing analysis",
            "position_size": 0,
            "stop_loss_pct": -8.0,
            "take_profit_pct": 15.0,
            "hold_duration": "hours",
        }
        return defaults.get(field)
