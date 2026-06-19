-- Sprint 7.1: Job Search History
CREATE TABLE IF NOT EXISTS job_search_history (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  query       text        NOT NULL,
  location    text,
  sources     text[]      NOT NULL DEFAULT '{}',
  results_count int       NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE job_search_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "search_history_owner"
  ON job_search_history FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS job_search_history_user_created
  ON job_search_history (user_id, created_at DESC);
