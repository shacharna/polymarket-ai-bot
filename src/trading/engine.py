"""
Trading Engine - Strict Risk Management
Coordinates strategies, AI analysis, and risk approval.
KEY RULE: LLM provides analysis only. Risk manager approves every trade.
No trade executes without passing risk_approve().
"""
from typing import Dict, List, Optional, Any, Tuple
from loguru import logger
from datetime import datetime
import time

from src.trading.alpaca_client import AlpacaClient
from src.agents.ai_agent import AITradingAgent
from src.agents.stock_scanner import StockScannerAgent
from src.trading.risk_manager import RiskManager
from src.trading.strategies import StrategyManager
from src.trading.polygon_client import PolygonIndicatorClient
from src.monitoring.logger import log_trade
from src.database import get_supabase_client
from config.settings import get_settings


class TradingEngine:
    """
    Trading engine with strict risk management.

    Flow:
    1. Strategies detect setups (technical signals)
    2. AI scores the setup quality and risk (ANALYSIS ONLY)
    3. Risk manager approves/rejects + sizes the trade
    4. Engine executes only if risk manager says YES
    """

    def __init__(self):
        self.settings = get_settings()

        # Components
        self.alpaca = AlpacaClient()
        self.ai_agent = AITradingAgent()
        self.scanner = StockScannerAgent()
        self.risk_manager = RiskManager()
        self.polygon = PolygonIndicatorClient()
        self.strategy_manager = StrategyManager(polygon_client=self.polygon)

        # NotebookLM agent (optional - disabled by default, opt-in via .env)
        self.notebook_agent = None
        if self.settings.notebooklm_enabled:
            try:
                from src.agents.notebook_lm_agent import NotebookLMAgent
                self.notebook_agent = NotebookLMAgent(
                    self.settings.notebooklm_notebook_url
                )
                self.notebook_agent.authenticate()
                logger.info(
                    "NotebookLM analysis enabled | "
                    f"Weight: {self.settings.notebooklm_weight:.0%}"
                )
            except Exception as e:
                logger.warning(f"NotebookLM agent init failed: {e} — falling back to GPT-4o only")
                self.notebook_agent = None

        # Database (optional - for trade history)
        self.supabase = None
        if self.settings.supabase_url and self.settings.supabase_key:
            try:
                self.supabase = get_supabase_client(
                    self.settings.supabase_url,
                    self.settings.supabase_key
                )
                if self.supabase and self.supabase.enabled:
                    logger.info("Trade history logging to Supabase enabled")
            except Exception as e:
                logger.warning(f"Supabase initialization failed: {e}")
                self.supabase = None

        # State
        self.is_running = False
        self.is_paused = False
        self.trades = []  # type: List[Dict]
        self.start_time = datetime.now()
        self.max_trades_history = 100  # Pi optimization: limit memory usage
        self.bot_version = "1.0.0"  # Track bot version for analytics

        logger.info(
            f"Trading Engine initialized | "
            f"Mode: STRICT RISK | "
            f"Risk/trade: {self.settings.min_risk_per_trade_pct*100:.1f}-{self.settings.risk_per_trade_pct*100:.1f}% | "
            f"Daily limit: {self.settings.daily_loss_limit_pct*100:.1f}% | "
            f"Max drawdown: {self.settings.max_drawdown_pct*100:.0f}% | "
            f"AI role: ANALYSIS ONLY"
        )

    def start(self):
        logger.info("Starting trading engine...")
        self.is_running = True
        self.is_paused = False
        self.run_trading_loop()

    def stop(self):
        logger.info("Stopping trading engine...")
        self.is_running = False

        # Stop NotebookLM agent
        if self.notebook_agent:
            try:
                self.notebook_agent.close()
            except Exception as e:
                logger.error(f"Error closing NotebookLM agent: {e}")

        # Stop Supabase client gracefully
        if self.supabase:
            try:
                self.supabase.stop()
            except Exception as e:
                logger.error(f"Error stopping Supabase client: {e}")

    def pause(self):
        logger.info("Pausing trading...")
        self.is_paused = True

    def resume(self):
        logger.info("Resuming trading + resetting loss pause...")
        self.is_paused = False
        self.risk_manager.reset_consecutive_losses()

    def run_trading_loop(self):
        """Main trading loop (optimized for Raspberry Pi)"""
        loop_count = 0
        import gc  # Garbage collection for memory management

        while self.is_running:
            try:
                loop_count += 1

                if self.is_paused:
                    logger.debug("Trading paused, skipping")
                    time.sleep(30)
                    continue

                # Check market hours
                if self.settings.market_hours_only and not self.alpaca.is_market_open():
                    clock = self.alpaca.get_market_clock()
                    if clock:
                        logger.debug(f"Market closed. Next open: {clock.get('next_open', '?')}")
                    time.sleep(60)
                    continue

                logger.debug(f"--- Trading loop #{loop_count} ---")

                # 1. Get account info
                account = self.alpaca.get_account()
                if not account:
                    logger.error("Failed to get account info")
                    time.sleep(30)
                    continue

                equity = account["equity"]
                buying_power = account["buying_power"]

                # 2. Check risk limits (daily loss + drawdown + consecutive losses)
                can_trade, reason = self.risk_manager.can_trade(equity)
                if not can_trade:
                    logger.warning(f"RISK BLOCK: {reason}")
                    time.sleep(60)
                    continue

                dd_ok, dd_reason = self.risk_manager.check_drawdown(equity)
                if not dd_ok:
                    logger.error(f"RISK BLOCK: {dd_reason}")
                    time.sleep(120)
                    continue

                if self.risk_manager.loss_pause_active:
                    logger.warning(
                        f"RISK BLOCK: Consecutive loss pause active "
                        f"({self.risk_manager.consecutive_losses} losses). "
                        f"Use /resume to reset."
                    )
                    time.sleep(60)
                    continue

                # 3. Get trading symbols
                symbols = self._get_trading_symbols()
                snapshots = self.alpaca.get_watchlist_snapshots(symbols)

                if not snapshots:
                    logger.warning("No snapshot data available")
                    time.sleep(self.settings.scan_interval)
                    continue

                logger.info(f"Scanning {len(snapshots)} stocks")

                # 4. Find strategy signals (technical analysis)
                signals = self._find_strategy_signals(snapshots)

                # 5. Get AI risk scores for signals (ANALYSIS ONLY - no trade decisions)
                scored_signals = self._score_with_ai(signals, snapshots)

                # 6. Submit to risk manager for approval + execution
                if scored_signals:
                    self._execute_approved_trades(scored_signals, equity, buying_power)

                # 7. Manage existing positions
                self.manage_positions()

                # 8. Reconcile bracket order exits (write closed trades to DB)
                self._reconcile_closed_positions()

                # 9. Cleanup memory (important for Raspberry Pi)
                if loop_count % 10 == 0:
                    gc.collect()
                    # Trim trade history to prevent unbounded growth
                    if len(self.trades) > self.max_trades_history:
                        self.trades = self.trades[-self.max_trades_history:]
                        logger.debug(f"Trimmed trade history to {self.max_trades_history} entries")

                time.sleep(self.settings.scan_interval)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                self.stop()
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                time.sleep(30)

        logger.info("Trading engine stopped")

    def _find_strategy_signals(self, snapshots):
        # type: (Dict[str, Dict],) -> List[Dict[str, Any]]
        """
        Phase 1: Pure technical strategy signals.
        No AI involved - just price action, volume, and indicators.
        """
        signals = []

        current_positions = self.alpaca.get_positions()
        held_symbols = {p["symbol"] for p in current_positions}
        available_slots = self.settings.max_concurrent_positions - len(current_positions)

        if available_slots <= 0:
            logger.debug(f"Max positions reached ({len(current_positions)})")
            return []

        for symbol, snapshot in snapshots.items():
            if symbol in held_symbols:
                continue

            # Pi optimization: Reduced from 30 to 20 bars to save memory
            bars = self.alpaca.get_bars(symbol, "15Min", 20)
            strategy_signals = self.strategy_manager.analyze_stock(snapshot, bars)

            if strategy_signals:
                best = self.strategy_manager.get_best_signal(strategy_signals)
                if best and best.get("confidence", 0) >= self.settings.confidence_threshold:
                    signals.append({
                        "symbol": symbol,
                        "snapshot": snapshot,
                        "bars": bars,
                        "strategy_signal": best,
                    })

        logger.info(f"Strategies found {len(signals)} signals")
        return signals

    def _score_with_ai(self, signals, snapshots):
        # type: (List[Dict[str, Any]], Dict[str, Dict]) -> List[Dict[str, Any]]
        """
        Phase 2: AI provides risk scores and analysis for strategy signals.
        AI DOES NOT decide whether to trade - it only scores.
        """
        scored = []

        # Pi optimization: Reduced from 5 to 3 AI calls per cycle to save cost and time
        for sig in signals[:3]:
            symbol = sig["symbol"]
            try:
                # Get technical indicators from Polygon.io (cached, minimal API calls)
                indicators = self.polygon.get_indicators_bundle(symbol)

                # Pass indicators to AI for context-aware analysis
                ai_analysis = self.ai_agent.analyze_stock(
                    symbol, sig["snapshot"], sig["bars"], indicators=indicators
                )

                # NotebookLM parallel analysis (if enabled)
                notebook_analysis = None
                if self.notebook_agent:
                    try:
                        strategy_reasoning = sig.get("strategy_signal", {}).get("reasoning", "")
                        notebook_analysis = self.notebook_agent.analyze_stock(
                            symbol, sig["snapshot"], strategy_reasoning
                        )
                    except Exception as e:
                        logger.warning(f"NotebookLM analysis failed for {symbol}: {e}")

                # Merge scores (or use GPT-4o only if NotebookLM unavailable)
                setup_score, risk_score, merged_reasoning = self._merge_ai_scores(
                    ai_analysis, notebook_analysis
                )
                logger.debug(
                    f"Merged scores for {symbol}: "
                    f"gpt4={ai_analysis.get('setup_score', '?')} "
                    f"notebook={notebook_analysis.get('setup_score', 'N/A') if notebook_analysis else 'N/A'} "
                    f"final={setup_score}"
                )

                # Combine strategy signal with merged AI risk assessment
                sig["ai_analysis"] = ai_analysis
                sig["notebook_analysis"] = notebook_analysis
                sig["setup_score"] = setup_score
                sig["risk_score"] = risk_score
                sig["ai_risks"] = ai_analysis.get("risks", [])

                # Only forward to risk manager if AI doesn't flag elevated risk
                if risk_score <= 6:
                    scored.append(sig)
                else:
                    logger.warning(
                        f"AI flagged HIGH RISK for {symbol} "
                        f"(risk_score={risk_score}/10): {sig['ai_risks']}"
                    )

            except Exception as e:
                logger.error(f"AI scoring failed for {symbol}: {e}")
                # If AI fails, still allow strategy-only trades
                if self.settings.allow_strategy_only_trades:
                    sig["ai_analysis"] = {}
                    sig["setup_score"] = 5
                    sig["risk_score"] = 5
                    sig["ai_risks"] = ["AI analysis unavailable"]
                    scored.append(sig)

        return scored

    def _merge_ai_scores(self, gpt4_analysis, notebook_analysis):
        # type: (Dict, Optional[Dict]) -> Tuple[int, int, str]
        """
        Merge GPT-4o and NotebookLM scores into a single assessment.

        Merging rules:
        - setup_score: weighted average (GPT-4o 60%, NotebookLM 40%)
        - risk_score: max of both — always take the more conservative rating
        - reasoning: combined, with NotebookLM citations appended

        If notebook_analysis is None (timeout / disabled), falls back to
        GPT-4o scores unchanged — bot behaviour is identical to pre-feature.
        """
        gpt4_setup = gpt4_analysis.get("setup_score", 5)
        gpt4_risk = gpt4_analysis.get("risk_score", 5)
        gpt4_reasoning = gpt4_analysis.get("reasoning", "")

        if notebook_analysis is None:
            return gpt4_setup, gpt4_risk, gpt4_reasoning

        w = self.settings.notebooklm_weight  # 0.4 default
        nb_setup = notebook_analysis.get("setup_score", gpt4_setup)
        nb_risk = notebook_analysis.get("risk_score", gpt4_risk)
        nb_reasoning = notebook_analysis.get("reasoning", "")
        nb_citations = notebook_analysis.get("citations", [])

        final_setup = round((gpt4_setup * (1 - w)) + (nb_setup * w))
        final_risk = max(gpt4_risk, nb_risk)  # Conservative: always use worst risk

        citations_str = " | ".join(nb_citations[:2]) if nb_citations else ""
        combined_reasoning = f"GPT-4o: {gpt4_reasoning} | NotebookLM: {nb_reasoning}"
        if citations_str:
            combined_reasoning += f" [Sources: {citations_str}]"

        return final_setup, final_risk, combined_reasoning

    def _execute_approved_trades(self, scored_signals, equity, buying_power):
        # type: (List[Dict[str, Any]], float, float) -> None
        """
        Phase 3: Risk manager approves each trade.
        NO TRADE executes without risk_approve() returning True.
        """
        # Sort by setup quality (best first)
        sorted_signals = sorted(
            scored_signals,
            key=lambda x: x.get("setup_score", 0),
            reverse=True,
        )

        current_positions = self.alpaca.get_positions()
        available_slots = self.settings.max_concurrent_positions - len(current_positions)
        max_this_cycle = min(self.settings.max_trades_per_cycle, available_slots)

        executed = 0
        for sig in sorted_signals:
            if executed >= max_this_cycle:
                break

            symbol = sig["symbol"]
            snapshot = sig["snapshot"]
            price = snapshot.get("price", 0)
            strategy_signal = sig["strategy_signal"]
            action = strategy_signal.get("action", "HOLD")
            confidence = strategy_signal.get("confidence", 0)

            if action == "HOLD" or price <= 0:
                continue

            # Calculate proposed position size
            position_size = self.risk_manager.calculate_position_size(
                confidence=confidence,
                buying_power=buying_power,
                current_equity=equity,
            )

            # ══════════════════════════════════════════════
            # RISK GATE: Every trade MUST pass through here
            # ══════════════════════════════════════════════
            approved, adjusted_size, reason = self.risk_manager.risk_approve(
                equity=equity,
                buying_power=buying_power,
                position_size_usd=position_size,
                price=price,
                symbol=symbol,
            )

            if not approved:
                logger.warning(f"RISK REJECTED {symbol}: {reason}")
                continue

            logger.info(f"RISK APPROVED {symbol}: ${adjusted_size:.2f} | {reason}")

            # Execute the approved trade
            if self._place_trade(symbol, action, adjusted_size, price, sig):
                executed += 1

    def _place_trade(self, symbol, action, position_size_usd, price, signal_data):
        # type: (str, str, float, float, Dict) -> bool
        """Place a single trade (only called after risk approval)"""
        try:
            qty = self.risk_manager.calculate_qty(position_size_usd, price)
            if qty <= 0:
                return False

            # Calculate SL/TP from settings (not from AI)
            sl_pct = self.settings.stop_loss_pct
            tp_pct = self.settings.take_profit_pct

            if action == "BUY":
                stop_loss_price = price * (1 + sl_pct / 100)  # sl_pct is negative
                take_profit_price = price * (1 + tp_pct / 100)
            else:
                stop_loss_price = price * (1 - sl_pct / 100)
                take_profit_price = price * (1 - tp_pct / 100)

            side = "buy" if action == "BUY" else "sell"
            result = self.alpaca.place_bracket_order(
                symbol=symbol,
                qty=qty,
                side=side,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price,
            )

            if result:
                strategy_signal = signal_data.get("strategy_signal", {})
                ai_analysis = signal_data.get("ai_analysis", {})

                trade = {
                    "symbol": symbol,
                    "action": action,
                    "price": price,
                    "qty": qty,
                    "size_usd": qty * price,
                    "confidence": strategy_signal.get("confidence", 0),
                    "strategy": strategy_signal.get("strategy", "unknown"),
                    "setup_score": signal_data.get("setup_score", 0),
                    "risk_score": signal_data.get("risk_score", 0),
                    "ai_risks": signal_data.get("ai_risks", []),
                    "reasoning": strategy_signal.get("reasoning", ""),
                    "order_id": result.get("order_id"),
                    "stop_loss": stop_loss_price,
                    "take_profit": take_profit_price,
                    "timestamp": datetime.now(),
                    "pnl": 0,
                }
                self.trades.append(trade)

                log_trade(
                    action=action,
                    market=symbol,
                    price=price,
                    size=qty * price,
                    confidence=strategy_signal.get("confidence", 0),
                )

                # Log trade to Supabase (async, non-blocking)
                if self.supabase:
                    try:
                        # Get indicators for storage
                        indicators_data = signal_data.get("snapshot", {})

                        # Get AI reasoning
                        ai_reasoning = ai_analysis.get("reasoning", "")
                        if not ai_reasoning and signal_data.get("ai_risks"):
                            ai_reasoning = " | ".join(signal_data.get("ai_risks", []))

                        # Determine if paper trading
                        paper_trading = "paper" in self.settings.alpaca_base_url.lower()

                        # Log trade entry to database (async)
                        self.supabase.log_trade_entry(
                            symbol=symbol,
                            side=side,
                            entry_price=price,
                            quantity=qty,
                            position_value=qty * price,
                            strategy=strategy_signal.get("strategy", "unknown"),
                            confidence=strategy_signal.get("confidence", 0),
                            ai_setup_score=signal_data.get("setup_score"),
                            ai_risk_score=signal_data.get("risk_score"),
                            ai_reasoning=ai_reasoning,
                            indicators=indicators_data,
                            paper_trading=paper_trading,
                            alpaca_order_id=result.get("order_id"),
                            bot_version=self.bot_version,
                        )
                    except Exception as e:
                        # Don't let DB errors affect trading
                        logger.error(f"Error logging trade to Supabase: {e}")

                logger.info(
                    f"EXECUTED {action} {qty}x {symbol} @ ${price:.2f} "
                    f"(${qty*price:.2f}) | "
                    f"Setup: {signal_data.get('setup_score', '?')}/10 | "
                    f"Risk: {signal_data.get('risk_score', '?')}/10 | "
                    f"SL: ${stop_loss_price:.2f} | TP: ${take_profit_price:.2f}"
                )
                return True

        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}")
        return False

    def _reconcile_closed_positions(self):
        # type: () -> None
        """
        Detect bracket orders (take_profit/stop_loss) that closed on Alpaca's side
        and write their exit data back to the DB so trade_performance view populates.

        Called once per scan cycle, after manage_positions().
        """
        if not self.supabase:
            return

        try:
            # Symbols currently open at Alpaca
            open_positions = self.alpaca.get_positions()
            open_symbols = {p["symbol"] for p in open_positions}

            # In-memory trades that have no exit recorded yet
            pending_db_update = [
                t for t in self.trades
                if t.get("symbol") not in open_symbols and not t.get("exit_recorded")
            ]

            if not pending_db_update:
                return

            # Fetch recently filled orders to get fill price + exit reason
            # Use a wide window (30 min) to catch any we may have missed
            filled_orders = self.alpaca.get_filled_orders(since_minutes=30)
            filled_by_symbol = {}
            for fo in filled_orders:
                sym = fo["symbol"]
                # Keep the most recent fill per symbol
                if sym not in filled_by_symbol or fo["filled_at"] > filled_by_symbol[sym]["filled_at"]:
                    filled_by_symbol[sym] = fo

            for trade in pending_db_update:
                symbol = trade["symbol"]
                entry_price = trade.get("price", 0)
                qty = trade.get("qty", 1)

                fill = filled_by_symbol.get(symbol)
                if fill:
                    exit_price = fill["filled_avg_price"]
                    exit_reason = fill["exit_reason"]
                else:
                    # Position closed but no recent fill found — use last known price
                    logger.warning(
                        f"Reconcile: {symbol} no longer open but no fill found — "
                        f"skipping DB update this cycle"
                    )
                    continue

                if entry_price > 0 and exit_price > 0:
                    pnl = (exit_price - entry_price) * qty
                    pnl_pct = (exit_price - entry_price) / entry_price * 100
                else:
                    pnl = 0.0
                    pnl_pct = 0.0

                ok = self.supabase.update_open_trade_exit(
                    symbol=symbol,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    profit_loss=pnl,
                    profit_loss_pct=pnl_pct,
                )
                if ok:
                    trade["exit_recorded"] = True
                    trade["pnl"] = pnl
                    self.risk_manager.record_trade(pnl)
                    logger.info(
                        f"Reconciled {symbol} bracket exit | "
                        f"Reason: {exit_reason} | "
                        f"Exit: ${exit_price:.2f} | P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)"
                    )

        except Exception as e:
            logger.error(f"Error in position reconciliation: {e}")

    def manage_positions(self):
        """Monitor open positions with trailing stops"""
        positions = self.alpaca.get_positions()

        for pos in positions:
            try:
                symbol = pos["symbol"]
                entry_price = pos["avg_entry_price"]
                current_price = pos["current_price"]

                should_trail, trail_reason = self.risk_manager.update_trailing_stop(
                    symbol=symbol,
                    entry_price=entry_price,
                    current_price=current_price,
                    position_type=pos["side"],
                )

                if should_trail:
                    logger.info(f"TRAILING STOP {symbol}: {trail_reason}")
                    if self.alpaca.close_position(symbol):
                        self.risk_manager.clear_trailing_stop(symbol)
                        self.risk_manager.record_trade(pos["unrealized_pl"])
                        self.risk_manager.record_day_trade()
                        logger.info(
                            f"Closed {symbol} via trailing stop | "
                            f"P&L: ${pos['unrealized_pl']:+.2f}"
                        )

                        # Write exit to Supabase so trade_performance view populates
                        if self.supabase:
                            try:
                                ok = self.supabase.update_open_trade_exit(
                                    symbol=symbol,
                                    exit_price=pos["current_price"],
                                    exit_reason="trailing_stop",
                                    profit_loss=pos["unrealized_pl"],
                                    profit_loss_pct=pos["unrealized_plpc"] * 100,
                                )
                                if ok:
                                    # Mark in-memory trade so reconciler skips it
                                    for t in self.trades:
                                        if t.get("symbol") == symbol and not t.get("exit_recorded"):
                                            t["exit_recorded"] = True
                                            break
                            except Exception as e:
                                logger.error(f"Error logging trade exit to Supabase: {e}")

            except Exception as e:
                logger.error(f"Error managing position {pos.get('symbol', '?')}: {e}")

    # ── Dynamic Stock Scanner ──

    def _get_trading_symbols(self):
        # type: () -> List[str]
        """Get symbols: fixed watchlist + AI-scanned"""
        symbols = list(self.settings.get_watchlist_symbols())

        if self.scanner.needs_rescan():
            try:
                logger.info("Running AI market scan...")
                alpaca_movers = self.alpaca.get_most_active_stocks(limit=50)
                picks = self.scanner.full_market_scan(alpaca_movers=alpaca_movers)
                for pick in picks:
                    sym = pick.get("symbol", "")
                    if sym and sym not in symbols:
                        symbols.append(sym)
                logger.info(f"Scanner added {len(picks)} stocks | Total: {len(symbols)}")
            except Exception as e:
                logger.error(f"Scanner error: {e}")
        else:
            for sym in self.scanner.get_dynamic_watchlist():
                if sym not in symbols:
                    symbols.append(sym)

        return symbols

    def run_scan(self):
        # type: () -> List[Dict[str, Any]]
        """Manual scan (Telegram /scan)"""
        try:
            alpaca_movers = self.alpaca.get_most_active_stocks(limit=50)
            return self.scanner.full_market_scan(alpaca_movers=alpaca_movers)
        except Exception as e:
            logger.error(f"Manual scan error: {e}")
            return []

    def get_scan_summary(self):
        # type: () -> str
        return self.scanner.get_scan_summary()

    # ── Telegram API ──

    def get_status(self):
        # type: () -> Dict
        account = self.alpaca.get_account()
        positions = self.alpaca.get_positions()
        clock = self.alpaca.get_market_clock()
        polygon_status = self.polygon.get_rate_limit_status()

        return {
            "status": (
                "Running" if self.is_running and not self.is_paused
                else "Paused" if self.is_paused
                else "Stopped"
            ),
            "equity": account.get("equity", 0) if account else 0,
            "buying_power": account.get("buying_power", 0) if account else 0,
            "day_trade_count": account.get("day_trade_count", 0) if account else 0,
            "open_positions": len(positions),
            "trades_today": self.risk_manager.daily_trades,
            "daily_pnl": self.risk_manager.daily_loss + self.risk_manager.daily_profit,
            "consecutive_losses": self.risk_manager.consecutive_losses,
            "loss_pause": self.risk_manager.loss_pause_active,
            "drawdown_pause": self.risk_manager.drawdown_pause_active,
            "mode": "STRICT RISK",
            "market_open": clock.get("is_open", False) if clock else False,
            "paper": "paper" in self.settings.alpaca_base_url,
            "polygon_requests_used": polygon_status["requests_used"],
            "polygon_requests_remaining": polygon_status["requests_remaining"],
            "last_update": datetime.now().isoformat(),
        }

    def get_balance(self):
        # type: () -> Dict
        account = self.alpaca.get_account()
        if not account:
            return {"error": "Cannot fetch account"}
        return {
            "equity": account["equity"],
            "buying_power": account["buying_power"],
            "cash": account["cash"],
            "portfolio_value": account["portfolio_value"],
            "total_pnl": sum(t.get("pnl", 0) for t in self.trades),
        }

    def get_positions(self):
        # type: () -> List[Dict]
        return self.alpaca.get_positions()

    def get_recent_trades(self, limit=10):
        # type: (int,) -> List[Dict]
        return sorted(
            self.trades,
            key=lambda x: x.get("timestamp", datetime.min),
            reverse=True,
        )[:limit]

    def get_statistics(self):
        # type: () -> Dict
        completed = [t for t in self.trades if t.get("pnl", 0) != 0]
        winners = [t for t in completed if t["pnl"] > 0]
        losers = [t for t in completed if t["pnl"] < 0]

        return {
            "total_trades": len(self.trades),
            "completed_trades": len(completed),
            "winning": len(winners),
            "losing": len(losers),
            "win_rate": (len(winners) / len(completed) * 100) if completed else 0,
            "total_pnl": sum(t.get("pnl", 0) for t in completed),
            "avg_win": sum(t["pnl"] for t in winners) / len(winners) if winners else 0,
            "avg_loss": sum(t["pnl"] for t in losers) / len(losers) if losers else 0,
            "best_trade": max((t["pnl"] for t in completed), default=0),
            "worst_trade": min((t["pnl"] for t in completed), default=0),
            "trades_today": self.risk_manager.daily_trades,
            "pnl_today": self.risk_manager.daily_loss + self.risk_manager.daily_profit,
            "consecutive_losses": self.risk_manager.consecutive_losses,
        }

    def get_strategies(self):
        # type: () -> Dict[str, bool]
        return {
            name: strategy.enabled
            for name, strategy in self.strategy_manager.strategies.items()
        }

    def get_risk_metrics(self):
        # type: () -> Dict
        return self.risk_manager.get_risk_metrics()
