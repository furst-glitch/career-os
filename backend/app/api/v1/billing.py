"""
Billing API — Stripe subscription management

GET   /billing/plans              — plansammenligning
GET   /billing/subscription       — aktuel abonnementsstatus + Stripe info
POST  /billing/create-checkout    — Stripe checkout session (plan-opgradering)
POST  /billing/create-portal      — Stripe customer portal URL
POST  /billing/webhook            — Stripe webhook modtager
GET   /billing/usage              — AI-forbrug for nuværende faktureringsperiode
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import get_current_user, get_supabase_admin

logger = logging.getLogger("app.billing")
router = APIRouter(prefix="/billing", tags=["Billing"])

# ── Planbeskrivelser ──────────────────────────────────────────────────────────

PLANS: dict[str, dict] = {
    "free": {
        "name": "Free",
        "price_dkk": 0,
        "interval": None,
        "features": [
            "5 AI-chat beskeder/dag",
            "2 CV-analyser/dag",
            "1 ansættelsesforhold",
            "Grundlæggende Career Memory",
        ],
        "stripe_price_id": None,
    },
    "pro": {
        "name": "Pro",
        "price_dkk": 149,
        "interval": "month",
        "features": [
            "30 AI-chat beskeder/dag",
            "Ubegrænsede analyser",
            "5 ansættelsesforhold",
            "Fuld Career Memory",
            "AI Løncoach",
            "Ansøgningsgenerator",
        ],
        "stripe_price_id": settings.stripe_price_pro or None,
    },
    "professional": {
        "name": "Professional",
        "price_dkk": 299,
        "interval": "month",
        "features": [
            "100 AI-chat beskeder/dag",
            "Multi-agent dokumentreview",
            "Ubegrænsede ansættelsesforhold",
            "Prioriteret support",
            "Avanceret lønanalyse",
        ],
        "stripe_price_id": settings.stripe_price_professional or None,
    },
    "enterprise": {
        "name": "Enterprise",
        "price_dkk": None,
        "interval": None,
        "features": [
            "Alt i Professional",
            "Ubegrænset AI-forbrug",
            "SSO / SAML",
            "Dedikeret support",
            "Tilpasset onboarding",
        ],
        "stripe_price_id": settings.stripe_price_enterprise or None,
    },
}

# ── Schemas ───────────────────────────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    plan: str  # "pro" | "professional" | "enterprise"


# ── Stripe helpers ────────────────────────────────────────────────────────────


def _stripe_client() -> None:
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Betalingssystem er ikke konfigureret endnu")
    stripe.api_key = settings.stripe_secret_key


def _get_or_create_stripe_customer(supabase, user: dict) -> str:
    """Return existing stripe_customer_id or create a new Stripe Customer."""
    result = (
        supabase.table("subscriptions")
        .select("stripe_customer_id")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    existing = (result.data[0] if result.data else {}).get("stripe_customer_id")
    if existing:
        return existing

    profile = (
        supabase.table("user_profiles")
        .select("display_name")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    name = (profile.data[0] if profile.data else {}).get("display_name") or ""

    customer = stripe.Customer.create(
        email=user.get("email", ""),
        name=name,
        metadata={"user_id": user["id"]},
    )
    supabase.table("subscriptions").update(
        {"stripe_customer_id": customer.id}
    ).eq("user_id", user["id"]).execute()
    logger.info("stripe_customer_created user=%s customer=%s", user["id"], customer.id)
    return customer.id


def _plan_from_price_id(price_id: str | None) -> str:
    if not price_id:
        return "free"
    for key, data in PLANS.items():
        if data.get("stripe_price_id") and data["stripe_price_id"] == price_id:
            return key
    return "free"


def _sync_stripe_subscription(supabase, stripe_sub: dict, user_id: str | None = None) -> None:
    """Write a Stripe subscription object back to our subscriptions table."""
    STATUS_MAP = {
        "active": "active",
        "trialing": "trialing",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "incomplete": "past_due",
        "incomplete_expired": "canceled",
    }
    stripe_status = stripe_sub.get("status", "canceled")
    status = STATUS_MAP.get(stripe_status, "canceled")

    items = (stripe_sub.get("items") or {}).get("data") or []
    price_id = items[0]["price"]["id"] if items else None
    plan = _plan_from_price_id(price_id)
    if status == "canceled":
        plan = "free"

    update: dict = {
        "plan": plan,
        "status": status,
        "stripe_subscription_id": stripe_sub.get("id"),
        "updated_at": "now()",
    }
    if stripe_sub.get("current_period_start"):
        update["current_period_start"] = datetime.fromtimestamp(
            stripe_sub["current_period_start"], tz=timezone.utc
        ).isoformat()
    if stripe_sub.get("current_period_end"):
        update["current_period_end"] = datetime.fromtimestamp(
            stripe_sub["current_period_end"], tz=timezone.utc
        ).isoformat()

    if not user_id:
        customer_id = stripe_sub.get("customer")
        row = (
            supabase.table("subscriptions")
            .select("user_id")
            .eq("stripe_customer_id", customer_id)
            .limit(1)
            .execute()
        )
        user_id = row.data[0]["user_id"] if row.data else None

    if user_id:
        supabase.table("subscriptions").update(update).eq("user_id", user_id).execute()
        logger.info(
            "subscription_synced user=%s plan=%s status=%s sub=%s",
            user_id, plan, status, stripe_sub.get("id"),
        )
    else:
        logger.warning("subscription_sync_skipped_no_user sub=%s", stripe_sub.get("id"))


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/plans")
async def list_plans():
    """Plansammenligning — ingen autentificering krævet."""
    return {"plans": PLANS}


@router.get("/subscription")
async def get_subscription(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Aktuel abonnementsstatus + AI-budget."""
    result = (
        supabase.table("subscriptions")
        .select("plan, status, current_period_end, stripe_customer_id, stripe_subscription_id")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    sub = result.data[0] if result.data else {"plan": "free", "status": "active"}

    budget_result = (
        supabase.table("ai_budgets")
        .select("monthly_limit_usd, current_spend_usd, warning_threshold, hard_limit, period_reset_at")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    budget = budget_result.data[0] if budget_result.data else {}

    plan_key = sub.get("plan", "free")
    return {
        "plan": plan_key,
        "status": sub.get("status", "active"),
        "current_period_end": sub.get("current_period_end"),
        "has_stripe_subscription": bool(sub.get("stripe_subscription_id")),
        "ai_budget": {
            "monthly_limit_usd": float(budget.get("monthly_limit_usd", 10) or 10),
            "current_spend_usd": float(budget.get("current_spend_usd", 0) or 0),
            "warning_threshold": float(budget.get("warning_threshold", 0.8) or 0.8),
            "hard_limit": budget.get("hard_limit", False),
            "period_reset_at": budget.get("period_reset_at"),
        },
        "plan_features": PLANS.get(plan_key, PLANS["free"]),
    }


@router.post("/create-checkout")
async def create_checkout(
    body: CheckoutRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Opret Stripe checkout session til plan-opgradering."""
    _stripe_client()

    plan_data = PLANS.get(body.plan)
    if not plan_data or not plan_data.get("stripe_price_id"):
        raise HTTPException(422, f"Ukendt eller ikke-konfigureret plan: {body.plan}")

    try:
        customer_id = _get_or_create_stripe_customer(supabase, user)
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": plan_data["stripe_price_id"], "quantity": 1}],
            success_url=f"{settings.frontend_url}/settings/billing?success=1",
            cancel_url=f"{settings.frontend_url}/settings/billing?canceled=1",
            metadata={"user_id": user["id"], "plan": body.plan},
            allow_promotion_codes=True,
        )
    except stripe.StripeError as exc:
        logger.error("stripe_checkout_failed user=%s error=%s", user["id"], exc)
        raise HTTPException(500, "Checkout oprettelse fejlede — prøv igen")

    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/create-portal")
async def create_portal(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Opret Stripe customer portal session (administrér abonnement og fakturaer)."""
    _stripe_client()

    result = (
        supabase.table("subscriptions")
        .select("stripe_customer_id")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    customer_id = (result.data[0] if result.data else {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(404, "Ingen betalingsprofil fundet — opret et abonnement først")

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{settings.frontend_url}/settings/billing",
        )
    except stripe.StripeError as exc:
        logger.error("stripe_portal_failed user=%s error=%s", user["id"], exc)
        raise HTTPException(500, "Portal oprettelse fejlede — prøv igen")

    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="stripe-signature"),
    supabase=Depends(get_supabase_admin),
):
    """Modtag og behandl Stripe webhook events."""
    if not settings.stripe_webhook_secret:
        logger.warning("stripe_webhook_received_without_secret")
        raise HTTPException(400, "Webhook ikke konfigureret")

    stripe.api_key = settings.stripe_secret_key
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("stripe_webhook_invalid_signature error=%s", exc)
        raise HTTPException(400, "Ugyldig webhook signatur")
    except Exception as exc:
        logger.error("stripe_webhook_parse_failed error=%s", exc)
        raise HTTPException(400, "Webhook parsing fejlede")

    event_type: str = event["type"]
    logger.info("stripe_webhook type=%s id=%s", event_type, event["id"])

    try:
        obj = event["data"]["object"]

        if event_type == "checkout.session.completed":
            stripe_sub_id = obj.get("subscription")
            if stripe_sub_id:
                stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
                _sync_stripe_subscription(supabase, stripe_sub)

        elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
            _sync_stripe_subscription(supabase, obj)

        elif event_type == "customer.subscription.deleted":
            customer_id = obj.get("customer")
            if customer_id:
                row = (
                    supabase.table("subscriptions")
                    .select("user_id")
                    .eq("stripe_customer_id", customer_id)
                    .limit(1)
                    .execute()
                )
                if row.data:
                    uid = row.data[0]["user_id"]
                    supabase.table("subscriptions").update({
                        "plan": "free",
                        "status": "canceled",
                        "stripe_subscription_id": None,
                        "updated_at": "now()",
                    }).eq("user_id", uid).execute()
                    logger.info("subscription_canceled_downgraded_to_free user=%s", uid)

        elif event_type == "invoice.payment_failed":
            customer_id = obj.get("customer")
            if customer_id:
                supabase.table("subscriptions").update(
                    {"status": "past_due", "updated_at": "now()"}
                ).eq("stripe_customer_id", customer_id).execute()
                logger.warning("invoice_payment_failed customer=%s", customer_id)

    except Exception as exc:
        # Return 200 so Stripe does not retry — failure is logged and monitored
        logger.error("stripe_webhook_processing_failed type=%s error=%s", event_type, exc, exc_info=True)

    return {"received": True}


@router.get("/usage")
async def get_usage(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """AI-forbrug for nuværende faktureringsperiode."""
    from datetime import date

    budget_result = (
        supabase.table("ai_budgets")
        .select("*")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    budget = budget_result.data[0] if budget_result.data else {}

    period_start = date.today().replace(day=1).isoformat()
    costs_result = (
        supabase.table("ai_costs")
        .select("total_tokens, operations_count, cost_by_agent")
        .eq("user_id", user["id"])
        .gte("period_start", period_start)
        .limit(1)
        .execute()
    )
    cost = costs_result.data[0] if costs_result.data else {}

    return {
        "period_start": period_start,
        "period_reset_at": budget.get("period_reset_at"),
        "monthly_limit_usd": float(budget.get("monthly_limit_usd", 10) or 10),
        "current_spend_usd": float(budget.get("current_spend_usd", 0) or 0),
        "hard_limit_reached": budget.get("hard_limit", False),
        "total_tokens": cost.get("total_tokens", 0),
        "operations_count": cost.get("operations_count", 0),
        "cost_by_agent": cost.get("cost_by_agent") or {},
    }
