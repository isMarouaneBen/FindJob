import { cn } from "../lib/cn";

export default function EmptyState({ icon: Icon, title, description, action, className }) {
  return (
    <div className={cn("card p-12 text-center flex flex-col items-center gap-3", className)}>
      {Icon && (
        <div className="w-12 h-12 rounded-2xl bg-brand-500/10 border border-brand-500/20
                        text-brand-300 grid place-items-center">
          <Icon size={22} />
        </div>
      )}
      {title && <h3 className="text-lg font-semibold text-text">{title}</h3>}
      {description && (
        <p className="text-sm text-text-mute max-w-md leading-relaxed">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
