import { useRef, useState, DragEvent, ChangeEvent } from "react";
import { UploadCloud, FileText } from "lucide-react";

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

export default function UploadZone({ onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const file = e.dataTransfer.files[0];
    if (file?.type === "application/pdf") onFile(file);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onFile(file);
    // Reset so the same file can be re-uploaded
    e.target.value = "";
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload engineering drawing PDF"
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => e.key === "Enter" && !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); !disabled && setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={[
        "flex cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-12 transition-all select-none",
        dragging
          ? "border-isc-blue bg-isc-light scale-[1.01]"
          : "border-slate-300 bg-white hover:border-isc-blue hover:bg-isc-light/40",
        disabled ? "pointer-events-none opacity-50" : "",
      ].join(" ")}
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-isc-light text-isc-navy">
        {dragging ? (
          <FileText className="h-8 w-8" />
        ) : (
          <UploadCloud className="h-8 w-8" />
        )}
      </div>

      <div className="text-center">
        <p className="text-base font-semibold text-slate-700">
          {dragging ? "Drop the PDF here" : "Drag & drop your drawing PDF"}
        </p>
        <p className="mt-1 text-sm text-slate-500">
          or{" "}
          <span className="font-medium text-isc-blue underline underline-offset-2">
            browse files
          </span>{" "}
          — PDF only, max 20 MB
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />
    </div>
  );
}
