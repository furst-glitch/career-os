from fastapi import APIRouter

router = APIRouter(prefix="/review", tags=["Multi-Agent Review"])

# POST /review/submit              - Submit dokument til multi-agent review
#                                    { type: cv|application, document_id, job_id?, agents?: [] }
# GET  /review/{id}                - Hent samlet review (inkl. status)
# GET  /review/{id}/agents         - Alle agenters individuelle output
# GET  /review/{id}/agents/{name}  - Specifik agents output
# GET  /review/{id}/stream         - SSE stream mens review kører
# POST /review/{id}/apply          - Anvend anbefalinger på dokument
