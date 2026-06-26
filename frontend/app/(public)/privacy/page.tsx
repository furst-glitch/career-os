import Link from "next/link";

export const metadata = {
  title: "Privatlivspolitik — CareerOS",
  description: "Sådan behandler CareerOS dine personoplysninger.",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-slate-50 py-12 px-4">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8">
          <Link href="/login" className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
            <span className="font-semibold">CareerOS</span>
          </Link>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white px-8 py-10 shadow-sm">
          <h1 className="text-2xl font-bold text-slate-900">Privatlivspolitik</h1>
          <p className="mt-2 text-sm text-slate-500">Sidst opdateret: 26. juni 2026</p>

          <div className="mt-8 space-y-8 text-sm text-slate-600 leading-relaxed">

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">1. Dataansvarlig</h2>
              <p>
                CareerOS er dataansvarlig for behandling af dine personoplysninger. Du kan kontakte os på:
              </p>
              <p className="mt-2 text-slate-700 font-medium">E-mail: kontakt@careeros.dk</p>
              <p className="text-slate-500 text-xs mt-1">
                Vi svarer inden for 30 dage på alle henvendelser om personoplysninger.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">2. Hvilke oplysninger indsamler vi?</h2>
              <p className="mb-2">Vi indsamler følgende kategorier af personoplysninger:</p>
              <ul className="list-disc pl-5 space-y-1.5">
                <li><strong>Kontooplysninger:</strong> navn, e-mailadresse, adgangskode (krypteret)</li>
                <li><strong>Karrieredata:</strong> CV-indhold, joberfaring, uddannelse, kompetencer og præstationer, som du uploader eller indtaster</li>
                <li><strong>Dokumenter:</strong> ansættelseskontrakter, lønsedler, pensionsoversigter og andre dokumenter, du uploader til analyse</li>
                <li><strong>Brugsdata:</strong> hvilke funktioner du anvender, fejllogge og performance-data (uden personhenførbar indhold)</li>
                <li><strong>Betalingsoplysninger:</strong> kortoplysninger behandles udelukkende af Stripe — vi lagrer ikke kortdata</li>
                <li><strong>AI-interaktioner:</strong> spørgsmål og svar i Career Coach og andre AI-funktioner</li>
              </ul>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">3. Formål og retsgrundlag</h2>
              <div className="space-y-3">
                <div className="rounded-lg bg-slate-50 px-4 py-3">
                  <p className="font-medium text-slate-800">Levering af tjenesten</p>
                  <p className="text-xs text-slate-500 mt-0.5">Retsgrundlag: Opfyldelse af kontrakt (GDPR art. 6, stk. 1, litra b)</p>
                </div>
                <div className="rounded-lg bg-slate-50 px-4 py-3">
                  <p className="font-medium text-slate-800">AI-analyse og personaliserede anbefalinger</p>
                  <p className="text-xs text-slate-500 mt-0.5">Retsgrundlag: Berettiget interesse / samtykke (GDPR art. 6, stk. 1, litra f / a)</p>
                </div>
                <div className="rounded-lg bg-slate-50 px-4 py-3">
                  <p className="font-medium text-slate-800">Fakturering og abonnementsstyring</p>
                  <p className="text-xs text-slate-500 mt-0.5">Retsgrundlag: Opfyldelse af kontrakt og retlig forpligtelse (GDPR art. 6, stk. 1, litra b og c)</p>
                </div>
                <div className="rounded-lg bg-slate-50 px-4 py-3">
                  <p className="font-medium text-slate-800">Forbedring af platformen (anonymiseret)</p>
                  <p className="text-xs text-slate-500 mt-0.5">Retsgrundlag: Berettiget interesse (GDPR art. 6, stk. 1, litra f)</p>
                </div>
              </div>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">4. AI-behandling af dine data</h2>
              <p>
                CareerOS anvender AI-sprogmodeller (Anthropic Claude og/eller OpenAI GPT) til at analysere dine karrieredata og dokumenter.
                Dine data sendes til disse udbydere under vores databehandleraftaler, hvor de er underlagt strenge fortrolighedskrav.
              </p>
              <p className="mt-2">
                <strong>Vigtigt:</strong> Dine data bruges aldrig til at træne eksterne AI-modeller.
                Anthropic og OpenAI benytter API-data udelukkende til at levere svaret — ikke til modeltræning.
              </p>
              <p className="mt-2">
                Du kan til enhver tid anvende din egen API-nøgle (BYOK) under Indstillinger → AI-udbydere.
                I så fald behandles dine data udelukkende via din egen konto hos AI-udbyderen.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">5. Opbevaringsperiode</h2>
              <ul className="list-disc pl-5 space-y-1.5">
                <li>Kontodata opbevares, så længe du har en aktiv konto</li>
                <li>Ved sletning af konto anonymiseres og slettes data inden for 30 dage</li>
                <li>Regnskabsmæssige data (fakturaer) opbevares i 5 år i henhold til bogføringsloven</li>
                <li>AI-interaktionslogge opbevares i anonymiseret form i op til 90 dage til fejlretning</li>
              </ul>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">6. Dataoverførsler</h2>
              <p>Vi anvender følgende databehandlere, som kan behandle dine data:</p>
              <ul className="list-disc pl-5 space-y-1.5 mt-2">
                <li><strong>Supabase:</strong> databaseinfrastruktur (EU/Frankfurt, ISO 27001)</li>
                <li><strong>Vercel:</strong> frontend-hosting (USA, EU-USA Data Privacy Framework)</li>
                <li><strong>Render:</strong> backend-hosting (USA, SCCs)</li>
                <li><strong>Stripe:</strong> betalingsbehandling (USA, EU-USA Data Privacy Framework)</li>
                <li><strong>Anthropic / OpenAI:</strong> AI-sprogmodeller (USA, SCCs og databehandleraftaler)</li>
              </ul>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">7. Dine rettigheder</h2>
              <p className="mb-2">Du har følgende rettigheder efter GDPR:</p>
              <ul className="list-disc pl-5 space-y-1.5">
                <li><strong>Indsigt:</strong> du kan til enhver tid se alle data vi har om dig via Indstillinger → Eksportér data</li>
                <li><strong>Berigtigelse:</strong> du kan rette ukorrekte oplysninger direkte i platformen</li>
                <li><strong>Sletning:</strong> du kan slette din konto og alle tilhørende data via Indstillinger → Slet konto</li>
                <li><strong>Dataportabilitet:</strong> eksport af dine data som JSON via API</li>
                <li><strong>Indsigelse:</strong> du kan gøre indsigelse mod behandling baseret på berettiget interesse</li>
                <li><strong>Tilbagetrækning af samtykke:</strong> samtykke kan til enhver tid tilbagekaldes</li>
              </ul>
              <p className="mt-3">
                For at udøve dine rettigheder: kontakt os på <strong>kontakt@careeros.dk</strong> eller brug funktionerne direkte i platformen.
              </p>
              <p className="mt-2 text-slate-500">
                Du har ret til at klage til Datatilsynet (datatilsynet.dk) hvis du er utilfreds med vores behandling.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">8. Sikkerhed</h2>
              <p>
                Vi beskytter dine data med branchestandard sikkerhedsforanstaltninger:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 mt-2">
                <li>Alle data transmitteres krypteret via TLS 1.2+</li>
                <li>Data krypteres i hvile hos Supabase (AES-256)</li>
                <li>API-nøgler krypteres med AES-256 og gemmes aldrig i klartekst</li>
                <li>Row Level Security (RLS) sikrer at du kun kan tilgå egne data</li>
                <li>Adgang til produktionssystemer er begrænset og auditeret</li>
              </ul>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">9. Kontakt</h2>
              <p>
                Spørgsmål til denne privatlivspolitik kan rettes til:{" "}
                <a href="mailto:kontakt@careeros.dk" className="text-blue-600 hover:underline">
                  kontakt@careeros.dk
                </a>
              </p>
            </section>

          </div>
        </div>

        <div className="mt-6 flex justify-center gap-6 text-xs text-slate-400">
          <Link href="/terms" className="hover:text-slate-600">Brugsbetingelser</Link>
          <Link href="/cookies" className="hover:text-slate-600">Cookiepolitik</Link>
          <Link href="/login" className="hover:text-slate-600">Log ind</Link>
        </div>
      </div>
    </div>
  );
}
