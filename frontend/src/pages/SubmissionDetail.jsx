import { useEffect, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { getSubmission, reviewSubmission, overrideSubmission } from "../api/submissions"
import { Card, CardHeader, CardContent } from "../components/ui/card"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Spinner } from "../components/ui/spinner"
import { ChevronDown, ChevronRight, RotateCcw, Sparkles, ArrowLeft, User } from "lucide-react"

// ── Helpers ────────────────────────────────────────────────────────────────────

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

const VERDICT_ACCENT = {
  approved:     "border-l-emerald-400 bg-emerald-50/30",
  flagged:      "border-l-amber-400   bg-amber-50/30",
  needs_review: "border-l-orange-400  bg-orange-50/30",
  rejected:     "border-l-red-400     bg-red-50/30",
}

const VERDICT_LABEL = {
  approved:     "compliant",
  flagged:      "flagged",
  needs_review: "needs review",
  rejected:     "rejected",
}

// ── Verdict row ────────────────────────────────────────────────────────────────

function VerdictRow({ verdict, amount, filename }) {
  const [open, setOpen] = useState(false)
  const accent = VERDICT_ACCENT[verdict.verdict] ?? "border-l-gray-300 bg-gray-50/30"

  return (
    <div className={`border border-gray-100 border-l-4 ${accent} rounded-xl overflow-hidden`}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/60 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          {open ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
          <span className="text-sm font-medium text-gray-800">{verdict.description || filename}</span>
        </div>
        <div className="flex items-center gap-3">
          {amount != null && <span className="text-sm font-bold text-gray-700">${amount.toFixed(2)}</span>}
          <Badge variant={verdict.verdict}>{VERDICT_LABEL[verdict.verdict] ?? verdict.verdict.replace("_", " ")}</Badge>
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4 pt-1 space-y-3 bg-white/60">
          <p className="text-sm text-gray-700 leading-relaxed">{verdict.reason}</p>
          {verdict.policy_citations?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Policy Citations</p>
              <div className="space-y-1.5">
                {verdict.policy_citations.map((c, i) => (
                  <div key={i} className="text-xs text-blue-700 bg-blue-50 border border-blue-100 rounded-lg px-3 py-1.5 leading-relaxed">
                    {c}
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="flex items-center gap-2 pt-1">
            <span className="text-xs text-gray-400">Confidence</span>
            <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden max-w-32">
              <div
                className="h-full bg-blue-400 rounded-full"
                style={{ width: `${((verdict.confidence ?? 0) * 100).toFixed(0)}%` }}
              />
            </div>
            <span className="text-xs font-medium text-gray-500">
              {((verdict.confidence ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Override form ──────────────────────────────────────────────────────────────

function OverrideForm({ submissionId, onDone }) {
  const [show, setShow]     = useState(false)
  const [form, setForm]     = useState({ overridden_by: "", new_status: "approved", reason: "" })
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!form.overridden_by || !form.reason) return
    setSaving(true)
    try {
      await overrideSubmission(submissionId, { submission_id: submissionId, ...form })
      onDone()
      setShow(false)
    } finally {
      setSaving(false)
    }
  }

  if (!show) return (
    <Button variant="secondary" onClick={() => setShow(true)}>
      <RotateCcw size={14} /> Override Decision
    </Button>
  )

  return (
    <Card>
      <CardHeader>
        <h4 className="font-semibold text-gray-900 flex items-center gap-2">
          <RotateCcw size={15} className="text-gray-500" /> Manager Override
        </h4>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Your email</label>
          <input
            className="mt-1.5 w-full bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:bg-white transition-all"
            placeholder="manager@northwind.com"
            value={form.overridden_by}
            onChange={e => setForm(f => ({ ...f, overridden_by: e.target.value }))}
          />
        </div>
        <div>
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">New status</label>
          <select
            className="mt-1.5 w-full bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:bg-white transition-all"
            value={form.new_status}
            onChange={e => setForm(f => ({ ...f, new_status: e.target.value }))}
          >
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="pending">Pending (reset)</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Reason</label>
          <textarea
            className="mt-1.5 w-full bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:bg-white transition-all resize-none"
            rows={3}
            placeholder="Explain your decision…"
            value={form.reason}
            onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
          />
        </div>
        <div className="flex gap-2 pt-1">
          <Button onClick={submit} disabled={saving || !form.overridden_by || !form.reason}>
            {saving ? <Spinner /> : null} Save Override
          </Button>
          <Button variant="ghost" onClick={() => setShow(false)}>Cancel</Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SubmissionDetail() {
  const { id } = useParams()
  const [sub, setSub]           = useState(null)
  const [loading, setLoading]   = useState(true)
  const [reviewing, setReviewing] = useState(false)

  const load = () => {
    setLoading(true)
    getSubmission(id).then(setSub).finally(() => setLoading(false))
  }

  useEffect(load, [id])

  const handleReview = async () => {
    setReviewing(true)
    try { await reviewSubmission(id); load() }
    finally { setReviewing(false) }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-full"><Spinner className="h-8 w-8" /></div>
  )
  if (!sub) return <p className="p-8 text-gray-500">Submission not found.</p>

  const emp = sub.employee
  const hasVerdicts = sub.receipts?.some(r => r.verdicts?.length > 0)

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">

      {/* Back */}
      <Link to="/submissions" className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-700 transition-colors">
        <ArrowLeft size={14} /> Submissions
      </Link>

      {/* Header card */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-start gap-5">
          {/* Avatar */}
          <div className={`w-14 h-14 ${avatarColor(emp?.name)} rounded-2xl flex items-center justify-center text-white text-lg font-bold shadow-md shrink-0`}>
            {initials(emp?.name)}
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-gray-900 tracking-tight">{emp?.name ?? "Unknown"}</h2>
                <p className="text-sm text-gray-500 mt-0.5">{emp?.title} · {emp?.department}</p>
                <p className="text-xs text-gray-400 mt-1">{emp?.employee_id} · Grade {emp?.grade}</p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-2xl font-bold text-gray-900">${sub.total_amount?.toFixed(2)}</p>
                <Badge variant={sub.status} className="mt-1 text-xs">
                  {sub.status.replace("_", " ")}
                </Badge>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 gap-3">
              <div>
                <p className="text-xs text-gray-400">Trip Purpose</p>
                <p className="text-sm font-medium text-gray-700 mt-0.5">{sub.trip_purpose ?? "—"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Travel Dates</p>
                <p className="text-sm font-medium text-gray-700 mt-0.5">{sub.trip_dates ?? "—"}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Employee detail strip */}
      <div className="grid grid-cols-3 gap-3">
        {[
          ["Home Base",  emp?.home_base  ?? "—"],
          ["Manager ID", emp?.manager_id ?? "—"],
          ["Submitted",  sub.submitted_at ? new Date(sub.submitted_at).toLocaleDateString() : "—"],
        ].map(([label, val]) => (
          <div key={label} className="bg-white rounded-xl border border-gray-100 shadow-sm px-4 py-3">
            <p className="text-xs text-gray-400">{label}</p>
            <p className="text-sm font-semibold text-gray-700 mt-0.5">{val}</p>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <Button onClick={handleReview} disabled={reviewing}>
          {reviewing
            ? <><Spinner /> Reviewing…</>
            : <><Sparkles size={14} /> Run AI Review</>
          }
        </Button>
        {(sub.status === "flagged" || sub.status === "needs_review") && (
          <OverrideForm submissionId={id} onDone={load} />
        )}
      </div>

      {/* Override history */}
      {sub.overrides?.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="font-semibold text-gray-900">Override History</h3>
          </CardHeader>
          <div className="divide-y divide-gray-100">
            {sub.overrides.map(o => (
              <div key={o.id} className="px-6 py-3.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant={o.original_status}>{o.original_status.replace("_"," ")}</Badge>
                  <span className="text-gray-300">→</span>
                  <Badge variant={o.new_status}>{o.new_status.replace("_"," ")}</Badge>
                  <span className="text-xs text-gray-400 ml-1">by {o.overridden_by}</span>
                  <span className="text-xs text-gray-300 ml-auto">
                    {new Date(o.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="text-sm text-gray-600 mt-1.5 leading-relaxed">{o.reason}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Receipts + verdicts */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">
              Receipts
              <span className="ml-2 text-xs font-normal text-gray-400 bg-gray-100 rounded-full px-2 py-0.5">
                {sub.receipts?.length ?? 0}
              </span>
            </h3>
            {!hasVerdicts && (
              <span className="text-xs text-gray-400">Run AI review to see verdicts</span>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-2.5">
          {sub.receipts?.map(r => (
            <div key={r.id}>
              {r.verdicts?.length > 0
                ? r.verdicts.map(v => (
                    <VerdictRow key={v.id} verdict={v} amount={r.amount} filename={r.filename} />
                  ))
                : (
                  <div className="flex items-center justify-between px-4 py-3 border border-gray-100 rounded-xl bg-gray-50/50">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center">
                        <User size={13} className="text-gray-400" />
                      </div>
                      <span className="text-sm text-gray-700 font-medium">{r.filename}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      {r.amount != null && <span className="text-sm font-bold text-gray-700">${r.amount.toFixed(2)}</span>}
                      <span className="text-xs bg-gray-100 text-gray-500 rounded-lg px-2.5 py-1 font-medium">{r.category}</span>
                    </div>
                  </div>
                )
              }
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
