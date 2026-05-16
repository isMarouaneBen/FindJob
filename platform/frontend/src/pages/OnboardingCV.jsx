import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import FileDropzone from "../components/FileDropzone";
import { uploadCV } from "../api/cv";

const CV_KEY = "findjob.cvId";

export default function OnboardingCV() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(0);

  const mutation = useMutation({
    mutationFn: () => uploadCV(file, setProgress),
    onSuccess: (data) => {
      localStorage.setItem(CV_KEY, data.cv_id);
      navigate("/onboarding/profile");
    },
  });

  return (
    <div className="max-w-2xl mx-auto">
      <ol className="flex items-center text-xs text-slate-500 mb-6">
        <li className="font-semibold text-brand-700">1 · Upload CV</li>
        <span className="mx-3 text-slate-300">›</span>
        <li>2 · Profile</li>
        <span className="mx-3 text-slate-300">›</span>
        <li>3 · Recommendations</li>
      </ol>

      <h1 className="text-2xl font-semibold text-slate-900">Upload your CV</h1>
      <p className="text-sm text-slate-600 mt-1">
        We'll extract your skills and use them to rank job offers.
        Your file is stored in MinIO and parsed asynchronously.
      </p>

      <div className="mt-6">
        <FileDropzone onFile={setFile} disabled={mutation.isPending} />
      </div>

      {mutation.isPending && (
        <div className="mt-4">
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-brand-500 transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-xs text-slate-500 mt-1">Uploading… {progress}%</p>
        </div>
      )}
      {mutation.isError && (
        <p className="mt-3 text-sm text-red-600">
          Upload failed: {mutation.error.response?.data?.detail ?? mutation.error.message}
        </p>
      )}

      <div className="mt-6 flex items-center justify-between">
        <Link to="/onboarding/profile" className="btn-ghost">Skip for now</Link>
        <button
          onClick={() => mutation.mutate()}
          disabled={!file || mutation.isPending}
          className="btn-primary"
        >
          {mutation.isPending ? "Uploading…" : "Continue"}
        </button>
      </div>
    </div>
  );
}
