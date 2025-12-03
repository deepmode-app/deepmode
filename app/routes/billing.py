# app/routes/billing.py

import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import (
    STRIPE_SECRET_KEY,
    STRIPE_PUBLIC_KEY,
    STRIPE_PRICE_IDS,
    STRIPE_WEBHOOK_SECRET,
)
from app.database import get_conn
from app.email_utils import (
    send_pro_welcome_email,
    send_pro_cancellation_email,
)

# ---------- Stripe initialization ----------

if not STRIPE_SECRET_KEY:
    print("[Stripe] WARNING: STRIPE_SECRET_KEY not set in environment. Stripe features will not work.")
else:
    stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter()


class CheckoutRequest(BaseModel):
    email: str   # user email to attach to Stripe customer
    plan: str    # "monthly" or "yearly"


class CustomerPortalRequest(BaseModel):
    email: str  # email to resolve Stripe customer


# ---------- Helpers ----------

def _get_email_from_checkout_session(session_obj) -> str | None:
    """
    Try to pull email from a Checkout Session object in a robust way.
    """
    return (
        session_obj.get("customer_details", {}).get("email")
        or session_obj.get("customer_email")
    )


def _subscription_status_to_pro_flag(status: str) -> bool:
    """
    Decide whether a given Stripe subscription status means the user
    should be treated as Pro.
    """
    if not status:
        return False
    s = status.lower()
    # Keep it simple: active or trialing = Pro. Everything else = not Pro.
    return s in ("active", "trialing")


def _find_user_by_email(conn, email: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          id,
          email,
          is_pro,
          stripe_customer_id,
          stripe_subscription_id,
          stripe_subscription_status,
          stripe_price_id
        FROM users
        WHERE email = %s
        """,
        (email,),
    )
    row = cur.fetchone()
    cur.close()
    return row


def _find_user_by_stripe_ids(conn, customer_id: str | None, subscription_id: str | None):
    """
    Primary match by stripe_customer_id, fallback by stripe_subscription_id.
    """
    cur = conn.cursor()

    if customer_id and subscription_id:
        cur.execute(
            """
            SELECT
              id,
              email,
              is_pro,
              stripe_customer_id,
              stripe_subscription_id,
              stripe_subscription_status,
              stripe_price_id
            FROM users
            WHERE stripe_customer_id = %s
               OR stripe_subscription_id = %s
            LIMIT 1
            """,
            (customer_id, subscription_id),
        )
    elif customer_id:
        cur.execute(
            """
            SELECT
              id,
              email,
              is_pro,
              stripe_customer_id,
              stripe_subscription_id,
              stripe_subscription_status,
              stripe_price_id
            FROM users
            WHERE stripe_customer_id = %s
            LIMIT 1
            """,
            (customer_id,),
        )
    elif subscription_id:
        cur.execute(
            """
            SELECT
              id,
              email,
              is_pro,
              stripe_customer_id,
              stripe_subscription_id,
              stripe_subscription_status,
              stripe_price_id
            FROM users
            WHERE stripe_subscription_id = %s
            LIMIT 1
            """,
            (subscription_id,),
        )
    else:
        cur.close()
        return None

    row = cur.fetchone()
    cur.close()
    return row


def _get_email_from_subscription(subscription_obj) -> str | None:
    """
    Fallback: given a subscription object, fetch the Customer and pull email.
    Only used if we can't match by stored Stripe IDs.
    """
    try:
        customer_id = subscription_obj.get("customer")
        if not customer_id:
            return None
        customer = stripe.Customer.retrieve(customer_id)
        return customer.get("email")
    except Exception as e:
        print("[Stripe] Failed to fetch customer email from subscription:", e)
        return None


def _extract_price_id_from_subscription(sub_obj) -> str | None:
    """
    Get the price id (e.g. price_123) from a subscription object.
    """
    try:
        items = sub_obj.get("items", {}).get("data", [])
        if not items:
            return None
        price = items[0].get("price")
        if isinstance(price, dict):
            return price.get("id")
        return None
    except Exception:
        return None


def _update_user_billing(
    conn,
    user_row,
    *,
    make_pro: bool | None,
    customer_id: str | None,
    subscription_id: str | None,
    subscription_status: str | None,
    price_id: str | None,
):
    """
    Centralised DB update for user billing fields.
    Returns (was_pro, is_pro_now).
    """
    email = user_row["email"]
    was_pro = bool(user_row["is_pro"])

    # Decide new Pro flag
    if make_pro is None:
        new_pro = was_pro
    else:
        new_pro = bool(make_pro)

    set_clauses = []
    params = []

    # is_pro
    if new_pro != was_pro:
        set_clauses.append("is_pro = %s")
        params.append(new_pro)

    # stripe_customer_id: only set if we got one
    if customer_id:
        if not user_row.get("stripe_customer_id"):
            set_clauses.append("stripe_customer_id = %s")
            params.append(customer_id)

    # subscription id
    if subscription_id:
        if user_row.get("stripe_subscription_id") != subscription_id:
            set_clauses.append("stripe_subscription_id = %s")
            params.append(subscription_id)

    # subscription status
    if subscription_status:
        if user_row.get("stripe_subscription_status") != subscription_status:
            set_clauses.append("stripe_subscription_status = %s")
            params.append(subscription_status)

    # price id
    if price_id:
        if user_row.get("stripe_price_id") != price_id:
            set_clauses.append("stripe_price_id = %s")
            params.append(price_id)

    if set_clauses:
        set_sql = ", ".join(set_clauses)
        params.append(email)
        cur = conn.cursor()
        cur.execute(
            f"UPDATE users SET {set_sql} WHERE email = %s",
            tuple(params),
        )
        conn.commit()
        cur.close()
        print(f"[Stripe] Updated billing fields for {email}: {set_sql}")
    else:
        print(f"[Stripe] No billing changes needed for {email}")

    return was_pro, new_pro


# ---------- Create Checkout Session ----------

@router.post("/billing/create-checkout-session")
async def create_checkout_session(request: Request, payload: CheckoutRequest):
    """
    Creates a Stripe Checkout Session and returns its URL.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Stripe is not configured. Please contact support."
        )

    plan = payload.plan.lower()
    if plan not in STRIPE_PRICE_IDS:
        raise HTTPException(
            status_code=500,
            detail=f"Stripe price ID for '{plan}' plan is not configured."
        )

    price_id = STRIPE_PRICE_IDS[plan]
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


# ---------- Webhook endpoint ----------

@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe webhook endpoint.

    For local dev, use:
      stripe listen --forward-to http://127.0.0.1:8000/billing/webhook
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not STRIPE_WEBHOOK_SECRET:
        print("[Stripe] ERROR: STRIPE_WEBHOOK_SECRET is not set in environment.")
        raise HTTPException(
            status_code=500,
            detail="Stripe webhook secret is not configured. Cannot verify webhook signatures."
        )

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        print("[Stripe] Invalid payload received on /billing/webhook")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        print("[Stripe] Invalid signature on /billing/webhook")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data_object = event["data"]["object"]

    print(f"[Stripe] Webhook received: {event_type}")

    conn = get_conn()

    try:
        # ---- 1) Checkout completion -> first upgrade to Pro ----
        if event_type == "checkout.session.completed":
            session_obj = data_object

            email = _get_email_from_checkout_session(session_obj)
            if not email:
                print("[Stripe] checkout.session.completed but no email found on session")
                return {"received": True}

            customer_id = session_obj.get("customer")
            subscription_id = session_obj.get("subscription")

            # Optionally load subscription to get status + price
            subscription_status = None
            price_id = None
            if subscription_id:
                try:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    subscription_status = sub.get("status")
                    price_id = _extract_price_id_from_subscription(sub)
                except Exception as e:
                    print("[Stripe] Failed to retrieve subscription in checkout.session.completed:", e)

            make_pro = True

            user_row = _find_user_by_email(conn, email)
            if not user_row:
                print(f"[Stripe] checkout.session.completed for unknown email {email}")
                return {"received": True}

            was_pro, is_pro_now = _update_user_billing(
                conn,
                user_row,
                make_pro=make_pro,
                customer_id=customer_id,
                subscription_id=subscription_id,
                subscription_status=subscription_status,
                price_id=price_id,
            )

            print(
                f"[Stripe] checkout.session.completed: {email}, "
                f"was_pro={was_pro}, is_pro_now={is_pro_now}, "
                f"customer_id={customer_id}, subscription_id={subscription_id}"
            )

            if not was_pro and is_pro_now:
                try:
                    send_pro_welcome_email(email)
                    print(f"[Stripe] Sent Pro welcome email to {email}")
                except Exception as e:
                    print(f"[Stripe] Failed to send Pro welcome email to {email}: {e!r}")

        # ---- 2) Subscription updated -> keep is_pro in sync ----
        elif event_type == "customer.subscription.updated":
            sub = data_object
            subscription_id = sub.get("id")
            customer_id = sub.get("customer")
            status = sub.get("status")
            price_id = _extract_price_id_from_subscription(sub)

            make_pro = _subscription_status_to_pro_flag(status)

            user_row = _find_user_by_stripe_ids(conn, customer_id, subscription_id)

            if not user_row:
                email = _get_email_from_subscription(sub)
                if not email:
                    print("[Stripe] subscription.updated but no user matched (no email, no stripe IDs)")
                    return {"received": True}
                user_row = _find_user_by_email(conn, email)
                if not user_row:
                    print(f"[Stripe] subscription.updated but no user found for email {email}")
                    return {"received": True}
            else:
                email = user_row["email"]

            was_pro, is_pro_now = _update_user_billing(
                conn,
                user_row,
                make_pro=make_pro,
                customer_id=customer_id,
                subscription_id=subscription_id,
                subscription_status=status,
                price_id=price_id,
            )

            print(
                f"[Stripe] subscription.updated: {email}, status={status}, "
                f"was_pro={was_pro}, is_pro_now={is_pro_now}"
            )

            if not was_pro and is_pro_now:
                try:
                    send_pro_welcome_email(email)
                    print(f"[Stripe] Sent Pro welcome email (via subscription.updated) to {email}")
                except Exception as e:
                    print(f"[Stripe] Failed to send Pro welcome email to {email}: {e!r}")

            if was_pro and not is_pro_now:
                try:
                    send_pro_cancellation_email(email)
                    print(f"[Stripe] Sent Pro cancellation email to {email}")
                except Exception as e:
                    print(f"[Stripe] Failed to send cancellation email to {email}: {e!r}")

        # ---- 3) Subscription deleted -> definitely not Pro ----
        elif event_type == "customer.subscription.deleted":
            sub = data_object
            subscription_id = sub.get("id")
            customer_id = sub.get("customer")
            status = sub.get("status")
            price_id = _extract_price_id_from_subscription(sub)

            make_pro = False

            user_row = _find_user_by_stripe_ids(conn, customer_id, subscription_id)

            if not user_row:
                email = _get_email_from_subscription(sub)
                if not email:
                    print("[Stripe] subscription.deleted but no user matched")
                    return {"received": True}
                user_row = _find_user_by_email(conn, email)
                if not user_row:
                    print(f"[Stripe] subscription.deleted but no user found for email {email}")
                    return {"received": True}
            else:
                email = user_row["email"]

            was_pro, is_pro_now = _update_user_billing(
                conn,
                user_row,
                make_pro=make_pro,
                customer_id=customer_id,
                subscription_id=subscription_id,
                subscription_status=status,
                price_id=price_id,
            )

            print(
                f"[Stripe] subscription.deleted: {email}, status={status}, "
                f"was_pro={was_pro}, is_pro_now={is_pro_now}"
            )

            if was_pro and not is_pro_now:
                try:
                    send_pro_cancellation_email(email)
                    print(f"[Stripe] Sent Pro cancellation email (deleted) to {email}")
                except Exception as e:
                    print(f"[Stripe] Failed to send cancellation email to {email}: {e!r}")

        else:
            print(f"[Stripe] Ignoring event type: {event_type}")

    finally:
        conn.close()

    return {"received": True}


# ---------- Customer Portal (email-based, robust) ----------

@router.post("/billing/customer-portal")
async def create_customer_portal(request: Request, payload: CustomerPortalRequest):
    """
    Create a Stripe Customer Portal session for the user identified by email.

    Behaviour:
    - Look up Stripe Customer by email directly via Stripe API (source of truth).
    - If found, create a Portal session and return portal_url.
    - If not found, return 400 with a clear message.
    - Also upserts stripe_customer_id in DB.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Stripe is not configured. Please contact support."
        )

    raw_email = (payload.email or "").strip()
    if not raw_email:
        raise HTTPException(status_code=400, detail="Email is required for billing portal.")

    base_url = str(request.base_url).rstrip("/")

    try:
        # 1) Find Stripe customer by email
        customers = stripe.Customer.list(email=raw_email, limit=1)
        if not customers.data:
            raise HTTPException(
                status_code=400,
                detail="No billing profile found for this account yet.",
            )

        customer = customers.data[0]
        customer_id = customer.id

        # 2) Upsert stripe_customer_id in DB (if user row exists)
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                   SET stripe_customer_id = %s
                 WHERE email = %s
                """,
                (customer_id, raw_email),
            )
            conn.commit()
            cur.close()
        finally:
            conn.close()

        # 3) Create Stripe billing portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{base_url}/dashboard",
        )

        return {"portal_url": portal_session.url}

    except HTTPException:
        raise
    except Exception as e:
        print("[Stripe] Error creating customer portal:", repr(e))
        raise HTTPException(
            status_code=500,
            detail="Could not open billing portal. Please try again later.",
        )


# ---------- Simple redirect for /billing/checkout ----------

@router.get("/billing/checkout")
def fake_checkout():
    # Right now this just sends to pricing. Later you can make a nice pricing page.
    return RedirectResponse("/pricing")
