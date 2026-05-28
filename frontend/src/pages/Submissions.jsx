import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { getSubmissions } from "../api/submissions"
import { Badge } from "../components/ui/badge"
import { Spinner } from "../components/ui/spinner"
import { Search, ArrowRight, Plus } from "lucide-react"

const STATUSES = ["all", "pending", "flagged", "needs_review", "approved", "rejected"]

const STATUS_COUNTS_LABEL = {
  all: "All", pending: "Pending", flagged: "Flagged",
  needs_review: "Needs Review", approved: "Approved", rejected: "Rejected",
}

function initials(name) {
  if (!name) return "?"
  return name.split(" ").map(p => p[0]).join("").toUpperCase().slice(0, 2)
}

const AVATAR_COLORS = [
  "bg-blue-500","bg-violet-500","bg-emerald-500","bg-amber-500",
  "bg-pink-500","bg-cyan-500","bg-orange-500","bg-teal-500",
]
function avatarColor(name) {
  if (!name) return AVATAR_COLORS[0]
  return AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length]
}

function parseStartDate(tripDates) {
  if (!tripDates) return null
  const m = tripDates.match(/\d{4}-\d{2}-\d{2}/)
  return m ? m[0] : null
}

export default function Submissions() {
  const [submissions, setSubmissions] = useState([])
  const [filter, setFilter]           = useState("all")
  const [search, setSearch]           = useState("")
  const [dateFrom, setDateFrom]       = useState("")
  const [dateTo, setDateTo]           = useState("")
  const [loading, setLoading]         = useState(true)

  useEffect(() => {
    getSubmissions().then(setSubmissions).finally(() => setLoading(false))
  }, [])

  const counts = submissions.reduce((acc, s) => {
    acc[s.status] = (acc[s.status] ?? 0) + 1
    return acc
  }, {})

  const searchLower = search.toLowerCase()
  const visible = submissions.filter(s => {
    if (filter !== "all" && s.status !== filter) return false
    if (searchLower) {
      const hay = [s.employee_name, s.employee_nw_id, s.trip_purpose, s.source_folder?.replace(/_/g, " ")]
        .join(" ").toLowerCase()
      if (!hay.includes(searchLower)) return false
    }
    if (dateFrom || dateTo) {
      const start = parseStartDate(s.trip_dates)
      if (!start) return false
      if (dateFrom && start < dateFrom) return false
      if (dateTo   && start > dateTo)   return false
    }
    return true
  })

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <Spinner className="h-8 w-8" />
    </div>
  )

  return (
    <div className="p-8 max-w-6xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Submissions</h2>
          <p className="text-sm text-gray-400 mt-0.5">{submissions.length} total submissions</p>
        </div>
        <Link to="/new-submission">
          <button className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-sm font-medium px-4 py-2.5 rounded-xl shadow-sm shadow-blue-200 transition-all">
            <Plus size={15} /> New Submission
          </button>
        </Link>
      </div>

      {/* Search + date filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-56">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="w-full pl-9 pr-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-sm"
            placeholder="Search by employee, ID, or trip…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-3 shadow-sm">
          <span className="text-xs text-gray-400">From</span>
          <input type="date" className="py-2.5 text-sm bg-transparent focus:outline-none text-gray-700"
            value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
        </div>
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-3 shadow-sm">
          <span className="text-xs text-gray-400">To</span>
          <input type="date" className="py-2.5 text-sm bg-transparent focus:outline-none text-gray-700"
            value={dateTo} onChange={e => setDateTo(e.target.value)} min={dateFrom} />
        </div>
        {(search || dateFrom || dateTo) && (
          <button
            onClick={() => { setSearch(""); setDateFrom(""); setDateTo("") }}
            className="text-xs text-gray-500 hover:text-gray-800 px-3 py-2 rounded-xl border border-gray-200 bg-white shadow-sm hover:border-gray-300 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Status tabs */}
      <div className="flex gap-1.5 mb-6 flex-wrap">
        {STATUSES.map(s => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              filter === s
                ? "bg-blue-600 text-white shadow-sm shadow-blue-200"
                : "bg-white text-gray-500 border border-gray-200 hover:border-gray-300 hover:text-gray-700"
            }`}
          >
            {STATUS_COUNTS_LABEL[s]}
            {s !== "all" && counts[s] > 0 && (
              <span className={`ml-1.5 text-xs ${filter === s ? "text-blue-200" : "text-gray-400"}`}>
                {counts[s]}
              </span>
            )}
            {s === "all" && (
              <span className={`ml-1.5 text-xs ${filter === s ? "text-blue-200" : "text-gray-400"}`}>
                {submissions.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Table card */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50/80 border-b border-gray-100">
              <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Employee</th>
              <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Trip</th>
              <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Dates</th>
              <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Total</th>
              <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {visible.map(sub => (
              <tr key={sub.id} className="hover:bg-slate-50/60 transition-colors group">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 ${avatarColor(sub.employee_name)} rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-sm`}>
                      {initials(sub.employee_name)}
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900 text-sm">{sub.employee_name ?? "—"}</p>
                      <p className="text-xs text-gray-400">{sub.employee_nw_id}</p>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 max-w-xs">
                  <Link to={`/submissions/${sub.id}`} className="font-medium text-blue-600 hover:text-blue-700 hover:underline text-sm">
                    {sub.source_folder?.replace(/_/g, " ") ?? `Submission #${sub.id}`}
                  </Link>
                  <p className="text-xs text-gray-400 mt-0.5 truncate">{sub.trip_purpose}</p>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap">{sub.trip_dates}</td>
                <td className="px-6 py-4 font-bold text-gray-900">${sub.total_amount?.toFixed(2)}</td>
                <td className="px-6 py-4">
                  <Badge variant={sub.status}>{sub.status.replace("_", " ")}</Badge>
                </td>
                <td className="px-6 py-4">
                  <Link to={`/submissions/${sub.id}`}>
                    <ArrowRight size={15} className="text-gray-300 group-hover:text-blue-400 group-hover:translate-x-0.5 transition-all" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {visible.length === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-400 text-sm">No submissions match your filters.</p>
          </div>
        )}
      </div>
    </div>
  )
}
