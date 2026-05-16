import { useRef, useState } from "react";
import { cn } from "../lib/cn";

const ALLOWED = [".pdf", ".docx", ".txt"];
const MAX_MB = 5;

export default function FileDropzone({ onFile, disabled }) {
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState(null);
  const [file, setFile] = useState(null);

  const choose = (f) => {
    setError(null);
    if (!f) return;
    const name = f.name.toLowerCase();
    if (!ALLOWED.some((ext) => name.endsWith(ext))) {
      setError(`Unsupported file type. Allowed: ${ALLOWED.join(", ")}`);
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File is too large (>${MAX_MB} MB).`);
      return;
    }
    setFile(f);
    onFile?.(f);
  };

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (disabled) return;
          choose(e.dataTransfer.files?.[0]);
        }}
        onClick={() => !disabled && inputRef.current?.click()}
        className={cn(
          "rounded-xl border-2 border-dashed px-6 py-10 text-center cursor-pointer transition-colors",
          drag ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white hover:bg-slate-50",
          disabled && "opacity-60 cursor-not-allowed"
        )}
      >
        <p className="text-slate-700">
          {file ? (
            <>
              <span className="font-medium">{file.name}</span>{" "}
              <span className="text-slate-500">({(file.size / 1024).toFixed(0)} KB)</span>
            </>
          ) : (
            <>
              <span className="font-medium">Drop your CV here</span>{" "}
              or <span className="text-brand-600 underline">browse</span>
            </>
          )}
        </p>
        <p className="text-xs text-slate-500 mt-1">
          PDF, DOCX or TXT — up to {MAX_MB} MB
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED.join(",")}
          className="hidden"
          onChange={(e) => choose(e.target.files?.[0])}
        />
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
