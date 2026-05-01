import { CheckCircle2, Download, RotateCcw, FileSpreadsheet, ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import type { CRSData, Page1Item, Page2CostItem, Page2RiskItem } from "../types";

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="sticky top-0 z-10 bg-isc-blue px-4 py-2">
      <p className="text-xs font-bold uppercase tracking-widest text-white">{title}</p>
    </div>
  );
}

function P1Row({ item }: { item: Page1Item }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="border-b border-slate-100">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-3 px-4 py-2.5 text-left hover:bg-slate-50 transition"
      >
        <span className="mt-0.5 flex-shrink-0 text-xs font-bold text-isc-blue w-6">{item.no}</span>
        <span className="flex-1 text-xs font-semibold text-slate-700 leading-snug">
          {item.description.replace(/\\n/g, " / ")}
        </span>
        {open
          ? <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 text-slate-400 mt-0.5" />
          : <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-slate-400 mt-0.5" />}
      </button>
      {open && (
        <div className="grid grid-cols-2 gap-px bg-slate-200 mx-4 mb-3 rounded overflow-hidden text-xs">
          <div className="bg-white p-2.5">
            <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-400">
              Specified in Drawing
            </p>
            <p className="whitespace-pre-wrap text-slate-700 leading-relaxed">{item.spec}</p>
          </div>
          <div className="bg-isc-light/60 p-2.5">
            <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-isc-blue">
              Feasibility Review
            </p>
            <p className="whitespace-pre-wrap text-slate-600 leading-relaxed">{item.review}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function P2CostRow({ item, alt }: { item: Page2CostItem; alt: boolean }) {
  return (
    <div className={`grid grid-cols-[80px_1fr] gap-x-3 border-b border-slate-100 px-4 py-2 text-xs ${alt ? "bg-slate-50" : "bg-white"}`}>
      <span className="font-semibold text-isc-blue">{item.no}</span>
      <div className="flex justify-between gap-4">
        <span className="font-medium text-slate-600 min-w-[140px]">{item.description}</span>
        <span className="text-right text-slate-700 flex-1">{item.value}</span>
      </div>
    </div>
  );
}

function RiskRow({ item }: { item: Page2RiskItem }) {
  return (
    <div className="border-b border-yellow-100 px-4 py-2.5 bg-yellow-50/40">
      <div className="flex gap-3 text-xs">
        <span className="flex-shrink-0 font-bold text-amber-600 w-6">{item.no}</span>
        <div>
          <p className="font-semibold text-slate-700 mb-1 leading-snug">
            {item.description.replace(/\\n/g, " ")}
          </p>
          <p className="whitespace-pre-wrap text-slate-600 leading-relaxed">{item.value}</p>
        </div>
      </div>
    </div>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────────────

interface Props {
  data: CRSData;
  filename: string;
  onDownload: () => void;
  onReset: () => void;
  downloading: boolean;
}

export default function ResultPanel({ data, filename, onDownload, onReset, downloading }: Props) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">

      {/* ── Toolbar ── */}
      <div className="flex items-center justify-between bg-isc-navy px-5 py-3.5">
        <div className="flex items-center gap-2.5 text-white min-w-0">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-green-300" />
          <div className="min-w-0">
            <p className="text-sm font-bold leading-tight">Analysis Complete</p>
            <p className="text-xs text-blue-200 truncate">{filename}</p>
          </div>
        </div>
        <div className="flex gap-2 flex-shrink-0 ml-4">
          <button
            onClick={onReset}
            className="flex items-center gap-1.5 rounded-lg border border-white/30 px-3 py-1.5 text-xs font-medium text-white/80 hover:bg-white/10 transition"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            New
          </button>
          <button
            onClick={onDownload}
            disabled={downloading}
            className="flex items-center gap-1.5 rounded-lg bg-isc-orange px-4 py-1.5 text-xs font-semibold text-white hover:bg-orange-700 transition disabled:opacity-60"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            {downloading ? "Generating…" : "Download CRS (.xlsx)"}
          </button>
        </div>
      </div>

      {/* ── Meta band ── */}
      <div className="grid grid-cols-2 gap-px bg-slate-200 text-xs">
        <div className="bg-isc-light/50 px-4 py-2">
          <span className="font-semibold text-slate-500">Customer: </span>
          <span className="text-isc-navy font-bold">{data.customer_name || "—"}</span>
        </div>
        <div className="bg-isc-light/50 px-4 py-2">
          <span className="font-semibold text-slate-500">Drawing: </span>
          <span className="text-slate-700">{data.enquiry_ref || "—"}</span>
        </div>
      </div>

      {/* ── Scrollable content ── */}
      <div className="overflow-y-auto max-h-[62vh]">

        {/* Page 1 — Technical review */}
        <SectionHeader title="Page 1 — Technical Review (Items 1–11)" />
        {data.page1?.map((item) => (
          <P1Row key={item.no} item={item} />
        ))}

        {/* Page 2 — Cost estimation */}
        <SectionHeader title="Page 2 — Cost Estimation Inputs (Items 12–25)" />
        {data.page2_cost?.map((item, i) => (
          <P2CostRow key={item.no} item={item} alt={i % 2 !== 0} />
        ))}

        {/* Page 2 — Risk analysis */}
        <SectionHeader title="Page 2 — Risk Analysis (Items 26–31)" />
        {data.page2_risk?.map((item) => (
          <RiskRow key={item.no} item={item} />
        ))}

        {/* Concluding remarks */}
        {data.concluding_remarks && (
          <div className="bg-green-50 border-t border-green-200 px-4 py-3">
            <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-green-700">
              Concluding Remarks
            </p>
            <p className="whitespace-pre-wrap text-xs text-green-900 leading-relaxed">
              {data.concluding_remarks}
            </p>
          </div>
        )}
      </div>

      {/* ── Download CTA at bottom ── */}
      <div className="border-t border-slate-200 bg-slate-50 px-5 py-3 flex items-center justify-between">
        <p className="text-xs text-slate-500">
          Review the extracted data above, then download the filled Contract Review Sheet.
        </p>
        <button
          onClick={onDownload}
          disabled={downloading}
          className="flex items-center gap-2 rounded-lg bg-isc-navy px-5 py-2 text-xs font-semibold text-white hover:bg-isc-blue transition disabled:opacity-60"
        >
          <Download className="h-3.5 w-3.5" />
          {downloading ? "Generating Excel…" : "Download CRS Excel"}
        </button>
      </div>
    </div>
  );
}
