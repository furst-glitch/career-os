import Link from "next/link";

export const metadata = {
  title: "Brugsbetingelser — CareerOS",
  description: "Vilkår og betingelser for brug af CareerOS.",
};

export default function TermsPage() {
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
          <h1 className="text-2xl font-bold text-slate-900">Brugsbetingelser</h1>
          <p className="mt-2 text-sm text-slate-500">Sidst opdateret: 26. juni 2026</p>

          <div className="mt-8 space-y-8 text-sm text-slate-600 leading-relaxed">

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">1. Accept af betingelser</h2>
              <p>
                Ved at oprette en konto og anvende CareerOS accepterer du disse brugsbetingelser. Hvis du ikke accepterer betingelserne, bedes du undlade at anvende tjenesten.
              </p>
              <p className="mt-2">
                Disse betingelser gælder for alle brugere af CareerOS, uanset om de benytter den gratis eller betalte version.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">2. Tjenesten</h2>
              <p>
                CareerOS er en AI-drevet karriereplatform, der hjælper brugere med at:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 mt-2">
                <li>Analysere og forbedre CV og ansøgninger</li>
                <li>Strukturere karrierehistorik og kompetencer</li>
                <li>Analysere ansættelseskontrakter, lønsedler og pensionsdokumenter</li>
                <li>Modtage AI-genererede karrierevejledninger og anbefalinger</li>
                <li>Matche jobopslag med kandidatprofil</li>
              </ul>
              <p className="mt-2">
                CareerOS forbeholder sig retten til at ændre, suspendere eller afvikle dele af tjenesten med rimeligt varsel.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">3. Brugerforpligtelser</h2>
              <p className="mb-2">Du forpligter dig til at:</p>
              <ul className="list-disc pl-5 space-y-1.5">
                <li>Angive korrekte oplysninger ved oprettelse og brug af platformen</li>
                <li>Holde dine loginoplysninger fortrolige og ikke dele dem med andre</li>
                <li>Kun uploade dokumenter og data, som du har ret til at dele</li>
                <li>Ikke anvende tjenesten til ulovlige formål</li>
                <li>Ikke forsøge at omgå tekniske sikkerhedsforanstaltninger</li>
                <li>Ikke anvende platformen til at skaffe information om andre personers karriere eller dokumenter uden deres samtykke</li>
              </ul>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">4. AI-genereret indhold</h2>
              <p>
                CareerOS anvender AI-sprogmodeller til at generere vejledning, analyser og dokumentudkast.
              </p>
              <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 mt-3">
                <p className="text-amber-800 font-medium text-xs">Vigtigt om AI-indhold</p>
                <p className="text-amber-700 text-xs mt-1">
                  AI-genereret indhold er vejledende og erstatter ikke professionel juridisk, finansiel eller karrieremæssig rådgivning.
                  Du er selv ansvarlig for at verificere oplysninger i genererede dokumenter, herunder CV, ansøgninger og analyser,
                  inden du anvender dem. CareerOS garanterer ikke nøjagtigheden af AI-genereret indhold.
                </p>
              </div>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">5. Abonnement og betaling</h2>
              <p>CareerOS tilbyder følgende planer:</p>
              <ul className="list-disc pl-5 space-y-1.5 mt-2">
                <li><strong>Gratis:</strong> begrænset adgang til AI-funktioner og analyser</li>
                <li><strong>Pro:</strong> fuld adgang til alle AI-funktioner, ubegrænset analysering</li>
                <li><strong>Professional:</strong> udvidet AI-budget og prioriteret support</li>
              </ul>
              <p className="mt-3">
                Betalte abonnementer faktureres månedligt eller årligt via Stripe. Priser fremgår af Indstillinger → Fakturering.
              </p>
              <p className="mt-2">
                Abonnementer fornyes automatisk. Du kan til enhver tid opsige eller nedgradere via Indstillinger → Fakturering → Administrer abonnement.
              </p>
              <p className="mt-2">
                <strong>Fortrydelsesret:</strong> Du har 14 dages fortrydelsesret fra tegning af abonnement, forudsat at du ikke allerede har benyttet betalte funktioner.
                Kontakt os på kontakt@careeros.dk for refusion.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">6. Intellektuel ejendom</h2>
              <p>
                CareerOS og alt tilhørende software, design og indhold ejes af CareerOS og er beskyttet af ophavsret.
              </p>
              <p className="mt-2">
                <strong>Dine data:</strong> Du ejer fuldt ud alle data, dokumenter og information du uploader til platformen.
                Du giver CareerOS en begrænset, ikke-eksklusiv licens til at behandle disse data med henblik på at levere tjenesten.
              </p>
              <p className="mt-2">
                <strong>Genereret indhold:</strong> CV-udkast, analyser og andre AI-genererede dokumenter baseret på dine data tilhører dig.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">7. Ansvarsbegrænsning</h2>
              <p>
                CareerOS stilles til rådighed "som beset" (as-is). I det omfang loven tillader det, fraskriver CareerOS sig ansvar for:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 mt-2">
                <li>Indirekte tab, herunder tabt arbejdsfortjeneste eller ansættelsesmuligheder</li>
                <li>Tab som følge af tekniske fejl eller driftsafbrydelser</li>
                <li>Beslutninger truffet på baggrund af AI-genereret indhold</li>
                <li>Tab af data som følge af faktorer uden for vores kontrol</li>
              </ul>
              <p className="mt-2">
                CareerOS' samlede ansvar over for en enkelt bruger er begrænset til det beløb, brugeren har betalt for tjenesten inden for de seneste 12 måneder.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">8. Opsigelse</h2>
              <p>
                Du kan til enhver tid slette din konto via Indstillinger → Slet konto. Dine data slettes inden for 30 dage, bortset fra data vi er lovmæssigt forpligtet til at opbevare.
              </p>
              <p className="mt-2">
                CareerOS kan opsige din adgang ved grov overtrædelse af disse betingelser, med øjeblikkelig virkning og uden forudgående varsel.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">9. Lovvalg og tvister</h2>
              <p>
                Disse betingelser er underlagt dansk ret. Eventuelle tvister søges løst i mindelighed.
                Kan en tvist ikke løses i mindelighed, afgøres den ved de danske domstole.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">10. Ændringer</h2>
              <p>
                Vi forbeholder os retten til at opdatere disse betingelser. Væsentlige ændringer varsles via e-mail eller notifikation i platformen med mindst 14 dages varsel.
                Fortsat brug af tjenesten efter ikrafttrædelsesdatoen udgør accept af de ændrede betingelser.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-3">11. Kontakt</h2>
              <p>
                Spørgsmål til disse betingelser kan rettes til:{" "}
                <a href="mailto:kontakt@careeros.dk" className="text-blue-600 hover:underline">
                  kontakt@careeros.dk
                </a>
              </p>
            </section>

          </div>
        </div>

        <div className="mt-6 flex justify-center gap-6 text-xs text-slate-400">
          <Link href="/privacy" className="hover:text-slate-600">Privatlivspolitik</Link>
          <Link href="/cookies" className="hover:text-slate-600">Cookiepolitik</Link>
          <Link href="/login" className="hover:text-slate-600">Log ind</Link>
        </div>
      </div>
    </div>
  );
}
