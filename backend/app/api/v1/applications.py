from fastapi import APIRouter

router = APIRouter(prefix="/applications", tags=["Applications"])

# Application Pipeline
# GET  /applications                          - Liste pipeline entries
# GET  /applications/{id}                     - Hent pipeline entry
# POST /applications                          - Opret pipeline entry
# PUT  /applications/{id}/status              - Opdater status
# GET  /applications/{id}/history             - Status-historik
# POST /applications/{id}/documents           - Tilknyt dokument til pipeline
# GET  /applications/{id}/documents           - Hent tilknyttede dokumenter

# Application Generation
# POST /applications/generate                 - Generer ansøgning (streaming)
# GET  /applications/{id}/versions            - Dokumentversioner for ansøgning
