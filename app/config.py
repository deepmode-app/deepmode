# app/config.py
"""
Application configuration loaded from environment variables.
"""

import os

# ---------- Stripe Configuration ----------

STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
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

