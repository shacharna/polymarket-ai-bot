"""
AI Trading Agent - Analysis Only
Provides macro risk scores, news summaries, and market analysis.
NEVER directly triggers or executes trades - only provides recommendations
that the strategy engine + risk manager evaluate independently.
"""
from typing import Dict, List, Optional, Any
from openai import OpenAI
from loguru import logger
from config.settings import get_settings
import json


class AITradingAgent:
    """
    AI agent that provides ANALYSIS ONLY.
    It scores setups and summarizes market context.
    Trade decisions are made by the strategy engine + risk manager.
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = self.settings.openai_model
        self.system_prompt = (
            "You are a market analyst providing research and risk assessments. "
            "You analyze technical setups, news catalysts, volume patterns, and sentiment. "
            "You provide OBJECTIVE analysis with risk scores - you do NOT make trade decisions. "
            "Your role is to score setups and flag risks so that the risk management system "
            "can decide whether to approve a trade. "
            "You must always highlight risks and downside scenarios. "
            "Always respond with valid JSON only, no other text."
        )
        logger.info(f"AI Agent initialized (ANALYSIS ONLY mode, {self.model})")

    def _chat(self, user_prompt, max_tokens=512):
        # type: (str, int) -> str
        """Send a chat completion request"""
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    def analyze_stock(self, symbol, snapshot, bars=None, indicators=None):
        # type: (str, Dict[str, Any], List[Dict[str, Any]], Optional[Dict]) -> Dict[str, Any]
        """
        Analyze a single stock and provide a risk-scored recommendation.
        Returns analysis data - does NOT execute any trade.
        """
        try:
            prompt = self._build_stock_analysis_prompt(symbol, snapshot, bars, indicators)
            # Pi optimization: Reduced from 512 to 350, increased to 400 for indicators
            response_text = self._chat(prompt, max_tokens=400)
            result = self._parse_response(response_text)

            logger.info(
                f"AI analysis for {symbol}: "
                f"bias={result.get('directional_bias', '?')} "
                f"setup_score={result.get('setup_score', 0)}/10 "
                f"risk_score={result.get('risk_score', 0)}/10"
            )
            return result

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return {
                "directional_bias": "NEUTRAL",
                "setup_score": 0,
                "risk_score": 10,
                "reasoning": f"Error: {str(e)}",
                "risks": ["Analysis failed"],
                "news_summary": "",
            }

    def analyze_watchlist(self, snapshots):
        # type: (Dict[str, Dict[str, Any]],) -> List[Dict[str, Any]]
        """
        Batch-scan watchlist and score each stock.
        Returns scored analysis - does NOT trigger trades.
        """
        try:
            prompt = self._build_watchlist_prompt(snapshots)
            # Pi optimization: Reduced from 1024 to 700 tokens
            response_text = self._chat(prompt, max_tokens=700)
            result = self._parse_response(response_text)

            if isinstance(result, list):
                analyses = result
            elif isinstance(result, dict) and "analyses" in result:
                analyses = result["analyses"]
            elif isinstance(result, dict) and "opportunities" in result:
                analyses = result["opportunities"]
            else:
                analyses = [result] if result.get("directional_bias") != "NEUTRAL" else []

            logger.info(f"Watchlist scan scored {len(analyses)} stocks")
            return analyses

        except Exception as e:
            logger.error(f"Error in watchlist scan: {e}")
            return []

    def get_macro_risk_score(self, sector_data=None, news=None):
        # type: (List[Dict], List[Dict]) -> Dict[str, Any]
        """
        Provide overall market risk assessment.
        Returns macro risk score (1-10, 10 = highest risk).
        """
        try:
            sector_text = ""
            if sector_data:
                for s in sector_data:
                    sector_text += f"  {s.get('sector', '?')}: {s.get('change_pct', 0):+.2f}%\n"

            news_text = ""
            if news:
                for n in news[:10]:
                    news_text += f"  - {n.get('title', '')}\n"

            # Pi optimization: Simplified prompt to save input tokens
            prompt = f"""Macro risk assessment:

**Sectors:**
{sector_text or "  No data"}

**News:**
{news_text or "  No news"}

**JSON format:**
{{"macro_risk_score": 1-10, "market_condition": "RISK_ON|NEUTRAL|RISK_OFF|CRISIS", "summary": "brief overview", "key_risks": ["risk1", "risk2"]}}

Score: 1-3=low, 4-6=moderate, 7-8=elevated, 9-10=extreme"""

            # Pi optimization: Reduced from 400 to 250 tokens
            response_text = self._chat(prompt, max_tokens=250)
            return self._parse_response(response_text)

        except Exception as e:
            logger.error(f"Error in macro risk assessment: {e}")
            return {
                "macro_risk_score": 5,
                "market_condition": "NEUTRAL",
                "summary": "Unable to assess",
                "key_risks": [],
            }

    def should_exit_position(self, symbol, entry_price, current_price, pnl_pct, holding_minutes):
        # type: (str, float, float, float, int) -> Dict[str, Any]
        """Analyze whether to exit a position. Returns recommendation only."""
        try:
            # Pi optimization: Simplified prompt
            prompt = f"""Exit analysis for {symbol}:
Entry: ${entry_price:.2f}, Current: ${current_price:.2f}, P&L: {pnl_pct:+.2f}%, Held: {holding_minutes}min

JSON: {{"exit_recommended": true/false, "reasoning": "brief", "urgency": "LOW|MEDIUM|HIGH"}}"""

            # Pi optimization: Reduced from 256 to 180 tokens
            response_text = self._chat(prompt, max_tokens=180)
            return self._parse_response(response_text)

        except Exception as e:
            logger.error(f"Error in exit analysis for {symbol}: {e}")
            return {"exit_recommended": False, "reasoning": str(e), "urgency": "LOW"}

    # ── Prompt Builders ──

    def _build_stock_analysis_prompt(self, symbol, snapshot, bars=None, indicators=None):
        # type: (str, Dict[str, Any], List[Dict[str, Any]], Optional[Dict]) -> str
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

        # Add technical indicators context from Polygon.io
        indicators_text = ""
        if indicators:
            rsi = indicators.get("rsi_14")
            sma50 = indicators.get("sma_50")
            sma200 = indicators.get("sma_200")
            macd = indicators.get("macd", {})

            indicators_text = "\n**Technical Indicators (Polygon.io):**\n"
            if rsi is not None:
                indicators_text += f"  RSI(14): {rsi:.1f}"
                if rsi > 70:
                    indicators_text += " (OVERBOUGHT - reversal risk)"
                elif rsi < 30:
                    indicators_text += " (OVERSOLD - bounce potential)"
                elif 50 <= rsi <= 65:
                    indicators_text += " (healthy momentum zone)"
                indicators_text += "\n"

            if sma50 is not None:
                indicators_text += f"  SMA(50): ${sma50:.2f}"
                if price > sma50:
                    pct_above = ((price - sma50) / sma50) * 100
                    indicators_text += f" (price {pct_above:+.1f}% ABOVE - uptrend)"
                else:
                    pct_below = ((price - sma50) / sma50) * 100
                    indicators_text += f" (price {pct_below:.1f}% BELOW - downtrend)"
                indicators_text += "\n"

            if sma200 is not None:
                indicators_text += f"  SMA(200): ${sma200:.2f}"
                if price > sma200:
                    indicators_text += " (price ABOVE - long-term bullish)"
                else:
                    indicators_text += " (price BELOW - long-term bearish)"
                indicators_text += "\n"

            if macd and macd.get("histogram") is not None:
                hist = macd["histogram"]
                indicators_text += f"  MACD Histogram: {hist:.3f}"
                if hist > 0:
                    indicators_text += " (BULLISH momentum)"
                else:
                    indicators_text += " (BEARISH momentum)"
                indicators_text += "\n"

        # Pi optimization: Simplified prompt, removed verbose rules
        return f"""Risk-scored analysis for {symbol}:

Price: ${price:.2f} | Daily: {change_pct:+.1f}% | Intraday: {intraday_pct:+.1f}% | Gap: {gap_pct:+.1f}%
Range: ${day_low:.2f}-${day_high:.2f} | Vol: {day_volume:,}
{bars_summary}{indicators_text}
JSON: {{
  "directional_bias": "BULLISH|BEARISH|NEUTRAL",
  "setup_score": 1-10,
  "risk_score": 1-10,
  "confidence": 0-100,
  "reasoning": "brief analysis using indicators",
  "risks": ["risk1", "risk2"]
}}

Rules: Use indicators for context. RSI>70=overbought risk, RSI<30=oversold bounce, price above SMA50/200=uptrend. setup_score=quality, risk_score=danger (10=very risky), list 2+ risks"""

    def _build_watchlist_prompt(self, snapshots):
        # type: (Dict[str, Dict[str, Any]],) -> str
        stocks_info = ""
        for symbol, snap in snapshots.items():
            stocks_info += (
                f"- {symbol}: ${snap.get('price', 0):.2f} "
                f"({snap.get('change_pct', 0):+.1f}% daily, "
                f"{snap.get('intraday_change_pct', 0):+.1f}% intraday, "
                f"gap {snap.get('gap_pct', 0):+.1f}%, "
                f"vol {snap.get('day_volume', 0):,})\n"
            )

        # Pi optimization: Simplified prompt
        return f"""Score stocks by quality/risk:

{stocks_info}
JSON: {{"analyses": [
  {{
    "symbol": "TICKER",
    "directional_bias": "BULLISH|BEARISH|NEUTRAL",
    "setup_score": 1-10,
    "risk_score": 1-10,
    "confidence": 0-100,
    "reasoning": "brief",
    "risks": ["risk1"]
  }}
]}}

Score all stocks. 7+=strong, 4-6=moderate, 1-3=weak. List 1+ risk each."""

    def _parse_response(self, response_text):
        # type: (str,) -> Any
        """Parse GPT's JSON response"""
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
            logger.error(f"Failed to parse AI response: {e}")
            return {
                "directional_bias": "NEUTRAL",
                "setup_score": 0,
                "risk_score": 10,
                "confidence": 0,
                "reasoning": "Failed to parse AI response",
                "risks": ["Parse error"],
            }
