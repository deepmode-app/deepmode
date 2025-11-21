# app/routes/billing.py

import os


from dotenv import load_dotenv
load_dotenv()  # safe to call again


import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import RedirectResponse



STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY") or "sk_test_dummy_for_now"
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY") or "pk_test_dummy_for_now"

stripe.api_key = STRIPE_SECRET_KEY
router = APIRouter()


stripe.api_key = STRIPE_SECRET_KEY

# 2) REPLACE THESE WITH YOUR REAL PRICE IDS FROM STRIPE
#    Go to: Stripe → Products → Deepmode Pro → Prices → API ID
PRICE_IDS = {
    "monthly": "price_1STANe22agTN2BGyT4ncyD5B",
    "yearly": "price_1STANe22agTN2BGy6y3wqXZ8",
}


class CheckoutRequest(BaseModel):
    email: str         # user email to attach to Stripe customer
    plan: str          # "monthly" or "yearly"


@router.post("/billing/create-checkout-session")
async def create_checkout_session(request: Request, payload: CheckoutRequest):
    """
    Creates a Stripe Checkout session and returns the URL.
    The extension or dashboard will open that URL in a new tab.
    """

    plan = payload.plan.lower()
    if plan not in PRICE_IDS:
        raise HTTPException(status_code=400, detail="Invalid plan. Use 'monthly' or 'yearly'.")

    price_id = PRICE_IDS[plan]

    # Base URL of your backend (works on Replit, local, etc.)
    base_url = str(request.base_url).rstrip("/")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=payload.email,
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            success_url=f"{base_url}/dashboard?session=success",
            cancel_url=f"{base_url}/dashboard?session=cancel",
        )

        return {"checkout_url": session.url}

    except Exception as e:
        # Don't leak internal errors to the user
        print("Stripe error in create_checkout_session:", repr(e))
        raise HTTPException(status_code=500, detail="Could not create checkout session.")

@router.get("/billing/checkout")
def fake_checkout():
    # Replace this later with Stripe Checkout URL
    return RedirectResponse("/pricing")