# CareerOS — API Reference

Base URL: `http://localhost:8000/api/v1` (dev) / `https://api.careeros.dk/api/v1` (prod)

## Autentificering

Alle endpoints (undtagen `/health`) kræver Supabase JWT:
```
Authorization: Bearer <supabase-access-token>
```

## Streaming (SSE)

AI-genererende endpoints streamer via Server-Sent Events.
Brug `apiStream()` fra `frontend/lib/api.ts`.

## Endpoints

### Auth
```
POST /auth/register
POST /auth/login
POST /auth/logout
GET  /auth/me
PUT  /auth/me
```

### CV Studio
```
POST   /cv/upload
GET    /cv/master
PUT    /cv/master
GET    /cv/versions
POST   /cv/versions
GET    /cv/versions/{id}
DELETE /cv/versions/{id}
POST   /cv/interview/start
```

### Experience Discovery
```
GET    /experience
POST   /experience
PUT    /experience/{id}
DELETE /experience/{id}
POST   /experience/{id}/star     ← SSE streaming
GET    /experience/{id}/stars
GET    /competencies
POST   /discovery/start
POST   /discovery/{id}/message   ← SSE streaming
GET    /discovery/{id}
POST   /discovery/{id}/extract
```

### Career Memory
```
GET    /memory
POST   /memory
DELETE /memory/{id}
GET    /memory/search?q=          ← Semantisk søgning
GET    /memory/snapshot
GET    /memory/goals
POST   /memory/goals
PUT    /memory/goals/{id}
DELETE /memory/goals/{id}
GET    /memory/preferences
PUT    /memory/preferences
GET    /memory/milestones
POST   /memory/milestones
```

### Jobs
```
GET    /jobs/search
GET    /jobs/{id}
POST   /jobs/{id}/save
DELETE /jobs/{id}/save
GET    /jobs/saved
```

### Application Pipeline
```
GET    /applications
GET    /applications/{id}
POST   /applications
PUT    /applications/{id}/status
GET    /applications/{id}/history
POST   /applications/{id}/documents
GET    /applications/{id}/documents
POST   /applications/generate        ← SSE streaming
```

### Interview Center
```
POST   /interview-center/packages
GET    /interview-center/packages
GET    /interview-center/packages/{id}
DELETE /interview-center/packages/{id}
POST   /interview-center/company-research
GET    /interview-center/company/{domain}
POST   /interview-center/role-analysis
GET    /interview-center/role-analysis/{id}
GET    /interview-center/guides
GET    /interview-center/guides/{id}
POST   /interview-center/salary-prep
GET    /interview-center/salary-prep/{id}
POST   /interview-center/sessions/start
POST   /interview-center/sessions/{id}/answer  ← SSE streaming
GET    /interview-center/sessions
```

### Search Intelligence
```
GET    /search/keywords
POST   /search/keywords
PUT    /search/keywords/{id}
DELETE /search/keywords/{id}
POST   /search/keywords/suggest    ← SSE streaming
POST   /search/keywords/apply
POST   /search/signal
GET    /search/profile
PUT    /search/profile
GET    /search/performance
```

### Multi-Agent Review
```
POST   /review/submit
GET    /review/{id}
GET    /review/{id}/agents
GET    /review/{id}/agents/{name}
GET    /review/{id}/stream         ← SSE streaming
POST   /review/{id}/apply
```

### Billing
```
GET    /billing/plans
GET    /billing/subscription
POST   /billing/create-portal
POST   /billing/webhook
GET    /billing/usage
```

### GDPR
```
GET    /gdpr/export
DELETE /gdpr/delete
GET    /gdpr/consent
POST   /gdpr/consent
```

## HTTP Status Codes

| Code | Betydning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized (ugyldig token) |
| 402 | Payment Required (plan for lav) |
| 403 | Forbidden |
| 404 | Not Found |
| 429 | Too Many Requests |
| 500 | Internal Server Error |
