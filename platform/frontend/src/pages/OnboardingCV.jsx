import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, RotateCcw, ShieldCheck, Sparkles } from "lucide-react";
import FileDropzone from "../components/FileDropzone";
import Stepper from "../components/Stepper";
import AnimatedBackground from "../components/AnimatedBackground";
import { uploadCV } from "../api/cv";
import { useAuth } from "../auth/AuthContext";
import { getCV, setCV } from "../auth/flow";

const STEPS = ["Upload CV", "Profile", "Recommendations"];

export default function OnboardingCV() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(0);
  const [replace, setReplace] = useState(false);
  const existingCvId = user ? getCV(user.user_id) : null;

  const mutation = useMutation({
    mutationFn: () => uploadCV(file, setProgress),
    onSuccess: (data) => {
      setCV(user.user_id, data.cv_id);
      navigate("/onboarding/profile");
    },
  });

  // If the user already has a CV and isn't explicitly replacing it,
  // show a short confirmation card with a clear "Continue" CTA.
  if (existingCvId && !replace) {
    return (
      <div className="relative min-h-[calc(100vh-3.5rem)]">
        <AnimatedBackground variant="app" />
        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 py-12">
          <Stepper steps={STEPS} current={0} className="mb-10" />

          <div className="card p-8 sm:p-10 animate-fade-up">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                            bg-emerald-500/10 border border-emerald-500/30 text-[11px] text-emerald-300">
              <CheckCircle2 size={12} /> CV already on file
            </div>
            <h1 className="mt-3 text-3xl font-display font-medium tracking-tight text-text">
              You're all set.
            </h1>
            <p className="mt-2 text-text-mute">
              We already parsed a résumé for you. You can jump straight to your recommendations,
              tweak your profile preferences, or replace the CV with a new file.
            </p>

            <div className="mt-7 flex flex-wrap gap-2">
              <Link to="/recommendations" className="btn-primary btn-lg group">
                See my recommendations
                <ArrowRight size={15} className="transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link to="/profile" className="btn-secondary">Edit profile preferences</Link>
              <button onClick={() => setReplace(true)} className="btn-ghost">
                <RotateCcw size={15} /> Replace CV
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-[calc(100vh-3.5rem)]">
      <AnimatedBackground variant="app" />
      <div className="relative max-w-3xl mx-auto px-4 sm:px-6 py-12">
        <Stepper steps={STEPS} current={0} className="mb-10" />

        <div className="card p-8 sm:p-10 animate-fade-up">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                          bg-brand-500/10 border border-brand-500/20 text-[11px] text-brand-300">
            <Sparkles size={11} /> Step 1 of 3
          </div>
          <h1 className="mt-3 text-3xl font-display font-medium tracking-tight text-text">
            Drop your CV
          </h1>
          <p className="mt-2 text-text-mute">
            We extract a structured profile (skills, experience, languages, location) and embed
            it in a 384-dim vector for semantic matching against thousands of offers.
          </p>

          <div className="mt-8">
            <FileDropzone onFile={setFile} disabled={mutation.isPending} file={file} />
          </div>

          {mutation.isPending && (
            <div className="mt-5">
              <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
                <div className="h-full bg-gradient-cta transition-all"
                     style={{ width: `${progress}%` }} />
              </div>
              <p className="text-xs text-text-dim mt-2">Uploading… {progress}%</p>
            </div>
          )}
          {mutation.isError && (
            <div className="mt-4 rounded-lg bg-rose-500/10 border border-rose-500/30 px-3 py-2 text-sm text-rose-300">
              Upload failed: {mutation.error.response?.data?.detail ?? mutation.error.message}
            </div>
          )}

          <div className="mt-8 flex items-center justify-between">
            <Link to="/onboarding/profile" className="btn-ghost">Skip — fill the form instead</Link>
            <button onClick={() => mutation.mutate()}
                    disabled={!file || mutation.isPending}
                    className="btn-primary btn-lg group">
              {mutation.isPending ? "Uploading…" : "Continue"}
              <ArrowRight size={15} className="transition-transform group-hover:translate-x-0.5" />
            </button>
          </div>

          <div className="mt-8 pt-6 border-t border-line flex items-start gap-2 text-xs text-text-dim">
            <ShieldCheck size={13} className="text-emerald-400 shrink-0 mt-0.5" />
            Your file lives in a private MinIO bucket. A Kafka worker parses it asynchronously and only
            your structured profile is cached. The raw CV never leaves your storage.
          </div>
        </div>
      </div>
    </div>
  );
}
