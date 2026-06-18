from fastapi import APIRouter

router = APIRouter(prefix="/cv", tags=["CV Studio"])

# POST /cv/upload           - Upload og parse eksisterende CV (PDF/DOCX)
# GET  /cv/master           - Hent Master CV
# PUT  /cv/master           - Opdater Master CV
# GET  /cv/versions         - Alle CV-versioner
# POST /cv/versions         - Generer CV-version til specifikt job
# GET  /cv/versions/{id}    - Hent specifik version
# DELETE /cv/versions/{id}  - Slet version
# POST /cv/interview/start  - Start AI-interview for profilopbygning
