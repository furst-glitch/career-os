-- M3: Career Memory Foundation — udvidelser til memory-tabeller

-- Extend memory_type enum med brugervendte typer
ALTER TYPE memory_type ADD VALUE IF NOT EXISTS 'experience';
ALTER TYPE memory_type ADD VALUE IF NOT EXISTS 'skill';
ALTER TYPE memory_type ADD VALUE IF NOT EXISTS 'project';
ALTER TYPE memory_type ADD VALUE IF NOT EXISTS 'reflection';
ALTER TYPE memory_type ADD VALUE IF NOT EXISTS 'career_note';

-- Extend career_preferences med jobpræferencer og AI-præferencer
ALTER TABLE public.career_preferences
  ADD COLUMN IF NOT EXISTS salary_min          int,
  ADD COLUMN IF NOT EXISTS salary_max          int,
  ADD COLUMN IF NOT EXISTS salary_currency     text NOT NULL DEFAULT 'DKK',
  ADD COLUMN IF NOT EXISTS role_types          text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS remote_preference   text NOT NULL DEFAULT 'hybrid',
  ADD COLUMN IF NOT EXISTS ai_preferences      jsonb NOT NULL DEFAULT '{}';

-- ivfflat index til pgvector søgning (kræver extension vector)
-- Oprettes kun hvis embedding-kolonnen indeholder data
CREATE INDEX IF NOT EXISTS career_memories_embedding_idx
  ON public.career_memories
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100)
  WHERE embedding IS NOT NULL;
