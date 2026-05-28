import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { getSubmissions } from "../api/submissions"
import { Badge } from "../components/ui/badge"
import { Spinner } from "../components/ui/spinner"
import {
  Clock, AlertTriangle, CheckCircle2, XCircle,
  ArrowRight, Plus, TrendingUp,
} from "lucide-react"

// ── Helpers ────────────────────────────────────────────────────────────────────

function initials(name) {
  if (!name) return "?"
  return name.split(" ").map(p => p[0]).join("").toUpperCase().slice(0, 2)
}

const AVATAR_COLORS = [
  "bg-blue-500", "bg-violet-500", "bg-emerald-500", "bg-amber-500",
  "bg-pink-500",  "bg-cyan-500",  "bg-orange-500",  "bg-teal-500",
]

function avatarColor(name) {
  if (!name) return AVATAR_COLORS[0]
  return AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length]
}

// ── Stat card ──────────────────────────────────────────────────────────────────

const STAT_META = {
  pending:  { label: "Pending Review", icon: Clock,          iconBg: "bg-amber-50",   iconCls: "text-amber-500",   bar: "bg-amber-400"   },
  flagged:  { label: "Flagged",        icon: AlertTriangle,  iconBg: "bg-orange-50",  iconCls: "text-orange-500",  bar: "bg-orange-400"  },
  approved: { label: "Approved",       icon: CheckCircle2,   iconBg: "bg-emerald-50", iconCls: "text-emerald-500", bar: "bg-emerald-400" },
  rejected: { label: "Rejected",       icon: XCircle,        iconBg: "bg-red-50",     iconCls: "text-red-500",     bar: "bg-red-400"     },
}

function StatCard({ status, count, total }) {
  const { label, icon: Icon, iconBg, iconCls, bar } = STAT_META[status]
  const pct = total > 0 ? Math.round((count / total) * 100) : 0

  return (
    <Link to={`/submissions?status=${status}`} className="block">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer group">
        <div className="flex items-start justify-between mb-5">
          <div className={`w-10 h-10 ${iconBg} rounded-xl flex items-center justify-center`}>
            <Icon size={18} className={iconCls} />
          </div>
          <span className="text-xs font-semibold text-gray-400 bg-gray-50 rounded-lg px-2 py-0.5">
            {pct}%
          </span>
        </div>
        <p className="text-3xl font-bold text-gray-900 tracking-tight">{count}</p>
        <p className="text-sm text-gray-500 mt-1">{label}</p>
        <div className="mt-4 h-1 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full ${bar} rounded-full transition-all duration-700`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </Link>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [submissions, setSubmissions] = useState([])
  const [loading, setLoading]         = useState(true)

  useEffect(() => {
    getSubmissions().then(setSubmissions).finally(() => setLoading(false))
  }, [])

  const counts = submissions.reduce((acc, s) => {
    acc[s.status] = (acc[s.status] ?? 0) + 1
    return acc
  }, {})
  const total  = submissions.length

  const recent = [...submissions]
    .sort((a, b) => new Date(b.submitted_at) - new Date(a.submitted_at))
    .slice(0, 6)

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  })

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <Spinner className="h-8 w-8" />
    </div>
  )

  return (
    <div className="p-8 max-w-6xl mx-auto">

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Dashboard</h2>
          <p className="text-sm text-gray-400 mt-0.5 flex items-center gap-1.5">
            <TrendingUp size={13} />
            {today}
          </p>
        </div>
        <Link to="/new-submission">
          <button className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-sm font-medium px-4 py-2.5 rounded-xl shadow-sm shadow-blue-200 transition-all">
            <Plus size={15} />
            New Submission
          </button>
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {["pending", "flagged", "approved", "rejected"].map(s => (
          <StatCard key={s} status={s} count={counts[s] ?? 0} total={total} />
        ))}
      </div>

      {/* Recent submissions */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h3 className="font-semibold text-gray-900">Recent Submissions</h3>
            <p className="text-xs text-gray-400 mt-0.5">{total} total submissions</p>
          </div>
          <Link
            to="/submissions"
            className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 font-medium bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors"
          >
            View all <ArrowRight size={12} />
          </Link>
        </div>

        <div className="divide-y divide-gray-50">
          {recent.length === 0 && (
            <p className="text-center text-gray-400 text-sm py-12">No submissions yet.</p>
          )}
          {recent.map(sub => (
            <Link
              key={sub.id}
              to={`/submissions/${sub.id}`}
              className="flex items-center gap-4 px-6 py-4 hover:bg-slate-50/60 transition-colors group"
            >
              {/* Avatar */}
              <div className={`w-9 h-9 ${avatarColor(sub.employee_name)} rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-sm`}>
                {initials(sub.employee_name)}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">
                  {sub.employee_name ?? sub.source_folder?.replace(/_/g, " ") ?? `Submission #${sub.id}`}
                </p>
                <p className="text-xs text-gray-400 truncate mt-0.5">{sub.trip_purpose ?? "—"}</p>
              </div>

              {/* Right */}
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-gray-400 hidden sm:block">
                  {sub.trip_dates?.split(" to ")[0]}
                </span>
                <span className="text-sm font-bold text-gray-800">
                  ${sub.total_amount?.toFixed(2)}
                </span>
                <Badge variant={sub.status}>{sub.status.replace("_", " ")}</Badge>
                <ArrowRight size={14} className="text-gray-300 group-hover:text-blue-400 group-hover:translate-x-0.5 transition-all" />
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
