import { cn } from "../../lib/utils"

export function Card({ children, className }) {
  return (
    <div className={cn("bg-white rounded-2xl border border-gray-100 shadow-sm", className)}>
      {children}
    </div>
  )
}

export function CardHeader({ children, className }) {
  return (
    <div className={cn("px-6 py-4 border-b border-gray-100", className)}>
      {children}
    </div>
  )
}

export function CardContent({ children, className }) {
  return (
    <div className={cn("px-6 py-4", className)}>
      {children}
    </div>
  )
}
