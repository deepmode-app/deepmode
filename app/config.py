# app/config.py
"""
Application configuration loaded from environment variables.
"""

import os

# ---------- Application Base URL ----------

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")

# ---------- Stripe Configuration ----------

# Note: Using STRIPE_PUBLISHABLE_KEY (not STRIPE_PUBLIC_KEY) to match Stripe's naming convention
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
# Legacy support: also check STRIPE_PUBLIC_KEY if STRIPE_PUBLISHABLE_KEY not set
if not STRIPE_PUBLISHABLE_KEY:
    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID_MONTHLY = os.getenv("STRIPE_PRICE_ID_MONTHLY", "")
STRIPE_PRICE_ID_YEARLY = os.getenv("STRIPE_PRICE_ID_YEARLY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Convenience dict for price IDs (empty if not configured)
STRIPE_PRICE_IDS = {}
if STRIPE_PRICE_ID_MONTHLY:
    STRIPE_PRICE_IDS["monthly"] = STRIPE_PRICE_ID_MONTHLY
if STRIPE_PRICE_ID_YEARLY:
    STRIPE_PRICE_IDS["yearly"] = STRIPE_PRICE_ID_YEARLY

# ---------- Stripe Mode Detection ----------

# Detect test mode from secret key prefix (sk_test_ = test, sk_live_ = live)
STRIPE_LIVE_MODE = STRIPE_SECRET_KEY.startswith("sk_live_") if STRIPE_SECRET_KEY else False

