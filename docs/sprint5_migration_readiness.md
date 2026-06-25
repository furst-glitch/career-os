# Sprint 5 — Migration Readiness Report
**Dato:** 2026-06-26  
**Udgangspunkt:** CVAgent migreret som referenceimplementering i Sprint 4.  
**Scope:** De resterende 21 agenter.  
**Stop:** Ingen agent migreres i dette sprint. Rapporten fastlægger rækkefølge og kompleksitet.

---

## Resumé

| Kategori | Antal | Handling |
|---|---|---|
| **Easy** — 1 LLM-kald, ikke-streaming | 14 | Migrér i Sprint 6 (batch) |
| **Medium** — Flere kald / multi-mode | 3 | Migrér i Sprint 6 (individuelt) |
| **Defer** — Streaming-afhængig | 2 | Migrér i Sprint 7+ (Gateway streaming) |
| **Skip** — Ikke implementeret | 2 | Intet at migrere |

---

## Easy-agenter (14)

Én `LiteLLMProvider.complete()` → én `self._call_gateway()`. Ingen streaming. Migreres med copy/paste af CVAgent-pattern.

| Agent-fil | Klasse | Capability | Noter |
|---|---|---|---|
| `agreement_analysis_agent.py` | AgreementAnalysisAgent | `agreement_analysis` | Standard |
| `application_agent.py` | ApplicationAgent | `cv_generation` | Internt opdelt i `_run_cv()` / `_run_cover_letter()`, men ét LLM-kald via `_llm_call()` |
| `ats_agent.py` | ATSAgent | `document_review` | Standard |
| `career_coach_agent.py` | CareerCoachAgent | `career_coaching` | Håndterer 4 analysis-types med én prompt |
| `career_value_agent.py` | CareerValueAgent | `salary_negotiation` | Standard |
| `contract_analysis_agent.py` | ContractAnalysisAgent | `contract_analysis` | Standard |
| `critic_agent.py` | CriticAgent | `document_review` | Modtager upstream-output fra 3 agenter som input |
| `designer_agent.py` | DesignerAgent | `document_review` | 8+ CV-templates + 5+ cover letter templates; ét LLM-kald |
| `hiring_manager_agent.py` | HiringManagerAgent | `document_review` | Standard |
| `hr_agent.py` | HRAgent | `document_review` | Standard |
| `job_agent.py` | JobAgent | `job_matching` | Standard |
| `job_discovery_agent.py` | JobDiscoveryAgent | `job_matching` | Håndterer `NoProviderKeyError` — fjernes ved migration (Gateway giver `GatewayAuthError`) |
| `payslip_check_agent.py` | PayslipCheckAgent | `payslip_extraction` | Standard |
| `salary_check_agent.py` | SalaryCheckAgent | `salary_negotiation` | Standard |
| `worktime_check_agent.py` | WorktimeCheckAgent | `contract_analysis` | Standard |

**Migrations-pattern:**
```python
# Fra:
provider = LiteLLMProvider(user_id=self.user_id)
response = await provider.complete(self.name, messages, temperature=0.7)
await self.log_usage(AgentUsage(...))

# Til:
response = await self._call_gateway("capability_name", messages, temperature=0.7)
usage = self._usage_from_response(response)
```

---

## Medium-agenter (3)

Kræver individuel vurdering pga. flere LLM-kald eller multi-mode operation.

### InterviewPrepAgent (`interview_prep_agent.py`)
- **Capability:** `interview_prep`
- **LLM-kald:** 3 parallelle (company_research, role_description, interview_guide)
- **Nuværende pattern:** Tre `LiteLLMProvider.complete()` kørt med `asyncio.gather()`; usage summeres manuelt
- **Migrations-plan:** Tre `self._call_gateway()` med `interview_prep` capability. `asyncio.gather()` bevares. Usage summeres via tre `_usage_from_response()`.

### ReviewBoardAgent (`review_board_agent.py`)
- **Capability:** `document_review` (brief-mode) / `cv_generation` (rewrite-mode)
- **LLM-kald:** 2 (ét per mode)
- **Nuværende pattern:** `_run_rewrite()` + `_run_brief()` med separate `log_usage()` med operation-suffixes (`_rewrite`, `_brief`)
- **Migrations-plan:** `self.capabilities = {"run_rewrite": "cv_generation", "run_brief": "document_review"}`. Brug `_call_gateway(self.capabilities["run_rewrite"], ...)` i hver metode.

### SalaryPrepAgent (`salary_prep_agent.py`)
- **Capability:** `salary_negotiation`
- **LLM-kald:** 2 ikke-streaming (`run()`, `generate_a4()`) + 1 streaming (`run_interview()`)
- **Migrations-plan (delvis):** Migrér `run()` og `generate_a4()` til `_call_gateway()` i Sprint 6. `run_interview()` DEFER til Sprint 7+ (streaming).

---

## Defer-agenter (2)

Disse agenter bruger `LiteLLMProvider`'s streaming, som Gateway ikke understøtter endnu (TD-007). Forbliver på `LiteLLMProvider` indtil Sprint 7+ tilføjer streaming-understøttelse.

| Agent-fil | Klasse | Streaming-metode | Bemærkning |
|---|---|---|---|
| `labor_rights_agent.py` | LaborRightsAgent | `run()` — fuld SSE-stream | Ingen log_usage pga. streaming |
| `salary_prep_agent.py` | SalaryPrepAgent | `run_interview()` — SSE-stream | Øvrige metoder migreres i Sprint 6 |

---

## Skip-agenter (2)

Stubs der returnerer fejl-metadata. Ingen LiteLLMProvider-kald. Intet at migrere.

| Agent-fil | Klasse | Status |
|---|---|---|
| `interview_agent.py` | InterviewAgent | Deaktiveret i migration 00044. Stub. |
| `salary_agent.py` | SalaryAgent | Deaktiveret i migration 00044. Stub. |

---

## Capability-mapping (komplet)

Alle agent-capabilities mapper til eksisterende rækker i `plan_capabilities` (migration 00047). **Ingen ny migration påkrævet.**

| Capability | Agenter |
|---|---|
| `chat` | LaborRightsAgent *(defer)* |
| `cv_parsing` | CVAgent *(allerede migreret)* |
| `cv_generation` | ApplicationAgent, ReviewBoardAgent (rewrite) |
| `contract_analysis` | ContractAnalysisAgent, WorktimeCheckAgent |
| `agreement_analysis` | AgreementAnalysisAgent |
| `payslip_extraction` | PayslipCheckAgent |
| `job_matching` | JobAgent, JobDiscoveryAgent |
| `interview_prep` | InterviewPrepAgent, InterviewAgent *(skip)* |
| `salary_negotiation` | CareerValueAgent, SalaryCheckAgent, SalaryPrepAgent, SalaryAgent *(skip)* |
| `career_coaching` | CareerCoachAgent |
| `document_review` | ATSAgent, CriticAgent, DesignerAgent, HiringManagerAgent, HRAgent, ReviewBoardAgent (brief) |
| `multi_agent_review` | Ingen enkelt agent — pipeline-niveau |

---

## Anbefalet migrations-rækkefølge (Sprint 6)

1. **Batch 1** (trivielle, samme mønster): AgreementAnalysis, ATS, CareerCoach, CareerValue, Contract, Critic, HiringManager, HR, Job, JobDiscovery, Payslip, SalaryCheck, Worktime *(13 agenter)*
2. **Batch 2** (lidt anderledes): Application *(1 agent — _llm_call()-indirection)*
3. **Individuelle** (medium): InterviewPrep, ReviewBoard, SalaryPrep (non-streaming del)
4. **Designer**: Ét kald, men mange templates — verifér output-format bevares

**Ikke i Sprint 6:** LaborRights, SalaryPrepAgent.run_interview() (streaming), InterviewAgent, SalaryAgent (stubs).

---

## Sprint 5 — Leverancer (denne sprint)

| Opgave | Status |
|---|---|
| T1: BaseAgent — `_get_gateway`, `_usage_from_response`, `_call_gateway` | ✅ Færdig |
| T2: AgentCapabilities — `capability` + `capabilities` class attrs | ✅ Færdig |
| T2b: CVAgent cleanup — bruger nu BaseAgent-metoderne | ✅ Færdig |
| T3: TD-008 — UsageTracker løser `agent_id` fra agent_registry (med cache) | ✅ Færdig |
| T4: Fail-closed — AIPolicyService afviser ukendte capabilities med `unknown_capability` | ✅ Færdig |
| T5: Migration Readiness Report | ✅ Dette dokument |
| Tests: 263 bestået, 99% coverage | ✅ Bekræftet |
