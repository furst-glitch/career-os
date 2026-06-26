# CareerOS — Release 1.0 Checklist

**Formål:** Komplet tjekliste for kommerciel lancering. Intet valgfrit. Intet "nice to have".

---

## KRITISK — Blokerer lancering

### Sikkerhed
- [ ] **Rotér alle API-nøgler** — generer nye Anthropic, OpenAI, Supabase service role nøgler
- [ ] **Verificér .env er i .gitignore** — kør `git check-ignore -v backend/.env`
- [ ] **Sæt alle production secrets i Render** — aldrig i koden eller git
- [ ] **Sæt ADMIN_EMAIL** i Render env vars
- [ ] **Stripe webhook secret** sat i Render og verificeret i Stripe Dashboard
- [ ] **Supabase RLS aktiveret** på alle tabeller (bekræftet ved migration 00014)
- [ ] **Test uautoriseret adgang** — bekræft at 401/403 returneres korrekt

### Betalingsflow
- [ ] **Stripe test mode → live mode** — skift til live API-nøgler
- [ ] **Stripe produkter oprettet** med korrekte priser (Pro, Professional, Enterprise)
- [ ] **Stripe webhook endpoint** registreret på production URL
- [ ] **Test komplet betalingsflow** — checkout → webhook → subscription aktiveret
- [ ] **Test abonnements-nedgradering** og opsigelse
- [ ] **Test refund-flow** (manuel i Stripe Dashboard)

### Database
- [ ] **Alle migrations kørt** på production Supabase
- [ ] **Verificér migrations er idempotente** — kør dem 2 gange, ingen fejl
- [ ] **Test brugeroprettelse** — trigger opretter user_profiles + subscriptions row
- [ ] **Backup bekræftet** — Supabase backup-plan aktiveret (Pro tier anbefalet)

### Infrastructure
- [ ] **Render plan opgraders** fra Free til Starter (undgå cold starts)
- [ ] **Custom domain** sat op på Render (api.careeros.dk eller lignende)
- [ ] **CORS_ORIGINS** opdateret til production Vercel URL
- [ ] **Vercel custom domain** sat op (careeros.dk)
- [ ] **SSL/TLS** verificeret på alle domæner

---

## HIGH — Bør løses inden lancering

### Monitoring
- [ ] **Sentry konfigureret** — SENTRY_DSN sat i Render
- [ ] **Health check monitoring** — opsæt UptimeRobot eller Render health checks på `/health`
- [ ] **CTO Dashboard tilgængeligt** — verificér `/cto` virker med admin email
- [ ] **Platform Intelligence** samler events (test `document.uploaded` event)

### Brugeroplevelse
- [ ] **Onboarding-flow testet** — ny bruger kan oprette konto og uploade første dokument
- [ ] **Fejltekster verificerede** — alle SSE-fejlbeskeder er på dansk og forståelige
- [ ] **Tomme tilstande verificerede** — dashboard med 0 data ser fornuftigt ud
- [ ] **Mobilvisning testet** — alle sider fungerer på mobil (Chrome DevTools)

### Email
- [ ] **Supabase Auth email-templates opdateret** (bekræftelse, reset password)
- [ ] **Custom email domain** sat op i Supabase (undgå spam-filter)
- [ ] **Test email-verifikationsflow** — ny bruger modtager og kan bekræfte email

### Dokumentation
- [ ] **Privatlivspolitik** tilgængelig på frontend (se WP5 backlog)
- [ ] **Brugsbetingelser** tilgængelig på frontend
- [ ] **Cookie-politik** tilgængelig (GDPR)
- [ ] **Kontaktoplysninger** tilgængelige på siden

---

## MEDIUM — Kan laves inden for 30 dage efter lancering

### Teknisk gæld
- [ ] **GDPR-endpoints** implementeret (`/api/v1/gdpr/export` og `/gdpr/delete`)
- [ ] **log_usage() for streaming agenter** — employment_chat_agent, labor_rights_agent, salary_prep_agent
- [ ] **Månedlig AI-kvote per bruger** — implementér soft limit (budget check eksisterer, sæt limits)
- [ ] **Retry-logik** for mislykkede background tasks (embedding-generering)

### Forretning
- [ ] **Analytics-baseline** etableret — uge 1-data i platform_events
- [ ] **Conversion tracking** — hvornår konverterer brugere fra free til paid?
- [ ] **Support-kanal** defineret (email, Intercom, Slack?)
- [ ] **Pricing page** på marketing-site med klare features per plan

---

## LOW — Nice to have, ikke blokkerende

- [ ] **Status page** oprettet (statuspage.io eller lignende)
- [ ] **Changelog** på marketing-site
- [ ] **FAQ** opdateret med hyppige spørgsmål fra testbrugere
- [ ] **App Store / PWA manifest** (ikke krævet for web)
- [ ] **Performance budget** defineret (<2s LCP)

---

## Lancerings-dag procedure

### T-24 timer
- [ ] Kør alle migrations på production
- [ ] Deployer backend og verificér `/health`
- [ ] Deployer frontend og verificér at login virker
- [ ] Test komplet betalingsflow med test-kort
- [ ] Kontrollér Stripe live mode er aktivt

### T-0 (lancering)
- [ ] Skift Stripe fra test til live
- [ ] Verificér webhook modtages korrekt
- [ ] Monitorér `/api/v1/intelligence/operational` de første 2 timer
- [ ] Hold Render og Supabase logs åbne
- [ ] Test oprettelse af ny konto (som slutbruger)

### T+24 timer
- [ ] Gennemgå CTO Dashboard — Platform Health Score
- [ ] Tjek for uventede fejl i logs
- [ ] Verificér AI-forbrug er inden for forventede rammer
- [ ] Evt. kommunikation til beta-brugere

---

## Definition of Done

Release 1.0 er klar når:
1. Alle KRITISK-punkter er afkrydset
2. Alle HIGH-punkter er afkrydset eller accepteret med dokumenteret risiko
3. En manuel end-to-end test er gennemført (oprettelse → upload → analyse → betaling)
4. CTO har underskrevet lancerings-godkendelse
