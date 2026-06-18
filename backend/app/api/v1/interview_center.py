from fastapi import APIRouter

router = APIRouter(prefix="/interview-center", tags=["Interview Center"])

# Pakker
# POST /interview-center/packages             - Opret pakke til job
# GET  /interview-center/packages             - Mine pakker
# GET  /interview-center/packages/{id}        - Hent pakke
# DELETE /interview-center/packages/{id}      - Slet pakke

# Virksomhedsresearch
# POST /interview-center/company-research     - Igangsæt research (async)
# GET  /interview-center/company/{domain}     - Hent cached research

# Rolleanalyse
# POST /interview-center/role-analysis        - Analyser jobopslag
# GET  /interview-center/role-analysis/{id}   - Hent analyse

# Knowledge Guides
# GET  /interview-center/guides               - Liste guides
# GET  /interview-center/guides/{id}          - Hent guide

# Lønforberedelse
# POST /interview-center/salary-prep          - Opret session
# GET  /interview-center/salary-prep/{id}     - Hent session

# Interviewtræning
# POST /interview-center/sessions/start       - Start træningssession
# POST /interview-center/sessions/{id}/answer - Send svar (streaming)
# GET  /interview-center/sessions             - Historik
