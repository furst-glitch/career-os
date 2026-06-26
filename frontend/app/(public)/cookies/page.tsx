import Link from "next/link";

export const metadata = {
  title: "Cookiepolitik — CareerOS",
  description: "Sådan anvender CareerOS cookies og lignende teknologier.",
};

export default function CookiesPage() {
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
          <h1 className="text-2xl font-bold text-slate-900">Cookiepolitik</h1>
          <p className="mt-2 text-sm text-slate-500">Sidst opdateret: 26. juni 2026</p>

          <div className="mt-8 space-y-8 text-sm text-slate-600 leading-relaxed">

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">Hvad er cookies?</h2>
              <p>
                Cookies er små tekstfiler, som et websted gemmer på din enhed. De bruges til at huske dine præferencer,
                holde dig logget ind og forbedre din oplevelse.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">Hvilke cookies bruger vi?</h2>

              <div className="space-y-4">
                <div className="rounded-lg border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2.5 flex items-center justify-between">
                    <p className="font-semibold text-slate-800">Nødvendige cookies</p>
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">Altid aktive</span>
                  </div>
                  <div className="px-4 py-3">
                    <p className="text-slate-600 text-xs mb-3">
                      Disse cookies er nødvendige for at platformen fungerer. De kan ikke deaktiveres.
                    </p>
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-slate-400 text-left">
                          <th className="font-medium pb-1.5 w-1/3">Cookie</th>
                          <th className="font-medium pb-1.5 w-1/3">Formål</th>
                          <th className="font-medium pb-1.5">Udløb</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-600 divide-y divide-slate-100">
                        <tr>
                          <td className="py-1.5 pr-2 font-mono">sb-access-token</td>
                          <td className="py-1.5 pr-2">Login-session (Supabase Auth)</td>
                          <td className="py-1.5">1 time</td>
                        </tr>
                        <tr>
                          <td className="py-1.5 pr-2 font-mono">sb-refresh-token</td>
                          <td className="py-1.5 pr-2">Automatisk fornyelse af session</td>
                          <td className="py-1.5">7 dage</td>
                        </tr>
                        <tr>
                          <td className="py-1.5 pr-2 font-mono">__stripe_sid</td>
                          <td className="py-1.5 pr-2">Sikker betalingssession (Stripe)</td>
                          <td className="py-1.5">Session</td>
                        </tr>
                        <tr>
                          <td className="py-1.5 pr-2 font-mono">__stripe_mid</td>
                          <td className="py-1.5 pr-2">Stripe-enhedsidentifikation</td>
                          <td className="py-1.5">1 år</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2.5 flex items-center justify-between">
                    <p className="font-semibold text-slate-800">Funktionelle cookies</p>
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">Nødvendige for tjenesten</span>
                  </div>
                  <div className="px-4 py-3">
                    <p className="text-slate-600 text-xs mb-3">
                      Husker dine præferencer som valgt sprog, skabelon og visningsindstillinger.
                    </p>
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-slate-400 text-left">
                          <th className="font-medium pb-1.5 w-1/3">Lagring</th>
                          <th className="font-medium pb-1.5 w-1/3">Formål</th>
                          <th className="font-medium pb-1.5">Type</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-600 divide-y divide-slate-100">
                        <tr>
                          <td className="py-1.5 pr-2 font-mono">localStorage</td>
                          <td className="py-1.5 pr-2">UI-præferencer, aktiv fane</td>
                          <td className="py-1.5">Local Storage</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2.5 flex items-center justify-between">
                    <p className="font-semibold text-slate-800">Analytiske cookies</p>
                    <span className="text-xs bg-slate-200 text-slate-600 px-2 py-0.5 rounded-full font-medium">Ingen tredjepartsanalyse</span>
                  </div>
                  <div className="px-4 py-3">
                    <p className="text-slate-600 text-xs">
                      CareerOS anvender <strong>ikke</strong> tredjeparts analysecookies (Google Analytics, Mixpanel, Hotjar, o.lign.).
                      Brugsdata indsamles via vores egne serverlogs i anonymiseret form og gemmes i vores egen database.
                      Ingen brugsdata deles med reklamenetværk eller datamæglere.
                    </p>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2.5 flex items-center justify-between">
                    <p className="font-semibold text-slate-800">Marketingcookies</p>
                    <span className="text-xs bg-slate-200 text-slate-600 px-2 py-0.5 rounded-full font-medium">Ingen</span>
                  </div>
                  <div className="px-4 py-3">
                    <p className="text-slate-600 text-xs">
                      CareerOS anvender ingen marketingcookies og ingen retargeting. Vi sælger ikke data til annoncører.
                    </p>
                  </div>
                </div>
              </div>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">Administrér cookies</h2>
              <p>
                Du kan til enhver tid slette cookies via din browsers indstillinger. Bemærk at sletning af nødvendige cookies
                vil logge dig ud og kan påvirke platformens funktionalitet.
              </p>
              <p className="mt-2">Vejledning til de mest anvendte browsere:</p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li><a href="https://support.google.com/chrome/answer/95647" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Chrome</a></li>
                <li><a href="https://support.mozilla.org/da/kb/slet-cookies-fjern-oplysninger-lagret-hjemmesider" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Firefox</a></li>
                <li><a href="https://support.apple.com/da-dk/guide/safari/sfri11471/mac" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Safari</a></li>
                <li><a href="https://support.microsoft.com/da-dk/windows/slette-og-administrere-cookies-168dab11-0753-043d-7c16-ede5947fc64d" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Microsoft Edge</a></li>
              </ul>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">Kontakt</h2>
              <p>
                Spørgsmål om vores cookieanvendelse kan rettes til:{" "}
                <a href="mailto:kontakt@careeros.dk" className="text-blue-600 hover:underline">
                  kontakt@careeros.dk
                </a>
              </p>
            </section>

          </div>
        </div>

        <div className="mt-6 flex justify-center gap-6 text-xs text-slate-400">
          <Link href="/privacy" className="hover:text-slate-600">Privatlivspolitik</Link>
          <Link href="/terms" className="hover:text-slate-600">Brugsbetingelser</Link>
          <Link href="/login" className="hover:text-slate-600">Log ind</Link>
        </div>
      </div>
    </div>
  );
}
