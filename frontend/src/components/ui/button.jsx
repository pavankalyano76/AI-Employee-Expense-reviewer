import { cn } from "../../lib/utils"

const variants = {
  primary:   "bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white shadow-sm shadow-blue-200 disabled:opacity-50 disabled:shadow-none",
  secondary: "bg-white hover:bg-gray-50 active:bg-gray-100 text-gray-700 border border-gray-200 hover:border-gray-300 shadow-sm disabled:opacity-50",
  danger:    "bg-red-600 hover:bg-red-700 active:bg-red-800 text-white shadow-sm disabled:opacity-50",
  ghost:     "text-gray-600 hover:bg-gray-100 active:bg-gray-200 disabled:opacity-50",
}

export function Button({ children, variant = "primary", className, ...props }) {
  return (
    <button
      className={cn(
        "inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all active:scale-[0.98] cursor-pointer disabled:cursor-not-allowed",
        variants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}
