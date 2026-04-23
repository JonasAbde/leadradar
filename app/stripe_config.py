import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Price IDs - these would be created in Stripe dashboard
# For MVP we use a simple model: free, pro, agency
PRICE_MAP = {
    "pro": os.getenv("STRIPE_PRO_PRICE_ID", ""),
    "agency": os.getenv("STRIPE_AGENCY_PRICE_ID", ""),
}

SUBSCRIPTION_LIMITS = {
    "free": {"sources": 1, "check_interval": "daily", "history_days": 7},
    "pro": {"sources": 10, "check_interval": "hourly", "history_days": 90},
    "agency": {"sources": 50, "check_interval": "hourly", "history_days": 365},
}

def get_checkout_session_url(customer_email: str, tier: str) -> str:
    """Create a Stripe Checkout session for subscription"""
    price_id = PRICE_MAP.get(tier)
    if not price_id:
        raise ValueError(f"No Stripe price ID configured for tier: {tier}")
    
    session = stripe.checkout.Session.create(
        customer_email=customer_email,
        payment_method_types=["card"],
        line_items=[{
            "price": price_id,
            "quantity": 1,
        }],
        mode="subscription",
        success_url=f"http://57.128.215.250:8000/dashboard?success=true&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url="http://57.128.215.250:8000/pricing?canceled=true",
    )
    return session.url

def handle_webhook(payload: bytes, sig_header: str):
    """Handle Stripe webhook events"""
    if not STRIPE_WEBHOOK_SECRET:
        return None
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return None
    except stripe.error.SignatureVerificationError:
        return None
    
    return event
