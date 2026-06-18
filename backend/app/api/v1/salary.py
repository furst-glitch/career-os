from fastapi import APIRouter

router = APIRouter(prefix="/salary", tags=["Salary"])

# POST /salary/analyze        - Analyser lønniveau for rolle/marked
# GET  /salary/history        - Tidligere analyser
