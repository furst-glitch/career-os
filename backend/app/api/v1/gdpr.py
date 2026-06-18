from fastapi import APIRouter

router = APIRouter(prefix="/gdpr", tags=["GDPR"])

# GET    /gdpr/export     - Eksporter al brugerdata som JSON
# DELETE /gdpr/delete     - Anmod om sletning af konto og data
# GET    /gdpr/consent    - Hent samtykke-log
# POST   /gdpr/consent    - Registrer samtykke
