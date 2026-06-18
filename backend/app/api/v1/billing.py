from fastapi import APIRouter

router = APIRouter(prefix="/billing", tags=["Billing"])

# GET  /billing/plans             - Tilgængelige abonnementsplaner
# GET  /billing/subscription      - Aktuel abonnementsstatus
# POST /billing/create-portal     - Stripe customer portal URL
# POST /billing/webhook           - Stripe webhook modtager
# GET  /billing/usage             - AI-forbrug denne måned
