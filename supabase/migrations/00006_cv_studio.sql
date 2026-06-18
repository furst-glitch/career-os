-- CV Studio
-- Master CV med underafsnit (erfaringer, uddannelse, kompetencer)

CREATE TABLE public.master_cvs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
  title       text NOT NULL DEFAULT 'Mit CV',
  summary     text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.cv_experiences (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  master_cv_id  uuid REFERENCES public.master_cvs(id) ON DELETE CASCADE NOT NULL,
  title         text NOT NULL,
  company       text NOT NULL,
  location      text,
  period_start  date NOT NULL,
  period_end    date,
  description   text,
  achievements  text[] NOT NULL DEFAULT '{}',
  is_current    bool NOT NULL DEFAULT false,
  sort_order    int NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.cv_educations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  master_cv_id  uuid REFERENCES public.master_cvs(id) ON DELETE CASCADE NOT NULL,
  degree        text NOT NULL,
  institution   text NOT NULL,
  location      text,
  period_start  date,
  period_end    date,
  description   text,
  grade         text,
  sort_order    int NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.cv_skills (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  master_cv_id  uuid REFERENCES public.master_cvs(id) ON DELETE CASCADE NOT NULL,
  name          text NOT NULL,
  category      text,
  level         text,
  sort_order    int NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER master_cvs_updated_at
  BEFORE UPDATE ON public.master_cvs
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Auto-opret master CV ved ny profil
CREATE OR REPLACE FUNCTION public.handle_new_profile()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.master_cvs (user_id) VALUES (NEW.user_id)
  ON CONFLICT (user_id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER on_profile_created
  AFTER INSERT ON public.user_profiles
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_profile();
