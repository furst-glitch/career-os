from __future__ import annotations

import asyncio
import re

from supabase import Client

# ── Match-score konstanter ────────────────────────────────────────────────────

BASE_WEIGHTS: dict[str, float] = {
    "skills":       0.35,
    "experience":   0.25,
    "profile":      0.20,
    "preferences":  0.15,
    "certificates": 0.05,
}

MATCH_THRESHOLDS: dict[str, int] = {
    "green":  70,
    "yellow": 45,
    "grey":   0,
    "skip":   15,
}

DEALBREAKER_SIGNALS: dict[str, dict] = {
    "academic_degree": {
        "job_signals": [
            "cand.merc", "cand.oecon", "cand.jur", "cand.scient",
            "cand.it", "cand.polyt", "kandidatuddannelse",
            "master's degree", "masteruddannelse",
            "hd(r)", "hd-r", "bachelor's degree",
        ],
        "candidate_check": "education_level",
        "severity": "hard",
    },
    "people_management": {
        "job_signals": [
            "personaleansvar", "personaleleder", "people manager",
            "direct reports", "medarbejdere refererer",
            "ledelse af medarbejdere", "lede et team",
            "personalemæssigt ansvar", "hr-ansvar for",
        ],
        "candidate_check": "people_management",
        "severity": "hard",
    },
    "senior_management": {
        "job_signals": [
            "lede gennem ledere", "lead through managers",
            "ledelse af ledere", "chef for chefer",
            "lede driftsledere", "lede sektionschefer",
        ],
        "candidate_check": "senior_management",
        "severity": "hard",
    },
    "eu_procurement": {
        "job_signals": [
            "eu-udbud", "udbudslov", "udbudsjurist",
            "udbudskonsulent", "udbudsretlig",
            "forsyningsvirksomhedsdirektivet",
            "tilbudsloven",
        ],
        "candidate_check": "eu_procurement",
        "severity": "hard",
    },
    "gmp_pharma": {
        "job_signals": [
            "gmp", "fda", "gxp", "pharmaceutical manufacturing",
            "life sciences regulatory", "cleanroom",
        ],
        "candidate_check": "gmp_experience",
        "severity": "hard",
    },
    "aviation": {
        "job_signals": [
            "easa part-145", "part-145", "aviation maintenance",
            "luftfartscertifikat", "camo",
        ],
        "candidate_check": "aviation_experience",
        "severity": "hard",
    },
    "big4_audit": {
        "job_signals": [
            "big 4", "big four", "fra revisionsvirksomhed",
            "revisoruddannelse", "statsautoriseret revisor",
            "acca", "chartered accountant",
        ],
        "candidate_check": "big4_experience",
        "severity": "hard",
    },
    "temp_position": {
        "job_signals": [
            "barselsvikariat", "tidsbegrænset", "vikariat",
            "maternity cover", "fixed term",
        ],
        "candidate_check": "accepts_temp",
        "severity": "soft",
        "score_penalty": 10,
    },
    "salary_mismatch": {
        "job_signals": [],
        "candidate_check": "salary_target",
        "severity": "soft",
        "score_penalty": 15,
    },
}


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
    3. Stamme 4/5 tegn  — "lede" er substreng af "teamleder";
                          "budge" matcher "budgetansvarlig"
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
            return w in job_tokens or any(w in jt for jt in job_tokens if len(jt) > len(w))
        if all(word_in_job(w) for w in words):
            return True

    # 3. Stamme — håndterer bøjninger og danske sammensatte ord.
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
            "full_description":    data.get("full_description"),
            "responsibilities":    data.get("responsibilities"),
            "company_description": data.get("company_description"),
            "scraped_at":          data.get("scraped_at"),
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
            "full_description", "responsibilities", "company_description", "scraped_at",
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

    # ── Match Score — private helpers ─────────────────────────────────────────

    def _build_job_context(self, job: dict) -> tuple[str, set[str], int]:
        """Build lowercase job_text + token set from best available text."""
        job_title = (job.get("title") or "").lower()
        full_desc = job.get("full_description") or ""
        teaser    = job.get("description") or ""
        best_desc = full_desc if len(full_desc) > len(teaser) else teaser
        job_text = " ".join(filter(None, [
            job_title,
            best_desc,
            *job.get("requirements", []),
            job.get("responsibilities") or "",
            job.get("company_description") or "",
        ])).lower()
        return job_text, set(_tokenise(job_text)), len(job_text)

    def _score_skills(
        self, job_text: str, job_tokens: set[str], snapshot: dict
    ) -> tuple[float, list[str]]:
        profile      = snapshot.get("profile", {}) or {}
        target_title = (profile.get("target_title") or "").lower()
        skill_names  = [
            s.get("name", "").lower()
            for s in (snapshot.get("skills") or [])
            if s.get("name")
        ]
        extended = list(dict.fromkeys(
            skill_names + [w for w in target_title.split() if len(w) > 3]
        ))
        matched = [s for s in extended if _match_term(s, job_text, job_tokens)]
        score = (
            min(100.0, len(matched) / len(extended) * 100 * 1.5)
            if extended else 0.0
        )
        return score, matched

    def _score_experience(
        self, job_text: str, job_tokens: set[str], snapshot: dict
    ) -> float:
        exp_data = snapshot.get("experience") or []
        n_exp = min(len(exp_data), 8)

        exp_title_hits = 0
        for exp in exp_data[:8]:
            words = [w for w in _tokenise(exp.get("title", "")) if len(w) > 2]
            if words and any(_match_term(w, job_text, job_tokens) for w in words):
                exp_title_hits += 1
        exp_title_score = min(100.0, exp_title_hits / max(n_exp, 1) * 100 * 2.0) if n_exp else 0.0

        exp_desc_tokens: set[str] = set()
        for exp in exp_data[:5]:
            desc = (exp.get("description") or "") + " " + " ".join(exp.get("achievements", []) or [])
            for w in _tokenise(desc):
                if len(w) > 5:
                    exp_desc_tokens.add(w)
        exp_desc_hits  = sum(1 for t in exp_desc_tokens if _match_term(t, job_text, job_tokens))
        exp_desc_score = min(100.0, exp_desc_hits * 2.5)

        return min(100.0, exp_title_score * 0.60 + exp_desc_score * 0.40)

    def _score_profile(
        self, job_text: str, job_tokens: set[str], snapshot: dict
    ) -> float:
        profile      = snapshot.get("profile", {}) or {}
        target_title = (profile.get("target_title") or "").lower()
        summary      = (profile.get("summary") or "").lower()

        target_words = [w for w in _tokenise(target_title) if len(w) > 3]
        target_hits  = sum(1 for w in target_words if _match_term(w, job_text, job_tokens))
        target_score = (
            min(100.0, target_hits / max(len(target_words), 1) * 100 * 1.5)
            if target_words else 0.0
        )
        summary_tokens = {w for w in _tokenise(summary) if len(w) > 6}
        summary_hits   = sum(1 for t in summary_tokens if _match_term(t, job_text, job_tokens))
        summary_score  = min(100.0, summary_hits * 2.0)
        return min(100.0, target_score * 0.70 + summary_score * 0.30)

    def _preference_score(
        self, job_text: str, job_tokens: set[str], snapshot: dict
    ) -> float:
        prefs      = snapshot.get("preferences", {}) or {}
        role_types = [r.lower() for r in (prefs.get("role_types") or [])]
        industries = [i.lower() for i in (prefs.get("industries") or [])]
        score = 0.0
        if role_types and any(_match_term(rt, job_text, job_tokens) for rt in role_types):
            score += 50.0
        if industries and any(_match_term(ind, job_text, job_tokens) for ind in industries):
            score += 50.0
        return score

    def _score_certificates(
        self, job_text: str, job_tokens: set[str], snapshot: dict
    ) -> tuple[float, list[str]]:
        certs_data = snapshot.get("certifications") or []
        cert_names = [c.get("name", "").lower() for c in certs_data if c.get("name")]
        matched    = [c for c in cert_names if _match_term(c, job_text, job_tokens)]
        return min(100.0, len(matched) * 34.0), matched

    def _compute_dynamic_weights(self, snapshot: dict) -> tuple[dict, dict]:
        """Redistribute weight from empty/sparse signals to populated ones."""
        profile = snapshot.get("profile", {}) or {}
        prefs   = snapshot.get("preferences", {}) or {}

        has_data = {
            "skills": len(snapshot.get("skills") or []) >= 3,
            "experience": len(snapshot.get("experience") or []) >= 1,
            "profile": bool(
                profile.get("summary")
                and len(profile.get("summary", "")) > 50
            ),
            "preferences": (
                len(prefs.get("role_types") or []) >= 1
                or len(prefs.get("industries") or []) >= 1
                or bool(profile.get("salary_expectation"))
                or bool(profile.get("location"))
            ),
            "certificates": len(snapshot.get("certifications") or []) >= 1,
        }

        weights = BASE_WEIGHTS.copy()
        redistributable = 0.0
        active_signals: list[str] = []

        for signal, weight in weights.items():
            if not has_data[signal]:
                redistributable += weight
                weights[signal] = 0.0
            else:
                active_signals.append(signal)

        if active_signals and redistributable > 0:
            total_active = sum(BASE_WEIGHTS[s] for s in active_signals)
            for signal in active_signals:
                weights[signal] += redistributable * (BASE_WEIGHTS[signal] / total_active)

        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights, has_data

    def _check_dealbreakers(self, job: dict, snapshot: dict) -> list[dict]:
        found: list[dict] = []
        job_full_text = " ".join(filter(None, [
            job.get("title") or "",
            job.get("full_description") or job.get("description") or "",
            " ".join(job.get("requirements") or []),
        ])).lower()

        for db_type, config in DEALBREAKER_SIGNALS.items():
            if db_type == "salary_mismatch":
                if self._has_salary_mismatch(job, snapshot):
                    found.append({
                        "type":     db_type,
                        "severity": config["severity"],
                        "penalty":  config.get("score_penalty", 0),
                        "signal":   "Estimeret løn under kandidatens mål",
                        "message":  self._dealbreaker_message(db_type, ""),
                    })
                continue

            matched_signal = next(
                (s for s in config["job_signals"] if s.lower() in job_full_text),
                None,
            )
            if not matched_signal:
                continue

            if not self._candidate_satisfies(config["candidate_check"], snapshot):
                found.append({
                    "type":     db_type,
                    "severity": config["severity"],
                    "penalty":  config.get("score_penalty", 0),
                    "signal":   matched_signal,
                    "message":  self._dealbreaker_message(db_type, matched_signal),
                })

        return found

    def _candidate_satisfies(self, check_type: str, snapshot: dict) -> bool:
        profile    = snapshot.get("profile", {}) or {}
        experience = snapshot.get("experience", []) or []
        skills     = snapshot.get("skills", []) or []
        prefs      = snapshot.get("preferences", {}) or {}

        summary = (profile.get("summary") or "").lower()
        profile_text = " ".join(filter(None, [
            summary,
            " ".join(e.get("title", "") for e in experience[:5]),
            " ".join((e.get("description") or "")[:200] for e in experience[:3]),
        ])).lower()
        skills_text = " ".join(s.get("name", "") for s in skills).lower()

        # If no profile data exists, do not flag as dealbreaker (avoid false positives)
        has_data = bool(summary or experience)

        checks: dict[str, bool] = {
            "education_level": (
                not has_data
                or any(sig in profile_text for sig in [
                    "cand.", "kandidat", "master", "ph.d", "hd",
                    "bachelor", "professionsbachelor", "merkonom",
                    "akademiuddannelse",
                ])
            ),
            "people_management": (
                not has_data
                or any(sig in profile_text for sig in [
                    "personaleansvar", "people manager", "direct reports",
                    "medarbejdere refererer", "personaleleder",
                    "leder for medarbejdere",
                ])
            ),
            "senior_management": (
                not has_data
                or any(sig in profile_text for sig in [
                    "leder for ledere", "chef for chefer",
                    "lead through managers", "lede driftsledere",
                ])
            ),
            "eu_procurement": (
                not has_data
                or any(
                    sig in skills_text or sig in profile_text
                    for sig in ["eu-udbud", "udbudslov", "udbudsjurist", "udbudsret"]
                )
            ),
            "gmp_experience": (
                not has_data
                or any(sig in profile_text for sig in [
                    "gmp", "gxp", "fda", "cleanroom", "pharmaceutical",
                ])
            ),
            "aviation_experience": (
                not has_data
                or any(sig in profile_text for sig in [
                    "easa", "part-145", "aviation", "luftfart",
                ])
            ),
            "big4_experience": (
                not has_data
                or any(
                    sig in profile_text
                    for sig in [
                        "deloitte", "pwc", "kpmg", "ey ", "ernst & young",
                        "big 4", "revisionsvirksomhed",
                    ]
                )
            ),
            "accepts_temp": bool(prefs.get("accepts_temp_positions", False)),
            "salary_target": True,
        }

        return checks.get(check_type, True)

    def _has_salary_mismatch(self, job: dict, snapshot: dict) -> bool:
        profile = snapshot.get("profile", {}) or {}
        target_salary = profile.get("salary_expectation")
        if not target_salary:
            return False
        salary_max = job.get("salary_max")
        if not salary_max:
            return False
        try:
            return float(salary_max) < float(target_salary) * 0.90
        except (TypeError, ValueError):
            return False

    def _dealbreaker_message(self, db_type: str, signal: str) -> str:
        messages: dict[str, str] = {
            "academic_degree":  f"Kræver akademisk uddannelse ({signal})" if signal else "Kræver akademisk uddannelse",
            "people_management": "Kræver formel personaleledelse",
            "senior_management": "Kræver erfaring med ledelse via ledere",
            "eu_procurement":    "Kræver EU-udbudserfaring",
            "gmp_pharma":        "Kræver GMP/pharma-erfaring",
            "aviation":          "Kræver luftfartscertificering",
            "big4_audit":        "Kræver Big 4 revisionsbaggrund",
            "temp_position":     "Tidsbegrænset stilling",
            "salary_mismatch":   "Løn under kandidatens mål",
        }
        return messages.get(db_type, f"Mangler: {signal}")

    async def _embed_text(self, text: str) -> list[float] | None:
        """Embed text via OpenAI text-embedding-3-small. Returns None on any error."""
        try:
            import openai
            client = openai.AsyncOpenAI()
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8191],
            )
            return response.data[0].embedding
        except Exception:
            return None

    async def _semantic_score(self, job: dict, snapshot: dict) -> float | None:
        """
        Returns 0-100 cosine-similarity score, or None if unavailable.
        Cosine similarity for job matching typically ranges 0.3–0.9 → normalized to 0–100.
        """
        try:
            profile    = snapshot.get("profile", {}) or {}
            skills     = snapshot.get("skills", []) or []
            experience = snapshot.get("experience", []) or []

            candidate_parts = list(filter(None, [
                profile.get("summary"),
                " ".join(s.get("name", "") for s in skills[:20]),
                " ".join(e.get("title", "") for e in experience[:3]),
                " ".join(
                    " ".join(e.get("achievements") or [])
                    for e in experience[:2]
                ),
            ]))
            candidate_text = " ".join(candidate_parts).strip()
            if not candidate_text:
                return None

            full_desc = job.get("full_description") or ""
            teaser    = job.get("description") or ""
            job_text  = (full_desc if len(full_desc) > len(teaser) else teaser)[:3000].strip()
            if not job_text:
                return None

            job_emb, cand_emb = await asyncio.gather(
                self._embed_text(job_text),
                self._embed_text(candidate_text),
            )
            if job_emb is None or cand_emb is None:
                return None

            dot    = sum(a * b for a, b in zip(job_emb, cand_emb))
            norm_j = sum(x ** 2 for x in job_emb) ** 0.5
            norm_c = sum(x ** 2 for x in cand_emb) ** 0.5
            if norm_j == 0 or norm_c == 0:
                return None

            similarity = dot / (norm_j * norm_c)
            return max(0.0, min(100.0, (similarity - 0.3) / 0.6 * 100))

        except Exception:
            return None

    # ── Main scoring method ───────────────────────────────────────────────────

    async def compute_match_score(self, job: dict, snapshot: dict) -> dict:
        """
        Multi-signal match scoring med dynamic weights, dealbreaker-detektering
        og valgfri semantisk scoring.

        Jobtekst-hierarki: full_description > description > title

        Returnerer dict kompatibelt med eksisterende API (bevarer "total"-nøgle)
        plus nye felter: dealbreakers, recommendation, reason,
        weights_used, has_data, semantic_score, signal_scores.
        """
        # Step 1: Dealbreakers — afbryd tidligt ved hård mismatch
        dealbreakers     = self._check_dealbreakers(job, snapshot)
        hard_dealbreakers = [d for d in dealbreakers if d["severity"] == "hard"]
        soft_dealbreakers = [d for d in dealbreakers if d["severity"] == "soft"]

        job_text, job_tokens, text_chars_used = self._build_job_context(job)

        if hard_dealbreakers:
            return {
                "total":                12.0,
                "score":                12.0,
                "breakdown":            {},
                "matched_skills":       [],
                "matched_certs":        [],
                "missing_requirements": [],
                "text_chars_used":      text_chars_used,
                "dealbreakers":         dealbreakers,
                "recommendation":       "SKIP",
                "reason":               hard_dealbreakers[0]["message"],
                "weights_used":         {},
                "has_data":             {},
                "semantic_score":       None,
                "signal_scores":        {},
            }

        # Step 2: Dynamic weights based on profile completeness
        weights, has_data = self._compute_dynamic_weights(snapshot)

        # Step 3: Individual signal scores
        signals:       dict[str, float] = {}
        matched_skills: list[str] = []
        matched_certs:  list[str] = []

        if has_data["skills"]:
            s, matched_skills = self._score_skills(job_text, job_tokens, snapshot)
            signals["skills"] = s

        if has_data["experience"]:
            signals["experience"] = self._score_experience(job_text, job_tokens, snapshot)

        if has_data["profile"]:
            signals["profile"] = self._score_profile(job_text, job_tokens, snapshot)

        if has_data["preferences"]:
            signals["preferences"] = self._preference_score(job_text, job_tokens, snapshot)

        if has_data["certificates"]:
            s, matched_certs = self._score_certificates(job_text, job_tokens, snapshot)
            signals["certificates"] = s

        # Step 4: Semantic score (optional, never blocks)
        semantic = await self._semantic_score(job, snapshot)

        # Step 5: Weighted deterministic score
        deterministic = sum(
            signals.get(sig, 0.0) * w
            for sig, w in weights.items()
            if w > 0
        )

        # Step 6: Blend with semantic if available (65/35 split)
        final_score = (
            deterministic * 0.65 + semantic * 0.35
            if semantic is not None
            else deterministic
        )

        # Step 7: Soft dealbreaker penalties
        final_score = max(0.0, final_score - sum(d.get("penalty", 0) for d in soft_dealbreakers))
        final_score = min(100.0, final_score)

        # ── Manglende krav — jobkrav IKKE dækket af kandidatprofilen ─────────
        profile      = snapshot.get("profile", {}) or {}
        target_title = (profile.get("target_title") or "").lower()
        summary      = (profile.get("summary") or "").lower()
        exp_data     = snapshot.get("experience") or []
        skill_names  = [
            s.get("name", "").lower()
            for s in (snapshot.get("skills") or [])
            if s.get("name")
        ]
        candidate_text = " ".join(filter(None, [
            target_title, summary,
            *skill_names,
            *[e.get("title", "") for e in exp_data[:6]],
            *[(e.get("description") or "")[:300] for e in exp_data[:4]],
        ])).lower()
        candidate_tokens = set(_tokenise(candidate_text))

        missing_requirements: list[str] = []
        for req in (job.get("requirements") or [])[:12]:
            req_s = req.strip()
            if len(req_s) < 3:
                continue
            if not _match_term(req_s.lower(), candidate_text, candidate_tokens):
                missing_requirements.append(req_s)

        score = round(final_score, 1)

        return {
            "total":                score,   # backward compat
            "score":                score,
            "breakdown": {
                "skills":         round(signals.get("skills", 0.0), 1),
                "experience":     round(signals.get("experience", 0.0), 1),
                "profile":        round(signals.get("profile", 0.0), 1),
                "preferences":    round(signals.get("preferences", 0.0), 1),
                "certifications": round(signals.get("certificates", 0.0), 1),
            },
            "matched_skills":       matched_skills[:10],
            "matched_certs":        matched_certs[:3],
            "missing_requirements": missing_requirements[:5],
            "text_chars_used":      text_chars_used,
            "dealbreakers":         dealbreakers,
            "recommendation":       self._recommendation(score, dealbreakers),
            "reason":               self._match_reason(score, signals, dealbreakers),
            "weights_used":         weights,
            "has_data":             has_data,
            "semantic_score":       semantic,
            "signal_scores":        signals,
        }

    def _recommendation(self, score: float, dealbreakers: list[dict]) -> str:
        hard = [d for d in dealbreakers if d["severity"] == "hard"]
        soft = [d for d in dealbreakers if d["severity"] == "soft"]
        if hard:
            return "SKIP"
        if score >= 70 and not soft:
            return "APPLY"
        if score >= 70:
            return "CONSIDER"
        if score >= 45:
            return "CONSIDER"
        if score >= 30:
            return "BORDERLINE"
        return "SKIP"

    def _match_reason(
        self, score: float, signals: dict[str, float], dealbreakers: list[dict]
    ) -> str:
        if dealbreakers:
            hard = [d for d in dealbreakers if d["severity"] == "hard"]
            if hard:
                return hard[0]["message"]
            return "Bemærk: " + ", ".join(
                d["message"] for d in dealbreakers if d["severity"] == "soft"
            )
        if not signals:
            return "Utilstrækkelig profildata til præcis scoring"
        strongest = max(signals, key=signals.get)  # type: ignore[arg-type]
        names = {
            "skills":       "kompetencematch",
            "experience":   "erfaringsmatch",
            "profile":      "profilmatch",
            "preferences":  "præferencematch",
            "certificates": "certificeringsmatch",
        }
        return f"Stærkest på {names.get(strongest, strongest)} ({signals[strongest]:.0f}%)"

    def store_match_score(self, job_id: str, score: float) -> None:
        self.db.table("jobs").update({"match_score": score}).eq("id", job_id).execute()
