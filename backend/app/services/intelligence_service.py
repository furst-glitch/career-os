"""
IntelligenceService — Platform Intelligence Engine.

WP2: Product Analytics       — KPI beregning fra events + tabeller
WP3: Product Health Score    — vægtet sundhedsscore med komponentforklaring
WP4: Operational Intelligence — fejl, flaskehalse, budgetalerter
WP6: Prioritization Engine   — datadrevet top-10 liste uden AI-gæt
WP7: Executive Report        — struktureret ugentlig rapport til CEO/CTO

Alle metoder er læse-only. Ingen AI-kald. Deterministisk.
Fejl håndteres defensivt — delvise resultater returneres altid.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("app.intelligence")

# Approksimative MRR-bidrag per plan (DKK/md)
_PLAN_MRR_DKK: dict[str, int] = {
    "free": 0,
    "pro": 299,
    "professional": 799,
    "enterprise": 1999,
}


class IntelligenceService:
    def __init__(self, supabase) -> None:
        self._db = supabase

    # ── Low-level helpers ─────────────────────────────────────────────────────

    def _events_since(self, event_type: str, since: datetime, limit: int = 5000) -> list[dict]:
        try:
            r = (
                self._db.table("platform_events")
                .select("user_id, employment_id, document_id, properties, occurred_at")
                .eq("event_type", event_type)
                .gte("occurred_at", since.isoformat())
                .order("occurred_at", desc=True)
                .limit(limit)
                .execute()
            )
            return r.data or []
        except Exception as exc:
            logger.warning("events_since_failed type=%s error=%s", event_type, exc)
            return []

    def _count(self, event_type: str, since: datetime) -> int:
        return len(self._events_since(event_type, since))

    def _all_events_since(self, since: datetime, limit: int = 10000) -> list[dict]:
        try:
            r = (
                self._db.table("platform_events")
                .select("event_type, user_id, properties, occurred_at")
                .gte("occurred_at", since.isoformat())
                .order("occurred_at", desc=True)
                .limit(limit)
                .execute()
            )
            return r.data or []
        except Exception as exc:
            logger.warning("all_events_since_failed error=%s", exc)
            return []

    def _distinct_users(self, events: list[dict]) -> int:
        return len({e["user_id"] for e in events if e.get("user_id")})

    def _table_count(self, table: str, **filters) -> int:
        try:
            q = self._db.table(table).select("id", count="exact")
            for k, v in filters.items():
                if v == "__not_null__":
                    q = q.not_.is_(k, "null")
                else:
                    q = q.eq(k, v)
            r = q.limit(0).execute()
            return r.count or 0
        except Exception as exc:
            logger.warning("table_count_failed table=%s error=%s", table, exc)
            return 0

    def _table_data(self, table: str, select: str, limit: int = 1000, **filters) -> list[dict]:
        try:
            q = self._db.table(table).select(select)
            for k, v in filters.items():
                q = q.eq(k, v)
            r = q.limit(limit).execute()
            return r.data or []
        except Exception as exc:
            logger.warning("table_data_failed table=%s error=%s", table, exc)
            return []

    def _ai_cost_since(self, since: datetime) -> float:
        try:
            r = (
                self._db.table("ai_usage")
                .select("cost_usd")
                .gte("created_at", since.isoformat())
                .limit(10000)
                .execute()
            )
            return round(sum((row.get("cost_usd") or 0) for row in (r.data or [])), 4)
        except Exception:
            return 0.0

    # ── WP2: Product Analytics ────────────────────────────────────────────────

    def get_analytics(self, days: int = 30) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        since_7 = datetime.now(timezone.utc) - timedelta(days=7)

        # Events
        uploaded   = self._count(  "document.uploaded",           since)
        analyzed   = self._count(  "document.analyzed",           since)
        failed     = self._count(  "document.failed",             since)
        verified   = self._count(  "fact.verified",               since)
        chats      = self._count(  "chat.completed",              since)
        resolved   = self._count(  "recommendation.resolved",     since)
        dismissed  = self._count(  "recommendation.dismissed",    since)

        # Rates
        analysis_total = analyzed + failed
        analysis_success_pct = round(analyzed / analysis_total * 100) if analysis_total else 100

        # Facts from DB (more accurate than events for verification rate)
        facts_total    = self._table_count("document_facts")
        facts_verified = self._table_count("document_facts", verified_at="__not_null__")
        verification_rate_pct = round(facts_verified / facts_total * 100) if facts_total else 0

        # Recommendations from DB
        recs_total    = self._table_count("employment_recommendations")
        recs_resolved = 0
        try:
            r = (
                self._db.table("employment_recommendations")
                .select("id", count="exact")
                .in_("status", ["resolved", "dismissed"])
                .limit(0)
                .execute()
            )
            recs_resolved = r.count or 0
        except Exception:
            pass
        resolution_rate_pct = round(recs_resolved / recs_total * 100) if recs_total else 0

        # AI cost
        ai_cost_usd  = self._ai_cost_since(since)
        ai_cost_7d   = self._ai_cost_since(since_7)

        # Active users (distinct users with events)
        all_events = self._all_events_since(since)
        active_users = self._distinct_users(all_events)

        # TTFV: median time from account creation to first document.analyzed
        ttfv_days = self._compute_ttfv()

        # Subscriptions / revenue
        subs = self._table_data("subscriptions", "plan, status")
        active_subs = [s for s in subs if s.get("status") != "cancelled"]
        mrr_dkk = sum(_PLAN_MRR_DKK.get(s.get("plan", "free"), 0) for s in active_subs)
        paid_subs = [s for s in active_subs if s.get("plan", "free") != "free"]
        free_subs = [s for s in active_subs if s.get("plan", "free") == "free"]

        # Retention (D7: users active in first week still active last 7d)
        retention = self._compute_retention()

        # Average analysis duration (from properties.duration_ms)
        avg_analysis_ms = self._avg_prop(
            self._events_since("document.analyzed", since), "duration_ms"
        )
        avg_chat_ms = self._avg_prop(
            self._events_since("chat.completed", since), "duration_ms"
        )

        return {
            "period_days": days,
            "since": since.isoformat(),
            "documents": {
                "uploaded": uploaded,
                "analyzed": analyzed,
                "failed": failed,
                "analysis_success_rate_pct": analysis_success_pct,
                "avg_analysis_time_ms": avg_analysis_ms,
            },
            "facts": {
                "total": facts_total,
                "verified": facts_verified,
                "verification_rate_pct": verification_rate_pct,
            },
            "recommendations": {
                "total": recs_total,
                "resolved_or_dismissed": recs_resolved,
                "resolution_rate_pct": resolution_rate_pct,
                "resolved_this_period": resolved,
                "dismissed_this_period": dismissed,
            },
            "chat": {
                "completed": chats,
                "avg_chat_time_ms": avg_chat_ms,
            },
            "ai": {
                "cost_usd_period": ai_cost_usd,
                "cost_usd_7d": ai_cost_7d,
            },
            "users": {
                "active_in_period": active_users,
                "time_to_first_value_days": ttfv_days,
                "retention": retention,
            },
            "revenue": {
                "subscriptions_total": len(active_subs),
                "subscriptions_paid": len(paid_subs),
                "subscriptions_free": len(free_subs),
                "mrr_dkk": mrr_dkk,
                "arr_dkk": mrr_dkk * 12,
                "conversion_rate_pct": round(len(paid_subs) / len(active_subs) * 100) if active_subs else 0,
            },
        }

    def _avg_prop(self, events: list[dict], prop: str) -> int | None:
        vals = [
            e["properties"][prop] for e in events
            if isinstance(e.get("properties"), dict) and e["properties"].get(prop)
        ]
        return round(sum(vals) / len(vals)) if vals else None

    def _compute_ttfv(self) -> float | None:
        """Median days from account creation to first document.analyzed event."""
        try:
            # Get all document.analyzed events with user_id
            r = (
                self._db.table("platform_events")
                .select("user_id, occurred_at")
                .eq("event_type", "document.analyzed")
                .not_.is_("user_id", "null")
                .order("occurred_at")
                .limit(1000)
                .execute()
            )
            events = r.data or []
            if not events:
                return None

            # Get user profile created_at
            user_ids = list({e["user_id"] for e in events})
            profiles = self._table_data(
                "user_profiles", "user_id, created_at", limit=len(user_ids) + 10
            )
            created_map = {p["user_id"]: p["created_at"] for p in profiles}

            # First event per user
            first_event: dict[str, str] = {}
            for e in events:
                uid = e["user_id"]
                if uid not in first_event:
                    first_event[uid] = e["occurred_at"]

            diffs = []
            for uid, first_analyzed in first_event.items():
                created = created_map.get(uid)
                if not created:
                    continue
                try:
                    t0 = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    t1 = datetime.fromisoformat(first_analyzed.replace("Z", "+00:00"))
                    diffs.append((t1 - t0).total_seconds() / 86400)
                except Exception:
                    pass

            if not diffs:
                return None
            diffs.sort()
            mid = len(diffs) // 2
            return round(diffs[mid], 1)
        except Exception as exc:
            logger.warning("ttfv_failed error=%s", exc)
            return None

    def _compute_retention(self) -> dict:
        """D7 retention: fraction of users active in first week still active last 7d."""
        try:
            now = datetime.now(timezone.utc)
            week_ago = now - timedelta(days=7)
            two_weeks_ago = now - timedelta(days=14)

            prev_week = self._all_events_since(two_weeks_ago)
            prev_week = [e for e in prev_week if e.get("occurred_at", "") < week_ago.isoformat()]
            curr_week = self._all_events_since(week_ago)

            prev_users = {e["user_id"] for e in prev_week if e.get("user_id")}
            curr_users = {e["user_id"] for e in curr_week if e.get("user_id")}

            retained = prev_users & curr_users
            d7 = round(len(retained) / len(prev_users) * 100) if prev_users else None
            return {"d7_pct": d7, "active_prev_week": len(prev_users), "active_this_week": len(curr_users)}
        except Exception:
            return {"d7_pct": None, "active_prev_week": 0, "active_this_week": 0}

    # ── WP3: Product Health Score ─────────────────────────────────────────────

    def get_health_score(self) -> dict:
        since_7  = datetime.now(timezone.utc) - timedelta(days=7)
        since_30 = datetime.now(timezone.utc) - timedelta(days=30)

        # Component 1: Stability (25%) — document failure rate
        uploaded_7 = self._count("document.uploaded", since_7)
        failed_7   = self._count("document.failed",   since_7)
        error_rate = (failed_7 / max(1, uploaded_7)) * 100 if uploaded_7 else 0
        stability = max(0, round(100 - error_rate))

        # Component 2: AI Performance (20%) — chat completions vs ai errors
        chats_7     = self._count("chat.completed", since_7)
        ai_errors_7 = self._count("ai.error",       since_7)
        ai_score = round(chats_7 / max(1, chats_7 + ai_errors_7) * 100) if (chats_7 + ai_errors_7) else 100

        # Component 3: Analysis Quality (20%) — high+medium confidence facts
        facts_total = self._table_count("document_facts")
        facts_low   = self._table_count("document_facts", confidence="low")
        quality_facts = max(0, facts_total - facts_low)
        quality_score = round(quality_facts / max(1, facts_total) * 100) if facts_total else 100

        # Component 4: User Engagement (15%) — distinct active users last 7d
        events_7 = self._all_events_since(since_7)
        dau_7 = self._distinct_users(events_7)
        engagement_score = min(100, dau_7 * 20)  # 5 users = 100

        # Component 5: Trust Score (10%) — fact verification rate
        facts_verified = self._table_count("document_facts", verified_at="__not_null__")
        trust_score = round(facts_verified / max(1, facts_total) * 100) if facts_total else 0

        # Component 6: Resolution Rate (10%) — open recommendations resolved
        recs_total = self._table_count("employment_recommendations")
        try:
            r = (
                self._db.table("employment_recommendations")
                .select("id", count="exact")
                .in_("status", ["resolved", "dismissed"])
                .limit(0)
                .execute()
            )
            recs_resolved = r.count or 0
        except Exception:
            recs_resolved = 0
        resolution_score = round(recs_resolved / max(1, recs_total) * 100) if recs_total else 100

        # Weighted average
        score = round(
            stability       * 0.25
            + ai_score      * 0.20
            + quality_score * 0.20
            + engagement_score * 0.15
            + trust_score   * 0.10
            + resolution_score * 0.10
        )

        grade = "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"

        # Trend: compare to 7 days ago (approximate)
        prev_uploaded = self._count("document.uploaded", since_30)
        trend = "stable"
        if uploaded_7 > prev_uploaded * 0.15:
            trend = "improving"
        elif uploaded_7 < prev_uploaded * 0.05:
            trend = "declining"

        return {
            "score": score,
            "grade": grade,
            "trend": trend,
            "components": {
                "stability":       {"score": stability,        "weight": 0.25, "label": "Stabilitet",         "detail": f"{error_rate:.1f}% fejlrate på dokumentanalyse"},
                "ai_performance":  {"score": ai_score,         "weight": 0.20, "label": "AI Performance",     "detail": f"{chats_7} chatsvars, {ai_errors_7} AI-fejl (7d)"},
                "analysis_quality":{"score": quality_score,    "weight": 0.20, "label": "Analysekvalitet",    "detail": f"{quality_facts}/{facts_total} fakta er high/medium confidence"},
                "user_engagement": {"score": engagement_score, "weight": 0.15, "label": "Brugeraktivitet",    "detail": f"{dau_7} aktive brugere seneste 7 dage"},
                "trust_score":     {"score": trust_score,      "weight": 0.10, "label": "Trust Score",        "detail": f"{facts_verified}/{facts_total} fakta verificeret af bruger"},
                "resolution_rate": {"score": resolution_score, "weight": 0.10, "label": "Løsningsrate",       "detail": f"{recs_resolved}/{recs_total} anbefalinger løst"},
            },
        }

    # ── WP4: Operational Intelligence ────────────────────────────────────────

    def get_operational(self) -> dict:
        since_7  = datetime.now(timezone.utc) - timedelta(days=7)
        since_30 = datetime.now(timezone.utc) - timedelta(days=30)

        all_events_7 = self._all_events_since(since_7)
        all_events_30 = self._all_events_since(since_30)

        # Top error types
        error_events = [e for e in all_events_30 if "failed" in e["event_type"] or "error" in e["event_type"]]
        error_counter: Counter = Counter(e["event_type"] for e in error_events)
        top_errors = [
            {"event_type": t, "count": c, "label": _event_label(t)}
            for t, c in error_counter.most_common(10)
        ]

        # Document types with high failure rate
        uploaded_events = self._events_since("document.uploaded", since_30)
        failed_events   = self._events_since("document.failed",   since_30)
        uploaded_by_type: Counter = Counter(
            e["properties"].get("doc_type", "ukendt") for e in uploaded_events
        )
        failed_by_type: Counter = Counter(
            e["properties"].get("doc_type", "ukendt") for e in failed_events
        )
        doc_type_health = []
        for doc_type, total in uploaded_by_type.most_common():
            failures = failed_by_type.get(doc_type, 0)
            fail_rate = round(failures / max(1, total) * 100)
            doc_type_health.append({
                "doc_type": doc_type,
                "uploaded": total,
                "failed": failures,
                "failure_rate_pct": fail_rate,
                "alert": fail_rate > 15,
            })

        # Slowest operations (from duration_ms property)
        analyzed_events = self._events_since("document.analyzed", since_30)
        slow_analyses = sorted(
            [
                {
                    "doc_type": e["properties"].get("doc_type"),
                    "facts": e["properties"].get("facts_total"),
                    "duration_ms": e["properties"]["duration_ms"],
                    "occurred_at": e["occurred_at"],
                }
                for e in analyzed_events
                if isinstance(e.get("properties"), dict) and e["properties"].get("duration_ms")
            ],
            key=lambda x: x["duration_ms"],
            reverse=True,
        )[:10]

        # Users with most errors (potential churn risk)
        user_error_counts: Counter = Counter(
            e["user_id"] for e in error_events if e.get("user_id")
        )
        top_error_users = [
            {"user_id": uid, "error_count": cnt}
            for uid, cnt in user_error_counts.most_common(5)
        ]

        # AI cost per user (last 30 days)
        ai_per_user = self._ai_cost_per_user(since_30)

        # Budget alerts: users with >$1 AI spend in 7 days
        ai_7d_per_user = self._ai_cost_per_user(since_7)
        budget_alerts = [
            {"user_id": uid, "cost_usd_7d": cost}
            for uid, cost in ai_7d_per_user.items()
            if cost > 1.0
        ]

        # Active users per day (last 7)
        daily_active = self._daily_active_users(all_events_7)

        return {
            "top_errors": top_errors,
            "doc_type_health": doc_type_health,
            "slowest_analyses": slow_analyses,
            "top_error_users": top_error_users,
            "ai_cost_per_user_usd": ai_per_user,
            "budget_alerts": budget_alerts,
            "daily_active_users_7d": daily_active,
        }

    def _ai_cost_per_user(self, since: datetime) -> dict[str, float]:
        try:
            r = (
                self._db.table("ai_usage")
                .select("user_id, cost_usd")
                .gte("created_at", since.isoformat())
                .limit(10000)
                .execute()
            )
            totals: dict[str, float] = defaultdict(float)
            for row in (r.data or []):
                uid = row.get("user_id")
                cost = row.get("cost_usd") or 0
                if uid:
                    totals[uid] += cost
            return {uid: round(cost, 4) for uid, cost in totals.items()}
        except Exception:
            return {}

    def _daily_active_users(self, events: list[dict]) -> list[dict]:
        by_day: dict[str, set] = defaultdict(set)
        for e in events:
            day = (e.get("occurred_at") or "")[:10]
            uid = e.get("user_id")
            if day and uid:
                by_day[day].add(uid)
        return [
            {"date": day, "active_users": len(users)}
            for day, users in sorted(by_day.items())
        ]

    # ── WP6: Prioritization Engine ────────────────────────────────────────────

    def get_priorities(self) -> dict:
        since_30 = datetime.now(timezone.utc) - timedelta(days=30)

        # Gather signals
        uploaded   = self._count("document.uploaded",        since_30)
        analyzed   = self._count("document.analyzed",        since_30)
        failed     = self._count("document.failed",          since_30)
        chats      = self._count("chat.completed",           since_30)
        verified   = self._count("fact.verified",            since_30)
        facts_total    = self._table_count("document_facts")
        facts_verified = self._table_count("document_facts", verified_at="__not_null__")
        recs_total  = self._table_count("employment_recommendations")
        try:
            r = (
                self._db.table("employment_recommendations")
                .select("id", count="exact")
                .eq("status", "pending")
                .limit(0)
                .execute()
            )
            recs_pending = r.count or 0
        except Exception:
            recs_pending = 0

        analysis_total = analyzed + failed
        analysis_fail_pct = round(failed / max(1, analysis_total) * 100) if analysis_total else 0
        verification_pct  = round(facts_verified / max(1, facts_total) * 100) if facts_total else 0
        resolution_pct    = round((recs_total - recs_pending) / max(1, recs_total) * 100) if recs_total else 100

        fixes: list[dict] = []
        ux_improvements: list[dict] = []
        opportunities: list[dict] = []

        # ── Top Fixes ──
        if analysis_fail_pct > 10:
            fixes.append({
                "title": "Reducér dokumentanalysefejlrate",
                "evidence": f"{analysis_fail_pct}% af {analysis_total} analyser fejler — over 10% tærsklen",
                "impact": "high",
                "effort": "medium",
            })

        # Doc type–specific failures
        failed_events = self._events_since("document.failed", since_30)
        failed_by_type: Counter = Counter(
            e["properties"].get("doc_type", "ukendt") for e in failed_events
        )
        for doc_type, count in failed_by_type.most_common(3):
            if count >= 2:
                fixes.append({
                    "title": f"Forbedre parsing af '{doc_type}'-dokumenter",
                    "evidence": f"{count} fejl ved {doc_type}-analyse seneste 30 dage",
                    "impact": "high" if count >= 5 else "medium",
                    "effort": "medium",
                })

        # AI errors
        ai_errors = self._count("ai.error", since_30)
        if ai_errors >= 3:
            fixes.append({
                "title": "Reducér AI-fejlrate",
                "evidence": f"{ai_errors} AI-fejl registreret seneste 30 dage",
                "impact": "high",
                "effort": "medium",
            })

        # ── UX Improvements ──
        if verification_pct < 20 and facts_total >= 5:
            ux_improvements.append({
                "title": "Øg faktum-verifikationsrate",
                "evidence": f"Kun {verification_pct}% af {facts_total} fakta er verificeret af bruger",
                "impact": "high",
                "effort": "low",
                "suggestion": "Promovér verificering med onboarding-guider eller in-app påmindelser",
            })

        if recs_pending >= 3 and resolution_pct < 40:
            ux_improvements.append({
                "title": "Gør anbefalinger lettere at håndtere",
                "evidence": f"{recs_pending} åbne anbefalinger — kun {resolution_pct}% er løst",
                "impact": "high",
                "effort": "low",
                "suggestion": "Tilføj 'Løs alle'-knap eller guidet gennemgang af anbefalinger",
            })

        if uploaded > 0 and chats == 0:
            ux_improvements.append({
                "title": "Øg chat-adoption",
                "evidence": f"0 chatsamtaler på trods af {uploaded} uploadede dokumenter",
                "impact": "medium",
                "effort": "low",
                "suggestion": "Tilføj suggested questions eller auto-start chat efter analyse",
            })
        elif uploaded > 5 and chats < uploaded * 0.2:
            ux_improvements.append({
                "title": "Øg chat-adoption",
                "evidence": f"Kun {chats} chatsamtaler for {uploaded} analyser ({round(chats/max(1,uploaded)*100)}% adoptionsrate)",
                "impact": "medium",
                "effort": "low",
                "suggestion": "Tilføj contextuelle chat-suggestioner direkte fra faktumvisning",
            })

        # ── Opportunities ──
        subs = self._table_data("subscriptions", "plan, status")
        active_subs = [s for s in subs if s.get("status") != "cancelled"]
        free_count = sum(1 for s in active_subs if s.get("plan", "free") == "free")
        paid_count = len(active_subs) - free_count

        if free_count >= 3 and paid_count == 0:
            opportunities.append({
                "title": "Konvertér gratis brugere til betalt abonnement",
                "evidence": f"{free_count} gratis brugere, 0 betalende kunder",
                "impact": "high",
                "effort": "medium",
                "suggestion": "Implementér in-app upsell efter første succesfulde dokumentanalyse",
            })
        elif free_count > paid_count * 2:
            opportunities.append({
                "title": "Øg konverteringsrate",
                "evidence": f"{free_count} gratis vs {paid_count} betalende ({round(paid_count/max(1,free_count+paid_count)*100)}% konvertering)",
                "impact": "high",
                "effort": "medium",
            })

        if analyzed >= 10 and chats < analyzed * 0.3:
            opportunities.append({
                "title": "Chat er underudnyttet — forbedre synlighed",
                "evidence": f"{chats} chat-session for {analyzed} analyserede dokumenter",
                "impact": "medium",
                "effort": "low",
            })

        # Rank all by impact × frequency
        _impact_score = {"high": 3, "medium": 2, "low": 1}

        def _score(item: dict) -> int:
            return _impact_score.get(item.get("impact", "low"), 1)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "top_fixes":           sorted(fixes,           key=_score, reverse=True)[:10],
            "top_ux_improvements": sorted(ux_improvements, key=_score, reverse=True)[:10],
            "top_opportunities":   sorted(opportunities,   key=_score, reverse=True)[:10],
        }

    # ── WP7: Executive Report ─────────────────────────────────────────────────

    def get_executive_report(self) -> dict:
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        analytics   = self.get_analytics(days=7)
        health      = self.get_health_score()
        operational = self.get_operational()
        priorities  = self.get_priorities()

        # Highlights (what went well)
        highlights: list[str] = []
        if analytics["documents"]["analyzed"] > 0:
            highlights.append(
                f"{analytics['documents']['analyzed']} dokumenter analyseret med "
                f"{analytics['documents']['analysis_success_rate_pct']}% succesrate"
            )
        if analytics["chat"]["completed"] > 0:
            highlights.append(f"{analytics['chat']['completed']} chatsamtaler gennemført")
        if analytics["revenue"]["subscriptions_paid"] > 0:
            highlights.append(
                f"{analytics['revenue']['subscriptions_paid']} betalende kunder — "
                f"MRR: {analytics['revenue']['mrr_dkk']} DKK"
            )
        if analytics["facts"]["verification_rate_pct"] >= 30:
            highlights.append(
                f"Høj verifikationsrate: {analytics['facts']['verification_rate_pct']}% af fakta bekræftet"
            )

        # Concerns (what needs attention)
        concerns: list[str] = []
        if analytics["documents"]["analysis_success_rate_pct"] < 85:
            concerns.append(
                f"Lav analysesuccesrate: {analytics['documents']['analysis_success_rate_pct']}% "
                f"({analytics['documents']['failed']} fejl)"
            )
        if analytics["facts"]["verification_rate_pct"] < 20 and analytics["facts"]["total"] >= 5:
            concerns.append(
                f"Lav verifikationsrate: {analytics['facts']['verification_rate_pct']}% "
                f"af {analytics['facts']['total']} fakta bekræftet"
            )
        if analytics["recommendations"]["resolution_rate_pct"] < 30 and analytics["recommendations"]["total"] >= 3:
            concerns.append(
                f"Lav løsningsrate: {analytics['recommendations']['resolution_rate_pct']}% "
                f"af {analytics['recommendations']['total']} anbefalinger håndteret"
            )
        if analytics["users"]["active_in_period"] == 0:
            concerns.append("Ingen aktive brugere i perioden")
        if analytics["revenue"]["subscriptions_paid"] == 0 and analytics["users"]["active_in_period"] >= 5:
            concerns.append("Ingen betalende kunder trods aktive brugere")

        # Summary text
        score = health["score"]
        grade = health["grade"]
        active = analytics["users"]["active_in_period"]
        summary = (
            f"Platformen er i {_grade_label(grade)} stand (score {score}/100). "
            f"{active} aktive brugere seneste 7 dage. "
        )
        if highlights:
            summary += highlights[0] + ". "
        if concerns:
            summary += f"Primær bekymring: {concerns[0].lower()}."

        # Action items (top 3 from priorities combined)
        all_actions = (
            priorities["top_fixes"][:2]
            + priorities["top_ux_improvements"][:1]
            + priorities["top_opportunities"][:1]
        )
        action_items = [
            {
                "priority": i + 1,
                "title": a["title"],
                "evidence": a["evidence"],
                "impact": a.get("impact", "medium"),
                "suggestion": a.get("suggestion"),
            }
            for i, a in enumerate(all_actions[:5])
        ]

        return {
            "period": f"{week_ago.date()} til {now.date()}",
            "generated_at": now.isoformat(),
            "summary": summary,
            "product_health": {
                "score": health["score"],
                "grade": health["grade"],
                "trend": health["trend"],
            },
            "highlights": highlights,
            "concerns": concerns,
            "analytics_snapshot": {
                "docs_analyzed": analytics["documents"]["analyzed"],
                "analysis_success_pct": analytics["documents"]["analysis_success_rate_pct"],
                "facts_verified_pct": analytics["facts"]["verification_rate_pct"],
                "active_users": analytics["users"]["active_in_period"],
                "mrr_dkk": analytics["revenue"]["mrr_dkk"],
                "ai_cost_usd": analytics["ai"]["cost_usd_period"],
            },
            "top_operational_issues": (operational["top_errors"] or [])[:3],
            "action_items": action_items,
            "full_priorities": priorities,
        }


# ── Module helpers ────────────────────────────────────────────────────────────

def _event_label(event_type: str) -> str:
    labels = {
        "document.uploaded":         "Dokument uploadet",
        "document.analyzed":         "Dokument analyseret",
        "document.failed":           "Dokumentanalyse fejlet",
        "fact.verified":             "Faktum verificeret",
        "chat.completed":            "Chatsamtale afsluttet",
        "recommendation.resolved":   "Anbefaling løst",
        "recommendation.dismissed":  "Anbefaling afvist",
        "employment.created":        "Ansættelse oprettet",
        "subscription.started":      "Abonnement startet",
        "subscription.cancelled":    "Abonnement opsagt",
        "ai.error":                  "AI-fejl",
    }
    return labels.get(event_type, event_type)


def _grade_label(grade: str) -> str:
    return {"A": "fremragende", "B": "god", "C": "middel", "D": "dårlig"}.get(grade, "ukendt")
