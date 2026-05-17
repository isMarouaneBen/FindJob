import { useRef, useState } from "react";
import { CloudUpload, FileText, X } from "lucide-react";
import { cn } from "../lib/cn";

const ALLOWED = [".pdf", ".docx", ".txt"];
const MAX_MB = 5;

export default function FileDropzone({ onFile, disabled, file: controlledFile }) {
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState(null);
  const [internalFile, setInternalFile] = useState(null);
  const file = controlledFile ?? internalFile;

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
    setInternalFile(f);
    onFile?.(f);
  };

  const clear = () => { setInternalFile(null); onFile?.(null); };

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); !disabled && setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault(); setDrag(false);
          if (disabled) return;
          choose(e.dataTransfer.files?.[0]);
        }}
        onClick={() => !disabled && !file && inputRef.current?.click()}
        className={cn(
          "relative rounded-2xl border-2 border-dashed transition-all overflow-hidden",
          drag && "border-brand-500 bg-brand-500/[0.08]",
          !drag && "border-line-strong bg-white/[0.02] hover:border-brand-500/40 hover:bg-white/[0.04]",
          disabled && "opacity-50 cursor-not-allowed",
          !file && "cursor-pointer",
          "px-6 py-14 text-center"
        )}
      >
        {/* subtle moving beam on hover */}
        {!file && !disabled && (
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-400/60 to-transparent
                          opacity-0 hover:opacity-100 transition-opacity" />
        )}

        {file ? (
          <div className="flex items-center justify-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/15 border border-brand-500/30
                            text-brand-300 grid place-items-center">
              <FileText size={18} />
            </div>
            <div className="text-left">
              <p className="font-medium text-text">{file.name}</p>
              <p className="text-xs text-text-dim">{(file.size / 1024).toFixed(0)} KB</p>
            </div>
            {!disabled && (
              <button type="button" onClick={(e) => { e.stopPropagation(); clear(); }}
                      className="ml-2 p-1.5 rounded-lg hover:bg-white/[0.05] text-text-dim hover:text-text">
                <X size={16} />
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="w-12 h-12 mx-auto rounded-2xl bg-brand-500/10 border border-brand-500/20
                            text-brand-300 grid place-items-center mb-3">
              <CloudUpload size={22} />
            </div>
            <p className="text-text">
              <span className="font-medium">Drop your CV here</span>{" "}
              or <span className="text-brand-300 underline underline-offset-4 decoration-brand-400/40">browse</span>
            </p>
            <p className="text-xs text-text-dim mt-1.5">
              PDF, DOCX or TXT — up to {MAX_MB} MB
            </p>
          </>
        )}
        <input ref={inputRef} type="file" accept={ALLOWED.join(",")}
               className="hidden" onChange={(e) => choose(e.target.files?.[0])} />
      </div>
      {error && <p className="field-error">{error}</p>}
    </div>
  );
}
