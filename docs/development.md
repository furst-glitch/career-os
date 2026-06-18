# CareerOS — Udviklingsguide

## Forudsætninger

- Python 3.12+
- Node.js 20+
- Docker Desktop
- Supabase CLI (`npm install -g supabase`)
- Git

## Første gangs setup

```bash
# 1. Klon repository
git clone https://github.com/din-org/careeros.git
cd CareerOS

# 2. Backend dependencies
cd backend && pip install -e ".[dev]" && cd ..

# 3. Frontend dependencies
cd frontend && npm install && cd ..

# 4. Miljøvariabler
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# Udfyld nøglerne i begge filer

# 5. Start lokal Supabase
supabase start
# Kopier output: anon key og service_role key til .env filerne

# 6. Anvend database migrations
supabase db reset
# Dette kører alle migrations + seed.sql

# 7. Start dev environment
make dev
```

## Daglig workflow

```bash
make dev              # Start alt
make dev-backend      # Kun backend (http://localhost:8000)
make dev-frontend     # Kun frontend (http://localhost:3000)
make test             # Kør alle tests
make lint             # Lint check
make format           # Auto-format
```

## API dokumentation

Når backend kører: http://localhost:8000/api/docs

## Supabase Studio

Når Supabase kører: http://localhost:54323

## Database migrations

```bash
# Ny migration
make new-migration
# Skriv SQL i den oprettede fil

# Anvend lokalt
supabase db push

# Nulstil og genopbyg (mister data!)
supabase db reset
```

## Miljøvariabler

### Backend (`backend/.env`)
| Variabel | Beskrivelse |
|---|---|
| `SECRET_KEY` | App secret (32+ tegn) |
| `SUPABASE_URL` | Supabase URL |
| `SUPABASE_ANON_KEY` | Anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin key |
| `ENCRYPTION_KEY` | Fernet key til API-nøgler |
| `OPENAI_API_KEY` | OpenAI (valgfri) |
| `ANTHROPIC_API_KEY` | Anthropic (valgfri) |
| `STRIPE_SECRET_KEY` | Stripe |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhooks |

### Frontend (`frontend/.env.local`)
| Variabel | Beskrivelse |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Anon key |
| `NEXT_PUBLIC_API_URL` | Backend URL |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Stripe public key |

## Generér Fernet encryption key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## GitHub Secrets (til CI/CD)

Tilføj i GitHub repository settings:
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DB_URL` (til migrations: `postgresql://postgres:...@db.xxx.supabase.co:5432/postgres`)
- `ENCRYPTION_KEY`
- `RAILWAY_TOKEN`
- `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`
