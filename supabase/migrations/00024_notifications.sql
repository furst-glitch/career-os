-- Sprint 8: Notification center
CREATE TABLE IF NOT EXISTS public.notifications (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    event_type  text NOT NULL,  -- 'job_found' | 'job_saved' | 'cv_uploaded' | 'ai_recommendation' | 'interview_reminder'
    title       text NOT NULL,
    body        text NOT NULL DEFAULT '',
    ref_id      text,           -- optional reference (job_id, pipeline_id, etc.)
    is_read     boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS notifications_user_unread
    ON public.notifications (user_id, is_read, created_at DESC);

-- RLS
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own notifications"
    ON public.notifications FOR ALL
    USING (user_id = auth.uid());
