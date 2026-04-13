"""
Web Dashboard API server.
FastAPI app exposing TradingEngine data and controls via REST.
Runs in a daemon thread alongside the trading engine.
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

app = FastAPI(title="Trading Bot Dashboard", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Module-level references set by init_server()
_engine = None       # type: Optional[Any]
_analytics = None    # type: Optional[Any]
_start_time = None   # type: Optional[datetime]

# Close-all confirmation state
_closeall_token = None          # type: Optional[str]
_closeall_token_expiry = None   # type: Optional[datetime]


def init_server(engine, analytics):
    # type: (Any, Any) -> None
    """Store engine/analytics references and record start time."""
    global _engine, _analytics, _start_time
    _engine = engine
    _analytics = analytics
    _start_time = datetime.utcnow()


def _safe_json(obj):
    # type: (Any) -> Any
    """Recursively convert non-JSON-serializable types (datetime, etc.)."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_json(i) for i in obj]
    try:
        import math
        if isinstance(obj, float) and math.isnan(obj):
            return None
    except Exception:
        pass
    return obj


def _ok(data):
    # type: (Any) -> JSONResponse
    return JSONResponse(content=_safe_json(data))


def _error(msg, status=500):
    # type: (str, int) -> JSONResponse
    return JSONResponse(content={"error": msg}, status_code=status)


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    uptime = int((datetime.utcnow() - _start_time).total_seconds()) if _start_time else 0
    return _ok({"ok": True, "uptime_seconds": uptime})


# ── Live data ────────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    if not _engine:
        return _error("engine not available", 503)
    try:
        return _ok(_engine.get_status())
    except Exception as e:
        logger.error(f"Dashboard /api/status error: {e}")
        return _error(str(e))


@app.get("/api/balance")
def get_balance():
    if not _engine:
        return _error("engine not available", 503)
    try:
        return _ok(_engine.get_balance())
    except Exception as e:
        logger.error(f"Dashboard /api/balance error: {e}")
        return _error(str(e))


@app.get("/api/positions")
def get_positions():
    if not _engine:
        return _error("engine not available", 503)
    try:
        return _ok(_engine.get_positions())
    except Exception as e:
        logger.error(f"Dashboard /api/positions error: {e}")
        return _error(str(e))


@app.get("/api/trades")
def get_trades():
    if not _engine:
        return _error("engine not available", 503)
    try:
        return _ok(_engine.get_recent_trades(limit=50))
    except Exception as e:
        logger.error(f"Dashboard /api/trades error: {e}")
        return _error(str(e))


@app.get("/api/statistics")
def get_statistics():
    if not _engine:
        return _error("engine not available", 503)
    try:
        return _ok(_engine.get_statistics())
    except Exception as e:
        logger.error(f"Dashboard /api/statistics error: {e}")
        return _error(str(e))


@app.get("/api/risk")
def get_risk():
    if not _engine:
        return _error("engine not available", 503)
    try:
        return _ok(_engine.get_risk_metrics())
    except Exception as e:
        logger.error(f"Dashboard /api/risk error: {e}")
        return _error(str(e))


@app.post("/api/positions/{symbol}/close")
def close_position(symbol):
    # type: (str) -> JSONResponse
    """Close a single position by symbol."""
    if not _engine:
        return _error("engine not available", 503)
    try:
        positions = _engine.get_positions()
        pos = next((p for p in positions if p["symbol"] == symbol), None)
        if not pos:
            return _error(f"No open position found for {symbol}", 404)

        success = _engine.alpaca.close_position(symbol)
        if success:
            logger.warning(f"Dashboard: closed position {symbol}")
            return _ok({"ok": True, "symbol": symbol})
        else:
            return _error(f"Failed to close {symbol} — check logs", 500)
    except Exception as e:
        logger.error(f"Dashboard /api/positions/{symbol}/close error: {e}")
        return _error(str(e))


@app.get("/api/strategies")
def get_strategies():
    if not _engine:
        return _error("engine not available", 503)
    try:
        return _ok(_engine.get_strategies())
    except Exception as e:
        logger.error(f"Dashboard /api/strategies error: {e}")
        return _error(str(e))


# ── Analytics (Supabase) ─────────────────────────────────────────────────────

@app.get("/api/analytics/summary")
def analytics_summary():
    if not _analytics:
        return _ok({"data": None, "available": False})
    try:
        return _ok({"data": _analytics.get_performance_summary(days=30), "available": True})
    except Exception as e:
        logger.error(f"Dashboard /api/analytics/summary error: {e}")
        return _error(str(e))


@app.get("/api/analytics/daily")
def analytics_daily():
    if not _analytics:
        return _ok({"data": [], "available": False})
    try:
        return _ok({"data": _analytics.get_daily_performance(days=30), "available": True})
    except Exception as e:
        logger.error(f"Dashboard /api/analytics/daily error: {e}")
        return _error(str(e))


@app.get("/api/analytics/strategies")
def analytics_strategies():
    if not _analytics:
        return _ok({"data": {}, "available": False})
    try:
        return _ok({"data": _analytics.get_strategy_performance(days=30), "available": True})
    except Exception as e:
        logger.error(f"Dashboard /api/analytics/strategies error: {e}")
        return _error(str(e))


@app.get("/api/analytics/symbols")
def analytics_symbols():
    if not _analytics:
        return _ok({"data": [], "available": False})
    try:
        return _ok({"data": _analytics.get_best_performing_symbols(limit=10), "available": True})
    except Exception as e:
        logger.error(f"Dashboard /api/analytics/symbols error: {e}")
        return _error(str(e))


# ── Controls ─────────────────────────────────────────────────────────────────

@app.post("/api/pause")
def pause():
    if not _engine:
        return _error("engine not available", 503)
    try:
        _engine.pause()
        logger.info("Dashboard: trading paused")
        return _ok({"ok": True, "status": "paused"})
    except Exception as e:
        logger.error(f"Dashboard /api/pause error: {e}")
        return _error(str(e))


@app.post("/api/resume")
def resume():
    if not _engine:
        return _error("engine not available", 503)
    try:
        _engine.resume()
        logger.info("Dashboard: trading resumed")
        return _ok({"ok": True, "status": "running"})
    except Exception as e:
        logger.error(f"Dashboard /api/resume error: {e}")
        return _error(str(e))


@app.post("/api/closeall/prepare")
def closeall_prepare():
    # type: () -> JSONResponse
    """
    Step 1 of Close All: generate a 30-second confirmation token.
    Returns position summary so the modal can show what will be closed.
    """
    global _closeall_token, _closeall_token_expiry

    if not _engine:
        return _error("engine not available", 503)

    try:
        positions = _engine.get_positions()
        total_value = sum(p.get("market_value", 0) for p in positions)
        total_pl = sum(p.get("unrealized_pl", 0) for p in positions)

        token = str(uuid.uuid4())
        _closeall_token = token
        _closeall_token_expiry = datetime.utcnow().timestamp() + 30  # 30 seconds

        return _ok({
            "token": token,
            "expires_in": 30,
            "position_count": len(positions),
            "total_value": round(total_value, 2),
            "total_pl": round(total_pl, 2),
        })
    except Exception as e:
        logger.error(f"Dashboard /api/closeall/prepare error: {e}")
        return _error(str(e))


@app.post("/api/closeall/confirm")
async def closeall_confirm(body: Dict[str, Any]):
    # type: (Dict[str, Any]) -> JSONResponse
    """
    Step 2 of Close All: validate token and execute.
    Pauses the engine first, then closes all positions.
    """
    global _closeall_token, _closeall_token_expiry

    if not _engine:
        return _error("engine not available", 503)

    token = body.get("token", "")

    if not _closeall_token or token != _closeall_token:
        return _error("Invalid or expired confirmation token", 400)

    if datetime.utcnow().timestamp() > _closeall_token_expiry:
        _closeall_token = None
        _closeall_token_expiry = None
        return _error("Confirmation token expired — no action taken", 400)

    # Invalidate token immediately (one-use only)
    _closeall_token = None
    _closeall_token_expiry = None

    try:
        # Pause engine first to prevent race with trading loop
        _engine.pause()
        success = _engine.alpaca.close_all_positions()
        logger.warning("Dashboard: CLOSE ALL POSITIONS executed")

        return _ok({
            "ok": success,
            "message": "All positions closed. Bot is paused — use Resume to restart trading.",
        })
    except Exception as e:
        logger.error(f"Dashboard /api/closeall/confirm error: {e}")
        return _error(str(e))


# ── Static files (dashboard HTML) ────────────────────────────────────────────
# Mounted last so /api/* routes take priority
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")


# ── Entry point ───────────────────────────────────────────────────────────────

def start_dashboard_server(engine, analytics, port=8080):
    # type: (Any, Any, int) -> None
    """
    Start the dashboard server. Call this in a daemon thread from main.py.
    Blocks until the process exits (uvicorn event loop).
    """
    init_server(engine, analytics)
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )
    except OSError as e:
        logger.error(f"Dashboard failed to start on port {port}: {e}")
        logger.error("Try setting a different port with DASHBOARD_PORT= in .env")
    except Exception as e:
        logger.error(f"Dashboard server error: {e}")
