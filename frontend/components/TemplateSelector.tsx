"use client";

import React from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

export type CvTemplate =
  | "nordic_executive"
  | "clean_professional"
  | "modern_nordic"
  | "minimal_nordic"
  | "bold_impact";

export type AppTemplate =
  | "corporate"
  | "executive"
  | "modern"
  | "technical"
  | "graduate";

// ── CV template metadata ──────────────────────────────────────────────────────

export const CV_TEMPLATES: Array<{ id: CvTemplate; label: string; desc: string }> = [
  {
    id: "nordic_executive",
    label: "Nordic Executive",
    desc: "Mørk navy sidebar, guld-accenter, to-kolonne — FM, ESG, ledelse",
  },
  {
    id: "clean_professional",
    label: "Clean Professional",
    desc: "Enkelt en-kolonne, blå accenter — finans, jura, offentlig",
  },
  {
    id: "modern_nordic",
    label: "Modern Nordic",
    desc: "Mørk header, venstre accent-stribe — tech, marketing",
  },
  {
    id: "minimal_nordic",
    label: "Minimal Nordic",
    desc: "Skandinavisk minimalisme, maks. luft — konsulenter, kreative",
  },
  {
    id: "bold_impact",
    label: "Bold Impact",
    desc: "Tyk mørk header, amber accent — salg, startup, ledelse",
  },
];

export const APP_TEMPLATES: Array<{ id: AppTemplate; label: string; desc: string }> = [
  {
    id: "corporate",
    label: "Corporate",
    desc: "Formel blå header, professionel sans-serif",
  },
  {
    id: "executive",
    label: "Executive",
    desc: "Premium brevhoved, Times, guld-regler",
  },
  {
    id: "modern",
    label: "Modern",
    desc: "Teal accent-stribe, clean whitespace",
  },
  {
    id: "technical",
    label: "Technical",
    desc: "Minimalistisk monokrom, struktureret",
  },
  {
    id: "graduate",
    label: "Graduate",
    desc: "Lilla/blå gradient header, imødekommende professionel",
  },
];

// ── Mini preview thumbnails ────────────────────────────────────────────────────

function CvPreviewNordicExecutive() {
  return (
    <div className="h-full w-full flex overflow-hidden">
      {/* Dark left sidebar */}
      <div className="w-6 bg-[#1a1a2e] flex-shrink-0 p-1 pt-2">
        <div className="mb-0.5 h-0.5 w-4 bg-[#c8a96e] rounded-sm" />
        <div className="space-y-0.5 mt-1">
          {[3, 3.5, 2.5, 3].map((w, i) => (
            <div key={i} style={{ width: `${w * 4}px` }} className="h-0.5 bg-[#9999bb] rounded-sm opacity-70" />
          ))}
        </div>
        <div className="mt-1.5 mb-0.5 h-0.5 w-4 bg-[#c8a96e] rounded-sm" />
        <div className="space-y-0.5">
          {[3, 3.5, 2.5].map((w, i) => (
            <div key={i} style={{ width: `${w * 4}px` }} className="h-0.5 bg-[#9999bb] rounded-sm opacity-70" />
          ))}
        </div>
      </div>
      {/* White right column */}
      <div className="flex-1 bg-white">
        {/* Header bar */}
        <div className="bg-[#1a1a2e] px-1.5 py-1 flex items-end gap-2">
          <div className="h-1.5 w-10 bg-white rounded-sm opacity-90" />
          <div className="h-0.5 w-8 bg-[#c8a96e] rounded-sm" />
        </div>
        <div className="p-1.5 space-y-0.5">
          <div className="h-0.5 w-8 bg-[#1a1a2e] rounded-sm opacity-40" />
          {[14, 12, 16, 10, 14].map((w, i) => (
            <div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{ width: `${w * 3}px` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function CvPreviewCleanProfessional() {
  return (
    <div className="h-full w-full bg-white px-2 py-1.5">
      <div className="mb-0.5 h-2 w-20 bg-slate-900 rounded-sm" />
      <div className="mb-1 h-0.5 w-14 bg-[#2c5282] rounded-sm" />
      <div className="border-t-2 border-[#2c5282] mb-1" />
      <div className="mb-0.5 h-0.5 w-10 bg-[#2c5282] opacity-60 rounded-sm" />
      <div className="border-t border-slate-200 mb-0.5" />
      <div className="space-y-0.5">
        {[18, 16, 14, 18, 16].map((w, i) => (
          <div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{ width: `${w * 3}px` }} />
        ))}
      </div>
    </div>
  );
}

function CvPreviewModernNordic() {
  return (
    <div className="h-full w-full bg-white overflow-hidden flex">
      {/* Left accent strip */}
      <div className="w-1 bg-[#2b4c7e] flex-shrink-0" />
      <div className="flex-1">
        {/* Dark header band */}
        <div className="bg-slate-800 px-1.5 py-1.5">
          <div className="h-1.5 w-14 bg-white rounded-sm opacity-90" />
          <div className="mt-0.5 h-0.5 w-10 bg-slate-400 rounded-sm opacity-60" />
        </div>
        <div className="p-1.5 space-y-0.5">
          <div className="flex items-center gap-1 mb-0.5">
            <div className="h-1.5 w-1.5 bg-[#2b4c7e] rounded-sm flex-shrink-0" />
            <div className="h-0.5 w-8 bg-slate-400 rounded-sm" />
          </div>
          {[14, 12, 16, 10, 14].map((w, i) => (
            <div key={i} className="h-0.5 bg-slate-200 rounded-sm ml-2.5" style={{ width: `${w * 3}px` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function CvPreviewMinimalNordic() {
  return (
    <div className="h-full w-full bg-white px-3 py-2.5">
      <div className="mb-0.5 h-2 w-20 bg-slate-700 rounded-sm opacity-80" />
      <div className="mb-2 h-0.5 w-14 bg-slate-400 rounded-sm opacity-50" />
      <div className="space-y-1.5">
        {[0, 1].map((gi) => (
          <div key={gi}>
            <div className="mb-0.5 h-0.5 w-6 bg-slate-300 rounded-sm" />
            <div className="space-y-0.5">
              {[14, 16, 12].map((w, i) => (
                <div key={i} className="h-0.5 bg-slate-100 rounded-sm" style={{ width: `${w * 3}px` }} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CvPreviewBoldImpact() {
  return (
    <div className="h-full w-full bg-white overflow-hidden">
      {/* Thick dark header */}
      <div className="bg-slate-900 px-1.5 py-2">
        <div className="h-2 w-16 bg-white rounded-sm opacity-90" />
        <div className="mt-0.5 h-0.5 w-10 bg-amber-400 rounded-sm" />
      </div>
      <div className="p-1.5">
        <div className="mb-0.5 flex items-center gap-1">
          <div className="h-1 w-1 bg-amber-400 rounded-sm flex-shrink-0" />
          <div className="h-0.5 w-8 bg-slate-600 rounded-sm" />
        </div>
        <div className="rounded bg-amber-50 px-1 py-0.5 mb-0.5">
          <div className="h-0.5 w-10 bg-slate-300 rounded-sm" />
        </div>
        <div className="space-y-0.5">
          {[14, 12, 16, 10].map((w, i) => (
            <div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{ width: `${w * 3}px` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

const CV_PREVIEWS: Record<string, PreviewComponent> = {
  nordic_executive:    CvPreviewNordicExecutive,
  clean_professional:  CvPreviewCleanProfessional,
  modern_nordic:       CvPreviewModernNordic,
  minimal_nordic:      CvPreviewMinimalNordic,
  bold_impact:         CvPreviewBoldImpact,
};

function AppPreviewCorporate() {
  return (
    <div className="h-full w-full overflow-hidden">
      <div className="bg-blue-700 px-1.5 py-1">
        <div className="h-1.5 w-12 bg-white opacity-90 rounded-sm" />
        <div className="mt-0.5 h-0.5 w-9 bg-blue-200 rounded-sm" />
      </div>
      <div className="p-1.5 bg-white space-y-0.5">
        {[12, 10, 18, 16, 14, 16, 14].map((w, i) => (
          <div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{ width: `${w * 3}px` }} />
        ))}
      </div>
    </div>
  );
}

function AppPreviewExecutive() {
  return (
    <div className="h-full w-full bg-white px-2 py-1.5">
      <div className="text-center mb-0.5">
        <div className="mx-auto h-1.5 w-16 bg-slate-800 rounded-sm" />
      </div>
      <div className="border-t-2 border-yellow-600 mb-0.5" />
      <div className="border-t border-yellow-400 mb-1" />
      <div className="text-right mb-0.5">
        <div className="ml-auto h-0.5 w-8 bg-slate-300 rounded-sm" />
      </div>
      <div className="mb-0.5 h-0.5 w-14 bg-slate-500 rounded-sm" />
      <div className="space-y-0.5">
        {[16, 18, 14, 16, 18].map((w, i) => (
          <div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{ width: `${w * 3}px` }} />
        ))}
      </div>
    </div>
  );
}

function AppPreviewModern() {
  return (
    <div className="h-full w-full bg-white overflow-hidden">
      <div className="bg-teal-500 h-1" />
      <div className="p-1.5">
        <div className="mb-0.5 h-1.5 w-14 bg-slate-800 rounded-sm" />
        <div className="mb-0.5 h-0.5 w-10 bg-teal-500 rounded-sm" />
        <div className="mb-1 h-0.5 w-9 bg-slate-300 rounded-sm" />
        <div className="border-t border-teal-300 mb-0.5" />
        <div className="space-y-0.5">
          {[16, 18, 14, 16, 18, 14].map((w, i) => (
            <div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{ width: `${w * 3}px` }} />
          ))}
        </div>
      </div>
      <div className="absolute bottom-0 left-0 right-0 bg-teal-500 h-1" />
    </div>
  );
}

function AppPreviewTechnical() {
  return (
    <div className="h-full w-full bg-white px-2 py-1.5">
      <div className="mb-0.5 h-1.5 w-14 bg-slate-900 rounded-sm" />
      <div className="border-t-2 border-slate-900 mb-0.5" />
      <div className="text-right mb-0.5">
        <div className="ml-auto h-0.5 w-8 bg-slate-300 rounded-sm" />
      </div>
      <div className="mb-0.5 h-0.5 w-12 bg-slate-700 rounded-sm" />
      <div className="border-t border-slate-200 mb-0.5" />
      <div className="space-y-0.5">
        {[16, 18, 14, 16, 14].map((w, i) => (
          <div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{ width: `${w * 3}px` }} />
        ))}
      </div>
    </div>
  );
}

function AppPreviewGraduate() {
  return (
    <div className="h-full w-full overflow-hidden">
      <div className="flex h-6">
        <div className="flex-1 bg-indigo-600" />
        <div className="flex-1 bg-blue-400" />
      </div>
      <div className="p-1.5 bg-white space-y-0.5">
        <div className="h-0.5 w-10 bg-slate-300 rounded-sm" />
        {[16, 18, 14, 16, 18, 14].map((w, i) => (
          <div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{ width: `${w * 3}px` }} />
        ))}
      </div>
    </div>
  );
}

const APP_PREVIEWS: Record<string, PreviewComponent> = {
  corporate: AppPreviewCorporate,
  executive: AppPreviewExecutive,
  modern:    AppPreviewModern,
  technical: AppPreviewTechnical,
  graduate:  AppPreviewGraduate,
};

// ── Generic TemplateSelector ──────────────────────────────────────────────────

type PreviewComponent = () => React.ReactElement;

interface TemplateSelectorProps<T extends string> {
  templates: Array<{ id: T; label: string; desc: string }>;
  previews: Record<string, PreviewComponent>;
  selected: T;
  onSelect: (id: T) => void;
  columns?: 3 | 5;
}

function TemplateGrid<T extends string>({
  templates, previews, selected, onSelect, columns = 5,
}: TemplateSelectorProps<T>) {
  return (
    <div className={`grid gap-3 ${columns === 5 ? "grid-cols-5" : "grid-cols-3"}`}>
      {templates.map(tpl => {
        const Preview: PreviewComponent = previews[tpl.id] ?? (() => <div />);
        const active = selected === tpl.id;
        return (
          <button
            key={tpl.id}
            onClick={() => onSelect(tpl.id)}
            className={`group flex flex-col rounded-xl border-2 overflow-hidden text-left transition-all ${
              active
                ? "border-blue-600 shadow-md ring-1 ring-blue-200"
                : "border-slate-200 hover:border-slate-400 hover:shadow-sm"
            }`}
          >
            {/* Mini preview thumbnail */}
            <div className={`relative h-24 w-full overflow-hidden bg-white ${
              active ? "" : "opacity-90 group-hover:opacity-100"
            }`}>
              <Preview />
              {active && (
                <div className="absolute inset-0 bg-blue-600/5" />
              )}
            </div>

            {/* Label */}
            <div className={`px-2 py-1.5 ${active ? "bg-blue-600" : "bg-slate-50"}`}>
              <p className={`text-xs font-semibold truncate ${active ? "text-white" : "text-slate-800"}`}>
                {tpl.label}
              </p>
              <p className={`mt-0.5 text-[10px] leading-tight line-clamp-2 ${
                active ? "text-blue-100" : "text-slate-400"
              }`}>
                {tpl.desc}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ── Structured CV templates (Master CV — legacy export system) ────────────────

export type StructuredCvTemplate =
  | "ats_professional"
  | "modern_professional"
  | "executive"
  | "minimal_nordic"
  | "creative_professional";

export const STRUCTURED_CV_TEMPLATES: Array<{ id: StructuredCvTemplate; label: string; desc: string }> = [
  { id: "ats_professional",    label: "ATS Professional",    desc: "Sort/hvid, ATS-optimeret, maksimal parser-kompatibilitet" },
  { id: "modern_professional", label: "Modern Professional", desc: "Navy sidebar, blå accenter, moderne to-kolonne layout" },
  { id: "executive",           label: "Executive",           desc: "Premium lederprofil, guld-accenter, brede marginer" },
  { id: "minimal_nordic",      label: "Minimal Nordic",      desc: "Skandinavisk design, meget luft, grå toner" },
  { id: "creative_professional",label: "Creative",           desc: "Teal header, moderne visuelt udtryk, pill-tags" },
];

function StructuredPreviewAts() {
  return (
    <div className="h-full w-full bg-white p-1.5">
      <div className="mb-0.5 h-2 w-20 bg-slate-900 rounded-sm" />
      <div className="mb-1 h-1 w-14 bg-slate-400 rounded-sm" />
      <div className="mb-0.5 border-t border-slate-900" />
      <div className="space-y-0.5">{[14,18,12,16].map((w,i)=><div key={i} className="h-0.5 bg-slate-300 rounded-sm" style={{width:`${w*4}px`}} />)}</div>
      <div className="mt-1 mb-0.5 border-t border-slate-900" />
      <div className="space-y-0.5">{[18,16,14].map((w,i)=><div key={i} className="h-0.5 bg-slate-300 rounded-sm" style={{width:`${w*4}px`}} />)}</div>
    </div>
  );
}
function StructuredPreviewModern() {
  return (
    <div className="h-full w-full flex">
      <div className="w-5 bg-blue-900 flex-shrink-0 p-1">
        <div className="mb-1 h-1.5 w-3 bg-white rounded-sm opacity-90" />
        <div className="mb-2 h-0.5 w-3 bg-blue-400 rounded-sm" />
        <div className="space-y-0.5">{[3,2.5,3,2.5].map((w,i)=><div key={i} style={{width:`${w*4}px`}} className="h-0.5 bg-blue-300 opacity-60 rounded-sm" />)}</div>
      </div>
      <div className="flex-1 p-1.5 bg-white">
        <div className="mb-0.5 h-1 w-full bg-blue-600 opacity-20 rounded-sm" />
        <div className="space-y-0.5 mt-1">{[14,12,16,10,14,12].map((w,i)=><div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{width:`${w*4}px`}} />)}</div>
      </div>
    </div>
  );
}
function StructuredPreviewExecutive() {
  return (
    <div className="h-full w-full bg-white px-2 py-1.5">
      <div className="text-center mb-0.5"><div className="mx-auto h-2 w-16 bg-slate-900 rounded-sm" /></div>
      <div className="mb-0.5 border-t-2 border-yellow-600 mt-0.5" />
      <div className="mb-0.5 border-t border-yellow-400" />
      <div className="mt-1 mb-0.5 h-0.5 w-10 bg-yellow-600 rounded-sm" />
      <div className="border-t border-yellow-300 mb-0.5" />
      <div className="space-y-0.5">{[18,16,14,18,16].map((w,i)=><div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{width:`${w*3}px`}} />)}</div>
    </div>
  );
}
function StructuredPreviewNordic() {
  return (
    <div className="h-full w-full bg-white px-2 py-2">
      <div className="mb-0.5 h-2.5 w-20 bg-slate-700 rounded-sm opacity-80" />
      <div className="mb-1 h-1 w-14 bg-slate-400 rounded-sm opacity-70" />
      <div className="mb-1.5 border-t border-slate-200" />
      <div className="space-y-1">{[0,1].map((_,gi)=><div key={gi}><div className="mb-0.5 h-0.5 w-6 bg-slate-400 rounded-sm opacity-60" /><div className="space-y-0.5 ml-5">{[14,12,16].map((w,i)=><div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{width:`${w*3}px`}} />)}</div></div>)}</div>
    </div>
  );
}
function StructuredPreviewCreative() {
  return (
    <div className="h-full w-full bg-white overflow-hidden">
      <div className="bg-teal-600 px-1.5 py-1"><div className="h-1.5 w-14 bg-white opacity-90 rounded-sm" /><div className="mt-0.5 h-0.5 w-10 bg-teal-200 rounded-sm" /></div>
      <div className="bg-teal-800 h-0.5" />
      <div className="p-1.5">
        <div className="mb-0.5 h-0.5 w-8 bg-teal-600 rounded-sm" />
        <div className="border-t border-teal-400 mb-0.5" />
        <div className="space-y-0.5">{[16,14,12].map((w,i)=><div key={i} className="h-0.5 bg-slate-200 rounded-sm" style={{width:`${w*3}px`}} />)}</div>
        <div className="mt-1 flex gap-0.5 flex-wrap">{[3,4,3,5].map((w,i)=><div key={i} className="h-1.5 bg-teal-100 rounded-full" style={{width:`${w*4}px`}} />)}</div>
      </div>
    </div>
  );
}

const STRUCTURED_CV_PREVIEWS: Record<string, PreviewComponent> = {
  ats_professional:     StructuredPreviewAts,
  modern_professional:  StructuredPreviewModern,
  executive:            StructuredPreviewExecutive,
  minimal_nordic:       StructuredPreviewNordic,
  creative_professional: StructuredPreviewCreative,
};

interface StructuredCvTemplateSelectorProps {
  selected: StructuredCvTemplate;
  onSelect: (id: StructuredCvTemplate) => void;
  columns?: 3 | 5;
}

export function StructuredCvTemplateSelector({ selected, onSelect, columns }: StructuredCvTemplateSelectorProps) {
  return (
    <TemplateGrid
      templates={STRUCTURED_CV_TEMPLATES}
      previews={STRUCTURED_CV_PREVIEWS}
      selected={selected}
      onSelect={onSelect}
      columns={columns}
    />
  );
}

// ── Public exports ────────────────────────────────────────────────────────────

interface CvTemplateSelectorProps {
  selected: CvTemplate;
  onSelect: (id: CvTemplate) => void;
  columns?: 3 | 5;
}

export function CvTemplateSelector({ selected, onSelect, columns }: CvTemplateSelectorProps) {
  return (
    <TemplateGrid
      templates={CV_TEMPLATES}
      previews={CV_PREVIEWS}
      selected={selected}
      onSelect={onSelect}
      columns={columns}
    />
  );
}

interface AppTemplateSelectorProps {
  selected: AppTemplate;
  onSelect: (id: AppTemplate) => void;
  columns?: 3 | 5;
}

export function AppTemplateSelector({ selected, onSelect, columns }: AppTemplateSelectorProps) {
  return (
    <TemplateGrid
      templates={APP_TEMPLATES}
      previews={APP_PREVIEWS}
      selected={selected}
      onSelect={onSelect}
      columns={columns}
    />
  );
}
