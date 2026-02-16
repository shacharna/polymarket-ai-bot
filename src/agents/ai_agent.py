"""
AI Trading Agent using Anthropic Claude
Makes trading decisions based on market data and news
"""
from typing import Dict, List, Optional, Any
from anthropic import Anthropic
from loguru import logger
from config.settings import get_settings
import json


class AITradingAgent:
    """AI agent for making trading decisions using Claude"""

    def __init__(self):
        """Initialize AI agent"""
        self.settings = get_settings()
        self.client = Anthropic(api_key=self.settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"  # Latest Claude model
        logger.info("AI Trading Agent initialized")

    def analyze_market(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a market and make trading recommendation

        Args:
            market_data: Market information including price, volume, etc.

        Returns:
            Dictionary with recommendation, confidence, reasoning
        """
        try:
            prompt = self._build_market_analysis_prompt(market_data)

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parse response
            result = self._parse_analysis_response(response.content[0].text)

            logger.info(
                f"Market analysis complete: {result.get('action', 'HOLD')} "
                f"with {result.get('confidence', 0)}% confidence"
            )

            return result

        except Exception as e:
            logger.error(f"Error in market analysis: {e}")
            return {
                "action": "HOLD",
                "confidence": 0,
                "reasoning": f"Error: {str(e)}",
                "position_size": 0
            }

    def _build_market_analysis_prompt(self, market_data: Dict[str, Any]) -> str:
        """Build prompt for market analysis"""

        market_question = market_data.get('question', 'Unknown')
        current_price = market_data.get('price', 0)
        volume = market_data.get('volume', 0)
        liquidity = market_data.get('liquidity', 0)
        end_date = market_data.get('end_date', 'Unknown')
        description = market_data.get('description', '')

        prompt = f"""You are an expert prediction market trader analyzing a Polymarket opportunity.

**Market Details:**
- Question: {market_question}
- Current Price: ${current_price:.4f} (probability: {current_price*100:.1f}%)
- 24h Volume: ${volume:,.2f}
- Liquidity: ${liquidity:,.2f}
- Resolution Date: {end_date}
- Description: {description}

**Your Task:**
Analyze this market and provide a trading recommendation.

**Analysis Framework:**
1. **Market Efficiency**: Is the current price accurate based on available information?
2. **Expected Value**: Calculate if there's positive expected value
3. **Risk Assessment**: What could go wrong?
4. **Liquidity**: Can we enter/exit easily?
5. **Time Horizon**: How long until resolution?

**Respond in JSON format:**
{{
    "action": "BUY|SELL|HOLD",
    "confidence": 0-100,
    "reasoning": "Brief explanation of your analysis",
    "position_size": 0-10,
    "stop_loss": 0.0-1.0,
    "take_profit": 0.0-1.0,
    "risk_factors": ["factor1", "factor2"]
}}

**Guidelines:**
- BUY if you believe actual probability > current price
- SELL if you believe actual probability < current price
- HOLD if market is fairly priced or too risky
- Confidence: 0-40 (low), 41-70 (medium), 71-100 (high)
- Position size: 1-3 (small), 4-7 (medium), 8-10 (large)
- Be conservative - only recommend trades with clear edge
- Consider only trading markets with >70% confidence

Provide your analysis:"""

        return prompt

    def _parse_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's JSON response"""
        try:
            # Try to extract JSON from response
            # Claude might wrap it in markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                # Assume entire response is JSON
                json_text = response_text.strip()

            result = json.loads(json_text)

            # Validate required fields
            required_fields = ["action", "confidence", "reasoning", "position_size"]
            for field in required_fields:
                if field not in result:
                    logger.warning(f"Missing field {field} in AI response")
                    result[field] = self._get_default_value(field)

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")

            return {
                "action": "HOLD",
                "confidence": 0,
                "reasoning": "Failed to parse AI response",
                "position_size": 0
            }

    def _get_default_value(self, field: str) -> Any:
        """Get default value for missing field"""
        defaults = {
            "action": "HOLD",
            "confidence": 0,
            "reasoning": "Missing analysis",
            "position_size": 0,
            "stop_loss": 0.0,
            "take_profit": 1.0,
            "risk_factors": []
        }
        return defaults.get(field)

    def analyze_news(self, news_text: str, market_question: str) -> Dict[str, Any]:
        """
        Analyze how news affects a specific market

        Args:
            news_text: News article or headline
            market_question: The market question to analyze against

        Returns:
            Impact analysis
        """
        try:
            prompt = f"""You are analyzing breaking news for its impact on a prediction market.

**Market Question:** {market_question}

**News:**
{news_text}

**Task:** Determine if this news affects the market and how.

**Respond in JSON:**
{{
    "relevant": true/false,
    "impact": "POSITIVE|NEGATIVE|NEUTRAL",
    "magnitude": 0-10,
    "reasoning": "Brief explanation",
    "recommended_action": "BUY|SELL|HOLD",
    "urgency": "LOW|MEDIUM|HIGH"
}}

Analysis:"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            result = self._parse_analysis_response(response.content[0].text)
            return result

        except Exception as e:
            logger.error(f"Error analyzing news: {e}")
            return {
                "relevant": False,
                "impact": "NEUTRAL",
                "magnitude": 0,
                "reasoning": str(e)
            }

    def should_exit_position(
        self,
        entry_price: float,
        current_price: float,
        holding_period_hours: int,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine if we should exit an existing position

        Args:
            entry_price: Price we entered at
            current_price: Current market price
            holding_period_hours: How long we've held the position
            market_data: Current market information

        Returns:
            Exit recommendation
        """
        try:
            profit_loss_pct = ((current_price - entry_price) / entry_price) * 100

            prompt = f"""You are managing an open position in a prediction market.

**Position Details:**
- Entry Price: ${entry_price:.4f}
- Current Price: ${current_price:.4f}
- P&L: {profit_loss_pct:+.2f}%
- Holding Period: {holding_period_hours} hours

**Market Context:**
- Question: {market_data.get('question', 'Unknown')}
- Liquidity: ${market_data.get('liquidity', 0):,.2f}
- Time to Resolution: {market_data.get('hours_to_resolution', 'Unknown')} hours

**Decision:** Should we exit this position now?

**Respond in JSON:**
{{
    "exit": true/false,
    "reasoning": "Brief explanation",
    "urgency": "LOW|MEDIUM|HIGH"
}}

**Consider:**
- Is profit target reached?
- Is there better opportunity elsewhere?
- Has the market thesis changed?
- Is resolution approaching?

Analysis:"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            result = self._parse_analysis_response(response.content[0].text)
            return result

        except Exception as e:
            logger.error(f"Error in exit analysis: {e}")
            return {
                "exit": False,
                "reasoning": str(e),
                "urgency": "LOW"
            }
