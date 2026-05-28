import { cn } from "../../lib/utils"

const variants = {
  approved:     "bg-emerald-50 text-emerald-700 border-emerald-200 ring-emerald-100",
  flagged:      "bg-amber-50  text-amber-700  border-amber-200  ring-amber-100",
  rejected:     "bg-red-50    text-red-700    border-red-200    ring-red-100",
  pending:      "bg-slate-100 text-slate-600  border-slate-200  ring-slate-100",
  under_review: "bg-blue-50   text-blue-700   border-blue-200   ring-blue-100",
  needs_review: "bg-orange-50 text-orange-700 border-orange-200 ring-orange-100",
  default:      "bg-slate-100 text-slate-600  border-slate-200  ring-slate-100",
}

const dots = {
  approved:     "bg-emerald-500",
  flagged:      "bg-amber-500",
  rejected:     "bg-red-500",
  pending:      "bg-slate-400",
  under_review: "bg-blue-500",
  needs_review: "bg-orange-500",
  default:      "bg-slate-400",
}

export function Badge({ children, variant = "default", className }) {
  const v = variants[variant] ?? variants.default
  const d = dots[variant]    ?? dots.default
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border",
      v,
      className,
    )}>
      <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", d)} />
      {children}
    </span>
  )
}
