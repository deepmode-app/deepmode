# app/routes/billing.py

import os

from dotenv import load_dotenv
load_dotenv()

import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.database import get_conn
from app.email_utils import send_pro_welcome_email

# ---------- Stripe keys ----------

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY") or "sk_test_dummy_for_now"
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY") or "pk_test_dummy_for_now"
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")  # from Stripe CLI "webhook signing secret"

stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter()

# ---------- Price IDs ----------

PRICE_IDS = {
    "monthly": "price_1STANe22agTN2BGyT4ncyD5B",
    "yearly": "price_1STANe22agTN2BGy6y3wqXZ8",
}


class CheckoutRequest(BaseModel):
    email: str   # user email to attach to Stripe customer
    plan: str    # "monthly" or "yearly"


# ---------- Create Checkout Session ----------

@router.post("/billing/create-checkout-session")
async def create_checkout_session(request: Request, payload: CheckoutRequest):
    """
    Creates a Stripe Checkout Session and returns its URL.
    Frontend opens that URL in a new tab.
    """
    plan = payload.plan.lower()
    if plan not in PRICE_IDS:
        raise HTTPException(status_code=400, detail="Invalid plan. Use 'monthly' or 'yearly'.")

    price_id = PRICE_IDS[plan]
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
        print("Stripe error in create_checkout_session:", repr(e))
        raise HTTPException(status_code=500, detail="Could not create checkout session.")


# ---------- Simple redirect for /billing/checkout ----------

@router.get("/billing/checkout")
def fake_checkout():
    # Right now just send to pricing/landing; in prod this can be a nice pricing page.
    return RedirectResponse("/pricing")


# ---------- Webhook endpoint ----------

@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe webhook endpoint.

    For local dev, use:
      stripe listen --forward-to localhost:8000/billing/webhook

    Handles:
    - checkout.session.completed -> marks user.is_pro = TRUE based on email and
      sends a Pro welcome email on first upgrade.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not STRIPE_WEBHOOK_SECRET:
        print("[Stripe] STRIPE_WEBHOOK_SECRET is not set in env.")
        raise HTTPException(status_code=500, detail="Webhook secret not configured.")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        # Invalid JSON
        print("[Stripe] Invalid payload received on /billing/webhook")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        print("[Stripe] Invalid signature on /billing/webhook")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data_object = event["data"]["object"]

    print(f"[Stripe] Webhook received: {event_type}")

    # ---- Handle Checkout completion -> upgrade to Pro ----
    if event_type == "checkout.session.completed":
        session_obj = data_object

        # Stripe sometimes gives email in different places depending on flow
        email = (
            session_obj.get("customer_details", {}).get("email")
            or session_obj.get("customer_email")
        )

        if not email:
            print("[Stripe] checkout.session.completed but no email found on session")
            return {"received": True}

        conn = get_conn()
        cur = conn.cursor()

        # 1) Look up user
        cur.execute(
            "SELECT is_pro FROM users WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()

        if not row:
            print(f"[Stripe] checkout.session.completed for unknown email {email}")
            cur.close()
            conn.close()
            return {"received": True}

        # RealDictCursor -> row["is_pro"]
        was_pro = bool(row["is_pro"])

        if not was_pro:
            # 2) Flip to PRO
            cur.execute(
                "UPDATE users SET is_pro = TRUE WHERE email = %s",
                (email,),
            )
            conn.commit()
            print(f"[Stripe] Marked {email} as PRO")

            # 3) Fire Pro welcome email (non-blocking)
            try:
                send_pro_welcome_email(email)
                print(f"[Stripe] Sent Pro welcome email to {email}")
            except Exception as e:
                print(f"[Stripe] Failed to send Pro welcome email to {email}: {e!r}")
        else:
            print(f"[Stripe] {email} already PRO – skipping upgrade + welcome email")

        cur.close()
        conn.close()

    # TODO later:
    # - customer.subscription.deleted  -> downgrade is_pro
    # - customer.subscription.updated (status='canceled') -> downgrade

    return {"received": True}
