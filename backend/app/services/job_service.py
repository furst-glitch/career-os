from __future__ import annotations

import re

from supabase import Client

# ── Hjælpefunktioner til match scoring ───────────────────────────────────────

def _tokenise(text: str) -> list[str]:
    """Lowercase ord fra tekst — beholder æøå."""
    return re.findall(r"[a-zæøåA-ZÆØÅ][a-zæøåA-ZÆØÅ']{1,}", text.lower())


def _match_term(term: str, job_text: str, job_tokens: set[str]) -> bool:
    """
    Returnerer True hvis term matcher i jobteksten via én af tre strategier:

    1. Eksakt substreng  — "facility management" i "...facility management..."
    2. Ordniveau         — hvert signifikant ord i term er substreng af mindst
                          ét jobord (dækker danske sammensætninger:
                          "ledelse" → "leder" er delstreng af "teamleder")
    3. Stamme (5 tegn)   — term[:5] er præfiks af mindst ét jobord
                          (dækker bøjninger: "procurement" → "procur" i "procurement")
    """
    if not term:
        return False

    # 1. Eksakt substreng
    if term in job_text:
        return True

    # 2. Ordniveau — alle væsentlige ord i term skal matche mindst ét jobord
    words = [w for w in term.split() if len(w) > 2]
    if words:
        def word_in_job(w: str) -> bool:
            # direkte match eller som delstreng i et jobord (f.eks. "leder" i "teamleder")
            return w in job_tokens or any(w in jt for jt in job_tokens if len(jt) > len(w))
        if all(word_in_job(w) for w in words):
            return True

    # 3. Stamme — håndterer bøjninger og danske sammensatte ord.
    #    Bruger 4 tegn for lange ord (≥7 tegn) så "ledelse" → "lede" matcher "teamleder",
    #    og 5 tegn for mellemlange ord så "budge" matcher "budgetansvarlig".
    for stem_len in (4, 5):
        if len(term) >= stem_len + 2:
            stem = term[:stem_len]
            if any(stem in jt for jt in job_tokens if len(jt) >= stem_len):
                return True

    return False


class JobService:
    def __init__(self, db: Client) -> None:
        self.db = db

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create_job(self, user_id: str, data: dict) -> dict:
        payload = {
            "user_id": user_id,
            "title": data.get("title", ""),
            "company": data.get("company", ""),
            "location": data.get("location"),
            "url": data.get("url"),
            "description": data.get("description"),
            "requirements": data.get("requirements", []),
            "salary_min": data.get("salary_min"),
            "salary_max": data.get("salary_max"),
            "source": data.get("source", "manual"),
            "job_type": data.get("job_type", "full_time"),
            "remote_type": data.get("remote_type", "hybrid"),
            "notes": data.get("notes"),
            "is_saved": data.get("is_saved", True),
        }
        result = self.db.table("jobs").insert(payload).execute()
        return result.data[0]

    def list_jobs(
        self,
        user_id: str,
        saved_only: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        q = self.db.table("jobs").select("*").eq("user_id", user_id).order(
            "created_at", desc=True
        ).limit(limit)
        if saved_only:
            q = q.eq("is_saved", True)
        jobs = q.execute().data or []

        # Tilknyt pipeline-status
        if jobs:
            job_ids = [j["id"] for j in jobs]
            pipeline_rows = (
                self.db.table("application_pipeline")
                .select("job_id, current_status, priority, id")
                .eq("user_id", user_id)
                .in_("job_id", job_ids)
                .execute()
                .data or []
            )
            pipeline_map = {p["job_id"]: p for p in pipeline_rows}
            for job in jobs:
                p = pipeline_map.get(job["id"])
                job["pipeline_status"] = p["current_status"] if p else None
                job["pipeline_id"] = p["id"] if p else None
                job["pipeline_priority"] = p["priority"] if p else None

        return jobs

    def get_job(self, job_id: str, user_id: str) -> dict | None:
        result = (
            self.db.table("jobs")
            .select("*")
            .eq("id", job_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        job = result.data[0]
        pipeline = (
            self.db.table("application_pipeline")
            .select("id, current_status, priority, deadline")
            .eq("job_id", job_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        p = pipeline.data[0] if pipeline.data else None
        job["pipeline_status"] = p["current_status"] if p else None
        job["pipeline_id"] = p["id"] if p else None
        return job

    def update_job(self, job_id: str, user_id: str, data: dict) -> dict:
        allowed = {
            "title", "company", "location", "url", "description",
            "requirements", "salary_min", "salary_max", "job_type",
            "remote_type", "notes", "is_saved",
        }
        payload = {k: v for k, v in data.items() if k in allowed}
        result = (
            self.db.table("jobs")
            .update(payload)
            .eq("id", job_id)
            .eq("user_id", user_id)
            .execute()
        )
        return result.data[0]

    def delete_job(self, job_id: str, user_id: str) -> None:
        self.db.table("jobs").delete().eq("id", job_id).eq("user_id", user_id).execute()

    def toggle_save(self, job_id: str, user_id: str) -> dict:
        current = self.get_job(job_id, user_id)
        if not current:
            raise ValueError("Job ikke fundet")
        new_saved = not current.get("is_saved", False)
        result = (
            self.db.table("jobs")
            .update({"is_saved": new_saved})
            .eq("id", job_id)
            .eq("user_id", user_id)
            .execute()
        )
        return result.data[0]

    # ── Match Score ───────────────────────────────────────────────────────────

    def compute_match_score(self, job: dict, snapshot: dict) -> dict:
        """
        Multi-signal match scoring der afspejler den faktiske kandidatprofil.

        Fem signaler med forskellig vægt:

          Signal                  Vægt   Kilde
          ─────────────────────── ────   ──────────────────────────────────
          Kompetencer (skills)    35 %   cv_skills + target_title ord
          Erfaring                25 %   cv_experiences titler (primær) +
                                         beskrivelsesnøgleord (sekundær)
          Profil-signal           20 %   target_title + master_cv summary
          Præferencer             15 %   role_types + industries
          Certifikater             5 %   cv_certifications

        Matchstrategi pr. term:
          1. Eksakt substreng   — "facility management" i jobtekst
          2. Ordniveau          — "ledelse" → "leder" delstreng i "teamleder"
          3. Stamme 5 tegn      — "budgetansvar" → "budge" præfiks i "budget"
        """
        profile      = snapshot.get("profile", {})
        target_title = (profile.get("target_title") or "").lower()
        summary      = (profile.get("summary") or "").lower()

        # Byg jobrepræsentation
        job_title = (job.get("title") or "").lower()
        job_text = " ".join(filter(None, [
            job_title,
            job.get("description") or "",
            *job.get("requirements", []),
        ])).lower()
        job_tokens: set[str] = set(_tokenise(job_text))

        skills_data  = snapshot.get("skills", [])
        exp_data     = snapshot.get("experience", [])
        certs_data   = snapshot.get("certifications", [])
        prefs        = snapshot.get("preferences", {})

        skill_names  = [s.get("name", "").lower() for s in skills_data if s.get("name")]
        cert_names   = [c.get("name", "").lower() for c in certs_data  if c.get("name")]

        # ── 1. Kompetencer (35 %) ─────────────────────────────────────────────
        # Udvid med target_title-ord som pseudo-kompetencer
        extended_skills = list(dict.fromkeys(
            skill_names
            + [w for w in target_title.split() if len(w) > 3]
        ))
        matched_skills = [s for s in extended_skills if _match_term(s, job_text, job_tokens)]
        n_skills = len(extended_skills)
        skill_score = (
            min(100.0, len(matched_skills) / n_skills * 100 * 1.5)
            if n_skills else 0.0
        )

        # ── 2. Erfaring (25 %) ───────────────────────────────────────────────
        # 2a. Titelmatch (6 af 10 point): erfaringstitler mod jobtitel + krav
        exp_title_hits = 0
        n_exp = min(len(exp_data), 8)
        for exp in exp_data[:8]:
            exp_title_words = [w for w in _tokenise(exp.get("title", "")) if len(w) > 2]
            if exp_title_words and any(_match_term(w, job_text, job_tokens) for w in exp_title_words):
                exp_title_hits += 1

        exp_title_score = min(100.0, exp_title_hits / max(n_exp, 1) * 100 * 2.0) if n_exp else 0.0

        # 2b. Beskrivelsesnøgleord (4 af 10 point)
        exp_desc_tokens: set[str] = set()
        for exp in exp_data[:5]:
            desc = (exp.get("description") or "") + " " + " ".join(exp.get("achievements", []) or [])
            for w in _tokenise(desc):
                if len(w) > 5:
                    exp_desc_tokens.add(w)

        exp_desc_hits  = sum(1 for t in exp_desc_tokens if _match_term(t, job_text, job_tokens))
        exp_desc_score = min(100.0, exp_desc_hits * 2.5)

        exp_score = min(100.0, exp_title_score * 0.60 + exp_desc_score * 0.40)

        # ── 3. Profil-signal (20 %) ──────────────────────────────────────────
        # target_title ord mod jobtitel (stærkt signal)
        target_words = [w for w in _tokenise(target_title) if len(w) > 3]
        target_hits  = sum(1 for w in target_words if _match_term(w, job_text, job_tokens))
        target_score = min(100.0, target_hits / max(len(target_words), 1) * 100 * 1.5) if target_words else 0.0

        # summary-termer mod jobtekst (fallback for ufuldstændig profil)
        summary_tokens = {w for w in _tokenise(summary) if len(w) > 6}
        summary_hits   = sum(1 for t in summary_tokens if _match_term(t, job_text, job_tokens))
        summary_score  = min(100.0, summary_hits * 2.0)

        profile_score = min(100.0, target_score * 0.70 + summary_score * 0.30)

        # ── 4. Præferencer (15 %) ────────────────────────────────────────────
        role_types = [r.lower() for r in prefs.get("role_types", [])]
        industries = [i.lower() for i in prefs.get("industries", [])]
        pref_score = 0.0
        if role_types and any(_match_term(rt, job_text, job_tokens) for rt in role_types):
            pref_score += 50.0
        if industries and any(_match_term(ind, job_text, job_tokens) for ind in industries):
            pref_score += 50.0

        # ── 5. Certifikater (5 %) ────────────────────────────────────────────
        matched_certs = [c for c in cert_names if _match_term(c, job_text, job_tokens)]
        cert_score    = min(100.0, len(matched_certs) * 34.0)

        total = round(
            skill_score   * 0.35
            + exp_score   * 0.25
            + profile_score * 0.20
            + pref_score  * 0.15
            + cert_score  * 0.05,
            1,
        )

        return {
            "total": total,
            "breakdown": {
                "skills":         round(skill_score, 1),
                "experience":     round(exp_score, 1),
                "profile":        round(profile_score, 1),
                "preferences":    round(pref_score, 1),
                "certifications": round(cert_score, 1),
            },
            "matched_skills": matched_skills[:10],
            "matched_certs":  matched_certs[:3],
        }

    def store_match_score(self, job_id: str, score: float) -> None:
        self.db.table("jobs").update({"match_score": score}).eq("id", job_id).execute()
