from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# GET  /jobs/search           - Søg jobs via Search Intelligence
# GET  /jobs/{id}             - Hent specifikt job
# POST /jobs/{id}/save        - Gem job
# DELETE /jobs/{id}/save      - Fjern gemt job
# GET  /jobs/saved            - Brugerens gemte jobs
