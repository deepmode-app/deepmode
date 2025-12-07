# app/routes/billing.py

import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import (
    STRIPE_SECRET_KEY,
    STRIPE_PUBLISHABLE_KEY,
    STRIPE_PRICE_IDS,
    STRIPE_WEBHOOK_SECRET,
    APP_BASE_URL,
    STRIPE_LIVE_MODE,
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
    # Log mode for DEV clarity (test mode only)
    if not STRIPE_LIVE_MODE:
        print("[Stripe] TEST MODE (no real charges) - Using test keys from environment")

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
    Creates a Stripe Checkout Session for subscription and returns its URL.
    
    Note: This is wired for DEV/test mode using STRIPE_PRICE_ID_MONTHLY and STRIPE_PRICE_ID_YEARLY
    from environment variables. For PROD, use LIVE keys in environment.
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
    base_url = APP_BASE_URL.rstrip("/")

    try:
        # Create subscription checkout session
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
        
        # Store customer_id in DB if we can get it (may not be available until checkout completes)
        # The webhook will handle the full customer/subscription association
        
        return {"checkout_url": session.url}
    except Exception as e:
        print("[Stripe] Error in create_checkout_session:", repr(e))
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

        # ---- 3) Subscription created -> upgrade to Pro ----
        elif event_type == "customer.subscription.created":
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
                    print("[Stripe] subscription.created but no user matched (no email, no stripe IDs)")
                    return {"received": True}
                user_row = _find_user_by_email(conn, email)
                if not user_row:
                    print(f"[Stripe] subscription.created but no user found for email {email}")
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
                f"[Stripe] subscription.created: {email}, status={status}, "
                f"was_pro={was_pro}, is_pro_now={is_pro_now}"
            )

            if not was_pro and is_pro_now:
                try:
                    send_pro_welcome_email(email)
                    print(f"[Stripe] Sent Pro welcome email (via subscription.created) to {email}")
                except Exception as e:
                    print(f"[Stripe] Failed to send Pro welcome email to {email}: {e!r}")

        # ---- 4) Subscription deleted -> definitely not Pro ----
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

        # ---- 5) Invoice payment succeeded -> ensure Pro status is active ----
        elif event_type == "invoice.payment_succeeded":
            invoice = data_object
            subscription_id = invoice.get("subscription")
            customer_id = invoice.get("customer")
            
            if not subscription_id:
                # Not a subscription invoice, ignore
                print("[Stripe] invoice.payment_succeeded but no subscription_id, ignoring")
                return {"received": True}
            
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                status = sub.get("status")
                price_id = _extract_price_id_from_subscription(sub)
                
                make_pro = _subscription_status_to_pro_flag(status)
                
                user_row = _find_user_by_stripe_ids(conn, customer_id, subscription_id)
                
                if not user_row:
                    email = _get_email_from_subscription(sub)
                    if not email:
                        print("[Stripe] invoice.payment_succeeded but no user matched")
                        return {"received": True}
                    user_row = _find_user_by_email(conn, email)
                    if not user_row:
                        print(f"[Stripe] invoice.payment_succeeded but no user found for email {email}")
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
                    f"[Stripe] invoice.payment_succeeded: {email}, "
                    f"was_pro={was_pro}, is_pro_now={is_pro_now}"
                )
            except Exception as e:
                print(f"[Stripe] Error processing invoice.payment_succeeded: {e!r}")

        # ---- 6) Invoice payment failed -> log but don't change Pro status yet ----
        elif event_type == "invoice.payment_failed":
            invoice = data_object
            subscription_id = invoice.get("subscription")
            customer_id = invoice.get("customer")
            
            if subscription_id:
                try:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    # Payment failed doesn't immediately cancel subscription
                    # Stripe will retry and eventually cancel if all retries fail
                    # We'll handle cancellation via subscription.deleted or subscription.updated
                    print(f"[Stripe] invoice.payment_failed for subscription {subscription_id} (customer {customer_id})")
                except Exception as e:
                    print(f"[Stripe] Error processing invoice.payment_failed: {e!r}")

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

        base_url = APP_BASE_URL.rstrip("/")

    try:
        # 1) Find Stripe customer by email
        customers = stripe.Customer.list(email=raw_email, limit=1)
        if not customers.data:
            # No customer found - return error (POST endpoint, frontend can redirect)
            raise HTTPException(
                status_code=400,
                detail="No billing profile found for this account yet. Please upgrade first.",
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


# ---------- Billing Portal Route (GET) ----------

@router.get("/billing/portal")
async def billing_portal_redirect(request: Request):
    """
    GET route for billing portal - redirects to Stripe Customer Portal.
    This is used by the dropdown link. Requires authentication via Bearer token.
    """
    from fastapi import Depends
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from app.auth_utils import decode_access_token
    from app.database import get_conn
    
    # Extract token from Authorization header
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        # If no token in header, try to get from query params (for GET links)
        # Or redirect to login
        return RedirectResponse("/login")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    if payload is None:
        return RedirectResponse("/login")
    
    user_id = payload.get("user_id")
    if not user_id:
        return RedirectResponse("/login")
    
    # Get user email from database
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return RedirectResponse("/login")
    
    user_email = row["email"]
    
    # Use the existing POST endpoint logic but redirect directly
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Stripe is not configured. Please contact support."
        )
    
    base_url = APP_BASE_URL.rstrip("/")
    
    try:
        # 1) Find Stripe customer by email
        customers = stripe.Customer.list(email=user_email, limit=1)
        if not customers.data:
            # No customer found - redirect to checkout instead of erroring
            return RedirectResponse(url=f"{base_url}/billing/checkout")
        
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
                (customer_id, user_email),
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
        
        # Redirect to portal URL
        return RedirectResponse(url=portal_session.url)
        
    except HTTPException:
        raise
    except Exception as e:
        print("[Stripe] Error creating customer portal:", repr(e))
        raise HTTPException(
            status_code=500,
            detail="Could not open billing portal. Please try again later.",
        )
