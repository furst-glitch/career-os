-- 00054_fact_verification_audit.sql
-- Tilføj verifikationsaudit-felter til document_facts.
--
-- Formål (WP4 — Human Verification):
--   - Spor HVEM, HVORNÅR og HVORFOR en bruger rettede eller godkendte et faktum.
--   - Gem gammel værdi så ændringshistorik er mulig.
--   - Faktum med `verified_at` IS NOT NULL = bruger har taget stilling.
--     Brugerens beslutning har altid højere prioritet end AI.
--
-- Alle felter er nullable — eksisterende rækker er uberørte.
-- Idempotent: ADD COLUMN IF NOT EXISTS.

ALTER TABLE public.document_facts
    ADD COLUMN IF NOT EXISTS verified_by         uuid         REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS verified_at         timestamptz,
    ADD COLUMN IF NOT EXISTS previous_value      text,
    ADD COLUMN IF NOT EXISTS verification_reason text;

-- Index til at finde verificerede vs. ikke-verificerede fakta effektivt
CREATE INDEX IF NOT EXISTS idx_document_facts_verified_at
    ON public.document_facts (verified_at)
    WHERE verified_at IS NOT NULL;
