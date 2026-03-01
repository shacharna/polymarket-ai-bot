"""
Supabase write test using direct REST API (no supabase library — no httpx conflicts).
Run from the project root:  python test_supabase_write.py
"""
import os
import sys
import json
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = (
    os.getenv("SUPABASE_URL") or
    os.getenv("NEXT_PUBLIC_SUPABASE_URL") or ""
).rstrip("/")

SUPABASE_KEY = (
    os.getenv("SUPABASE_KEY") or
    os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY") or ""
)

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: No Supabase credentials found in .env")
    print("  Expected: SUPABASE_URL + SUPABASE_KEY")
    print("  Or:       NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY")
    sys.exit(1)

print(f"URL : {SUPABASE_URL[:50]}...")
print(f"Key : {SUPABASE_KEY[:20]}...")
print()

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}
BASE = f"{SUPABASE_URL}/rest/v1"

# --- INSERT ---
test_record = {
    "symbol":         "AAPL",
    "side":           "buy",
    "entry_price":    182.50,
    "entry_time":     datetime.utcnow().isoformat(),
    "quantity":       10,
    "position_value": 1825.00,
    "strategy":       "momentum",
    "confidence":     75,
    "paper_trading":  True,
    "ai_setup_score": 7,
    "ai_risk_score":  4,
    "ai_reasoning":   "TEST RECORD - inserted by test_supabase_write.py",
    "rsi_14":         58.3,
    "sma_20":         179.40,
    "sma_50":         175.20,
    "bot_version":    "test-1.0",
}

print("Inserting test record...")
resp = requests.post(f"{BASE}/trades", headers=HEADERS, json=test_record)

if resp.status_code in (200, 201):
    inserted = resp.json()[0]
    record_id = inserted["id"]
    print(f"✓ Inserted  id={record_id}  symbol={inserted['symbol']}  entry_price={inserted['entry_price']}")
else:
    print(f"✗ Insert failed  status={resp.status_code}")
    print(f"  Response: {resp.text}")
    print()
    if resp.status_code == 401:
        if "42501" in resp.text or "row-level security" in resp.text:
            print("  → RLS is blocking the insert (HTTP 401 from PostgREST)")
            print("    Go to Supabase → SQL Editor → run:")
            print("      ALTER TABLE trades DISABLE ROW LEVEL SECURITY;")
        else:
            print("  → Wrong or missing API key")
    elif resp.status_code == 404:
        print("  → Table 'trades' not found")
        print("    Go to Supabase → SQL Editor → paste src/database/schema.sql → Run")
    elif resp.status_code == 403:
        print("  → RLS is blocking the insert")
        print("    Go to Supabase → Table Editor → trades → RLS → Disable RLS")
    elif "column" in resp.text.lower():
        print("  → Column mismatch — schema may need to be re-applied")
    sys.exit(1)

# --- READ BACK ---
print(f"\nReading back id={record_id}...")
resp = requests.get(
    f"{BASE}/trades",
    headers=HEADERS,
    params={"id": f"eq.{record_id}", "select": "id,symbol,strategy,confidence,paper_trading,ai_setup_score"}
)

if resp.status_code == 200 and resp.json():
    row = resp.json()[0]
    print(f"✓ Read OK   symbol={row['symbol']}  strategy={row['strategy']}  confidence={row['confidence']}")
    print(f"            paper_trading={row['paper_trading']}  ai_setup_score={row['ai_setup_score']}")
else:
    print(f"✗ Read failed  status={resp.status_code}  {resp.text}")

# --- DELETE (cleanup) ---
print(f"\nDeleting test record id={record_id}...")
resp = requests.delete(
    f"{BASE}/trades",
    headers={**HEADERS, "Prefer": "return=minimal"},
    params={"id": f"eq.{record_id}"}
)
if resp.status_code in (200, 204):
    print("✓ Cleaned up")
else:
    print(f"  (cleanup skipped: {resp.status_code} {resp.text})")

print()
print("=== SUCCESS — Supabase REST API is working correctly ===")
