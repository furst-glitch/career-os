from fastapi import APIRouter

router = APIRouter(prefix="/search", tags=["Search Intelligence"])

# GET  /search/keywords           - Alle keywords med vægte
# POST /search/keywords           - Tilføj keyword manuelt
# PUT  /search/keywords/{id}      - Opdater vægt/status
# DELETE /search/keywords/{id}    - Fjern keyword
# POST /search/keywords/suggest   - AI foreslår keywords (streaming)
# POST /search/keywords/apply     - Accepter foreslåede keywords
# POST /search/signal             - Registrer relevans-signal { job_id, signal_type }
# GET  /search/profile            - Aktiv søgeprofil
# PUT  /search/profile            - Opdater søgeprofil
# GET  /search/performance        - Keyword performance stats
