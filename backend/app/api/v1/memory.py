from fastapi import APIRouter

router = APIRouter(prefix="/memory", tags=["Career Memory"])

# GET  /memory                - Liste minder (pagineret)
# POST /memory                - Tilføj manuelt minde
# DELETE /memory/{id}         - Slet minde
# GET  /memory/search?q=      - Semantisk søgning i minder
# GET  /memory/snapshot       - Kontekst-snapshot til agenter
# GET  /memory/goals          - Liste karrieremål
# POST /memory/goals          - Opret mål
# PUT  /memory/goals/{id}     - Opdater mål
# DELETE /memory/goals/{id}   - Slet mål
# GET  /memory/preferences    - Hent præferencer
# PUT  /memory/preferences    - Opdater præferencer
# GET  /memory/milestones     - Hent milepæle
# POST /memory/milestones     - Tilføj milepæl
