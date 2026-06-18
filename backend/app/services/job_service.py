from __future__ import annotations

from supabase import Client


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
        """Keyword-baseret match mellem job og karriere-snapshot."""
        job_text = " ".join(
            filter(
                None,
                [
                    job.get("title", ""),
                    job.get("description", ""),
                    *job.get("requirements", []),
                    job.get("company", ""),
                ],
            )
        ).lower()

        # Skills (40%)
        skills = [s.get("name", "").lower() for s in snapshot.get("skills", []) if s.get("name")]
        matched_skills = [s for s in skills if s in job_text]
        skill_score = (
            min(100.0, len(matched_skills) / len(skills) * 100 * 1.5)
            if skills
            else 0.0
        )

        # Experience (30%) — titel + beskrivelse nøgleord
        exp_terms: set[str] = set()
        for exp in snapshot.get("experience", []):
            text = (exp.get("title", "") + " " + exp.get("description", "")).lower()
            for word in text.split():
                if len(word) > 4:
                    exp_terms.add(word)
        exp_matched = sum(1 for t in exp_terms if t in job_text)
        exp_score = min(100.0, exp_matched * 5.0)

        # Præferencer (20%) — rolletyper + brancher
        prefs = snapshot.get("preferences", {})
        role_types = [r.lower() for r in prefs.get("role_types", [])]
        industries = [i.lower() for i in prefs.get("industries", [])]
        pref_score = 0.0
        if role_types and any(rt in job_text for rt in role_types):
            pref_score += 50.0
        if industries and any(ind in job_text for ind in industries):
            pref_score += 50.0

        # Certifikater (10%)
        certs = [c.get("name", "").lower() for c in snapshot.get("certifications", []) if c.get("name")]
        matched_certs = [c for c in certs if c in job_text]
        cert_score = min(100.0, len(matched_certs) * 34.0)

        total = round(
            skill_score * 0.40
            + exp_score * 0.30
            + pref_score * 0.20
            + cert_score * 0.10,
            1,
        )

        return {
            "total": total,
            "breakdown": {
                "skills": round(skill_score, 1),
                "experience": round(exp_score, 1),
                "preferences": round(pref_score, 1),
                "certifications": round(cert_score, 1),
            },
            "matched_skills": matched_skills[:8],
            "matched_certs": matched_certs[:3],
        }

    def store_match_score(self, job_id: str, score: float) -> None:
        self.db.table("jobs").update({"match_score": score}).eq("id", job_id).execute()
