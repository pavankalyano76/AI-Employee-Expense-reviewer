import { NavLink, Outlet } from "react-router-dom"
import { LayoutDashboard, FileText, Receipt } from "lucide-react"
import { cn } from "../lib/utils"
import PolicyChatbot from "./PolicyChatbot"

const nav = [
  { to: "/",            label: "Dashboard",   icon: LayoutDashboard },
  { to: "/submissions", label: "Submissions", icon: FileText },
]

export default function Layout() {
  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 flex flex-col shrink-0">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-slate-700/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-500 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/25">
              <Receipt size={17} className="text-white" />
            </div>
            <div>
              <h1 className="text-white font-semibold text-sm tracking-tight">Northwind</h1>
              <p className="text-slate-400 text-xs mt-0.5">Expense Reviewer</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
                isActive
                  ? "bg-blue-500/20 text-blue-300 ring-1 ring-inset ring-blue-500/25"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-200",
              )}
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-slate-700/50">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
            <p className="text-xs text-slate-500">Claude · Pinecone · SQLite</p>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>

      {/* Floating chatbot on every page */}
      <PolicyChatbot />
    </div>
  )
}
