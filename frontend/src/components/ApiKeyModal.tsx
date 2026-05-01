import { useState } from "react";
import { KeyRound, Eye, EyeOff } from "lucide-react";

interface Props {
  onSave: (key: string) => void;
}

export default function ApiKeyModal({ onSave }: Props) {
  const [key, setKey] = useState("");
  const [show, setShow] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl">
        {/* Logo / Brand */}
        <div className="mb-6 flex flex-col items-center gap-2">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-isc-navy text-white text-xl font-bold shadow">
            ISC
          </div>
          <h1 className="text-xl font-bold text-isc-navy">ISC Drawing Analyser</h1>
          <p className="text-sm text-slate-500 text-center">
            Indo Shell Cast Pvt. Ltd.
          </p>
        </div>

        <div className="mb-5">
          <label className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold text-slate-700">
            <KeyRound className="h-4 w-4" />
            App Access Key
          </label>
          <div className="relative">
            <input
              type={show ? "text" : "password"}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && key && onSave(key)}
              placeholder="Enter your access key…"
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 pr-10 text-sm focus:border-isc-blue focus:outline-none focus:ring-2 focus:ring-isc-blue/20"
              autoFocus
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          <p className="mt-1.5 text-xs text-slate-400">
            Contact your ISC system administrator for the access key.
          </p>
        </div>

        <button
          onClick={() => key && onSave(key)}
          disabled={!key}
          className="w-full rounded-lg bg-isc-navy py-2.5 text-sm font-semibold text-white transition hover:bg-isc-blue disabled:cursor-not-allowed disabled:opacity-40"
        >
          Continue
        </button>
      </div>
    </div>
  );
}
