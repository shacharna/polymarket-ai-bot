#!/usr/bin/env python3
"""Test Supabase connection with detailed error logging"""
import traceback
from supabase import create_client

URL = "https://xznmjhtrmltnoyyanvic.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh6bm1qaHRybWx0bm95eWFudmljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA5NzA2NjksImV4cCI6MjA4NjU0NjY2OX0.UBQI-sRInX9rspkr9zvDAvPPj6KaluF-ztZZfPTXjio"

try:
    print("Testing Supabase connection...")
    client = create_client(URL, KEY)
    print(f"✓ Success! Client created: {type(client)}")
    print(f"✓ Client type: {client}")
except Exception as e:
    print(f"✗ Failed to create client")
    print(f"Error: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
