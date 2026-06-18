from fastapi import APIRouter

router = APIRouter(prefix="/experience", tags=["Experience Discovery"])

# GET  /experience                     - Liste erfaringer
# POST /experience                     - Opret erfaring
# PUT  /experience/{id}                - Opdater erfaring
# DELETE /experience/{id}              - Slet erfaring
# POST /experience/{id}/star           - Generer STAR-story (streaming)
# GET  /experience/{id}/stars          - Alle STAR-stories for erfaring
# GET  /competencies                   - Kompetence-bibliotek
# GET  /competencies/{id}              - Kompetence med beviser
# POST /discovery/start                - Start discovery session
# POST /discovery/{id}/message         - Send besked i session (streaming)
# GET  /discovery/{id}                 - Hent session og udledte data
# POST /discovery/{id}/extract         - Ekstraher strukturerede data
