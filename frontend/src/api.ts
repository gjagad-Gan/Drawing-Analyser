import type { CRSData, PreviewResponse } from "./types";

// In production: set VITE_API_URL to your Render/Railway backend URL.
// In dev:  Vite proxies /api → http://localhost:8000  (see vite.config.ts).
const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

function headers(apiKey: string): HeadersInit {
  return { "X-API-Key": apiKey };
}

/** Upload PDF and receive extracted data as JSON (no Excel yet). */
export async function previewDrawing(
  file: File,
  apiKey: string
): Promise<PreviewResponse> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${BASE_URL}/analyze/preview`, {
    method: "POST",
    headers: headers(apiKey),
    body: form,
  });

  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`Server error ${res.status}: ${msg}`);
  }

  return res.json() as Promise<PreviewResponse>;
}

/** Upload PDF and download the filled Excel Contract Review Sheet. */
export async function downloadExcel(
  file: File,
  apiKey: string
): Promise<{ blob: Blob; filename: string }> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${BASE_URL}/analyze`, {
    method: "POST",
    headers: headers(apiKey),
    body: form,
  });

  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`Server error ${res.status}: ${msg}`);
  }

  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? "contract_review.xlsx";

  return { blob: await res.blob(), filename };
}

/** Generate Excel from already-extracted data (avoids re-calling Claude). */
export function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export type { CRSData };
