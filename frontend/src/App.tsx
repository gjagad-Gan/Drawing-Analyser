import { useState, useCallback } from "react";
import { Loader2, AlertCircle, KeyRound } from "lucide-react";

import ApiKeyModal from "./components/ApiKeyModal";
import UploadZone from "./components/UploadZone";
import ResultPanel from "./components/ResultPanel";
import { previewDrawing, downloadExcel, triggerDownload } from "./api";
import type { CRSData, AnalysisStage } from "./types";

// ─── Stage labels ─────────────────────────────────────────────────────────────
const STAGE_LABELS: Record<AnalysisStage, string> = {
  idle: "",
  uploading: "Uploading drawing PDF…",
  analysing: "Claude is reading the drawing — extracting all technical data…",
  done: "",
  error: "",
};

const STAGE_PROGRESS: Record<AnalysisStage, number> = {
  idle: 0,
  uploading: 25,
  analysing: 75,
  done: 100,
  error: 0,
};

// ─── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [apiKey, setApiKey] = useState<string | null>(() =>
    sessionStorage.getItem("isc_api_key")
  );
  const [stage, setStage] = useState<AnalysisStage>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [result, setResult] = useState<{ data: CRSData; filename: string } | null>(null);
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [downloading, setDownloading] = useState(false);

  function handleApiKey(key: string) {
    sessionStorage.setItem("isc_api_key", key);
    setApiKey(key);
  }

  function handleReset() {
    setStage("idle");
    setResult(null);
    setCurrentFile(null);
    setErrorMsg("");
  }

  const handleFile = useCallback(
    async (file: File) => {
      if (!apiKey) return;
      setCurrentFile(file);
      setErrorMsg("");
      setResult(null);

      try {
        setStage("uploading");
        await new Promise((r) => setTimeout(r, 250));

        setStage("analysing");
        const preview = await previewDrawing(file, apiKey);

        setResult({ data: preview.data, filename: preview.filename });
        setStage("done");
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "Unknown error.");
        setStage("error");
      }
    },
    [apiKey]
  );

  async function handleDownload() {
    if (!currentFile || !apiKey) return;
    setDownloading(true);
    try {
      const { blob, filename } = await downloadExcel(currentFile, apiKey);
      triggerDownload(blob, filename);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloading(false);
    }
  }

  const busy = stage === "uploading" || stage === "analysing";

  return (
    <>
      {!apiKey && <ApiKeyModal onSave={handleApiKey} />}

      <div className="min-h-screen bg-gradient-to-br from-slate-100 to-blue-50">

        {/* ── Header ── */}
        <header className="bg-isc-navy shadow">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white text-isc-navy text-sm font-extrabold shadow">
                ISC
              </div>
              <div>
                <p className="text-sm font-bold text-white leading-none">Drawing Analyser</p>
                <p className="text-xs text-blue-300">Indo Shell Cast Pvt. Ltd. — Marketing Dept.</p>
              </div>
            </div>
            <button
              onClick={() => { sessionStorage.removeItem("isc_api_key"); setApiKey(null); handleReset(); }}
              className="flex items-center gap-1.5 text-xs text-blue-300 hover:text-white transition"
            >
              <KeyRound className="h-3.5 w-3.5" />
              Change Key
            </button>
          </div>
        </header>

        {/* ── Main ── */}
        <main className="mx-auto max-w-5xl px-6 py-10">

          {stage !== "done" && (
            <div className="mb-8 text-center">
              <h2 className="text-2xl font-bold text-isc-navy">
                Engineering Drawing → Contract Review Sheet
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Upload any raw-casting drawing PDF and get a filled ISC CRS in seconds.
              </p>
            </div>
          )}

          {/* Upload zone */}
          {stage !== "done" && (
            <UploadZone onFile={handleFile} disabled={busy} />
          )}

          {/* Progress */}
          {busy && (
            <div className="mt-8 flex flex-col items-center gap-3 text-isc-blue">
              <Loader2 className="h-8 w-8 animate-spin" />
              <p className="text-sm font-medium text-center max-w-sm">
                {STAGE_LABELS[stage]}
              </p>
              <div className="h-1.5 w-64 overflow-hidden rounded-full bg-isc-light">
                <div
                  className="h-full bg-isc-blue transition-all duration-1000 ease-out"
                  style={{ width: `${STAGE_PROGRESS[stage]}%` }}
                />
              </div>
              <p className="text-xs text-slate-400">
                This takes 20–40 seconds for a complex drawing.
              </p>
            </div>
          )}

          {/* Error */}
          {stage === "error" && (
            <div className="mt-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500" />
              <div>
                <p className="text-sm font-semibold text-red-700">Analysis Failed</p>
                <p className="mt-0.5 text-xs text-red-600">{errorMsg}</p>
                <button
                  onClick={handleReset}
                  className="mt-2 text-xs font-medium text-red-700 underline hover:no-underline"
                >
                  Try again
                </button>
              </div>
            </div>
          )}

          {/* Results */}
          {stage === "done" && result && (
            <ResultPanel
              data={result.data}
              filename={result.filename}
              onDownload={handleDownload}
              onReset={handleReset}
              downloading={downloading}
            />
          )}
        </main>

        <footer className="py-6 text-center text-xs text-slate-400">
          © {new Date().getFullYear()} Indo Shell Cast Pvt. Ltd. — Powered by Claude AI
        </footer>
      </div>
    </>
  );
}
