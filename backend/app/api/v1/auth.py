from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])

# POST /auth/register    - Opret bruger (via Supabase Auth)
# POST /auth/login       - Log ind
# POST /auth/logout      - Log ud
# POST /auth/refresh     - Forny token
# GET  /auth/me          - Hent aktuel bruger
# PUT  /auth/me          - Opdater profil
