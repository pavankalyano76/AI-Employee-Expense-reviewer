import { useState, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { getOrCreateEmployee } from "../api/employees"
import { createSubmission, uploadReceipt } from "../api/submissions"
import { Button } from "../components/ui/button"
import { Spinner } from "../components/ui/spinner"
import { Upload, X, CheckCircle, AlertCircle, Search } from "lucide-react"

// ── Step indicator ─────────────────────────────────────────────────────────────
function Steps({ current }) {
  const steps = ["Employee", "Trip Details", "Receipts"]
  return (
    <div className="flex items-center mb-10">
      {steps.map((label, i) => (
        <div key={i} className="flex items-center flex-1 last:flex-none">
          <div className="flex items-center gap-2.5 shrink-0">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
              i < current
                ? "bg-blue-600 text-white shadow-md shadow-blue-200"
                : i === current
                ? "bg-white border-2 border-blue-600 text-blue-600 shadow-sm"
                : "bg-white border-2 border-gray-200 text-gray-400"
            }`}>
              {i < current ? <CheckCircle size={14} /> : i + 1}
            </div>
            <span className={`text-sm font-semibold whitespace-nowrap ${
              i === current ? "text-gray-900" : i < current ? "text-gray-500" : "text-gray-400"
            }`}>
              {label}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div className="flex-1 mx-4 h-0.5 rounded-full overflow-hidden bg-gray-200">
              <div className={`h-full rounded-full transition-all duration-500 ${i < current ? "bg-blue-600 w-full" : "w-0"}`} />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Field ──────────────────────────────────────────────────────────────────────
function Field({ label, required, hint, children }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  )
}

const inputCls = "w-full bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:bg-white transition-all placeholder:text-gray-400"

// ── Step 1: Employee ───────────────────────────────────────────────────────────
function StepEmployee({ data, onChange, onNext }) {
  const [checking, setChecking] = useState(false)
  const [found, setFound]       = useState(null)

  const checkEmployee = async () => {
    if (!data.employee_id) return
    setChecking(true)
    try {
      const emp = await getOrCreateEmployee({ ...data, employee_id: data.employee_id })
      setFound(true)
      onChange({ ...data, ...emp })
    } catch {
      setFound(false)
    } finally {
      setChecking(false)
    }
  }

  const valid = data.employee_id && data.name && data.grade && data.title && data.department

  return (
    <div className="space-y-5">
      {/* ID lookup */}
      <div className="flex gap-3">
        <div className="flex-1">
          <Field label="Employee ID" required hint="Format: NW-XXXXX">
            <input className={inputCls} placeholder="NW-04821"
              value={data.employee_id}
              onChange={e => { onChange({ ...data, employee_id: e.target.value }); setFound(null) }}
            />
          </Field>
        </div>
        <div className="pt-7">
          <Button variant="secondary" onClick={checkEmployee} disabled={!data.employee_id || checking}>
            {checking ? <Spinner /> : <><Search size={13} /> Look up</>}
          </Button>
        </div>
      </div>

      {found === true && (
        <div className="flex items-center gap-2.5 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-xl px-4 py-3 text-sm">
          <CheckCircle size={15} className="shrink-0" />
          <span><strong>Employee found.</strong> Fields pre-filled from the existing record.</span>
        </div>
      )}
      {found === false && (
        <div className="flex items-center gap-2.5 bg-blue-50 border border-blue-200 text-blue-700 rounded-xl px-4 py-3 text-sm">
          <AlertCircle size={15} className="shrink-0" />
          <span><strong>New employee.</strong> Fill in the details below — they will be created on submit.</span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <Field label="Full Name" required>
          <input className={inputCls} placeholder="Sarah Chen"
            value={data.name} onChange={e => onChange({ ...data, name: e.target.value })} />
        </Field>
        <Field label="Grade" required>
          <select className={inputCls} value={data.grade}
            onChange={e => onChange({ ...data, grade: parseInt(e.target.value) || "" })}>
            <option value="">Select grade</option>
            {[1,2,3,4,5,6,7,8,9,10].map(g => <option key={g} value={g}>Grade {g}</option>)}
          </select>
        </Field>
        <Field label="Title" required>
          <input className={inputCls} placeholder="Operations Manager"
            value={data.title} onChange={e => onChange({ ...data, title: e.target.value })} />
        </Field>
        <Field label="Department" required>
          <input className={inputCls} placeholder="Logistics Ops"
            value={data.department} onChange={e => onChange({ ...data, department: e.target.value })} />
        </Field>
        <Field label="Manager ID">
          <input className={inputCls} placeholder="NW-03012"
            value={data.manager_id} onChange={e => onChange({ ...data, manager_id: e.target.value })} />
        </Field>
        <Field label="Home Base">
          <input className={inputCls} placeholder="Irvine, CA"
            value={data.home_base} onChange={e => onChange({ ...data, home_base: e.target.value })} />
        </Field>
      </div>

      <div className="flex justify-end pt-2">
        <Button onClick={onNext} disabled={!valid}>Continue →</Button>
      </div>
    </div>
  )
}

// ── Step 2: Trip ───────────────────────────────────────────────────────────────
function StepTrip({ data, onChange, onBack, onNext }) {
  const [startDate, endDate] = (data.trip_dates || " to ").split(" to ")

  const setDates = (start, end) =>
    onChange({ ...data, trip_dates: `${start} to ${end}` })

  const valid = data.trip_purpose && startDate && endDate && startDate <= endDate

  return (
    <div className="space-y-5">
      <Field label="Trip Purpose" required>
        <textarea className={inputCls} rows={3}
          placeholder="Quarterly client review with Mountain Freight Partners in Denver"
          value={data.trip_purpose}
          onChange={e => onChange({ ...data, trip_purpose: e.target.value })}
        />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Start Date" required>
          <input type="date" className={inputCls}
            value={startDate}
            onChange={e => setDates(e.target.value, endDate)}
          />
        </Field>
        <Field label="End Date" required>
          <input type="date" className={inputCls}
            value={endDate} min={startDate}
            onChange={e => setDates(startDate, e.target.value)}
          />
        </Field>
      </div>
      {startDate && endDate && startDate > endDate && (
        <p className="text-xs text-red-500 flex items-center gap-1.5">
          <AlertCircle size={12} /> End date must be on or after start date.
        </p>
      )}
      <div className="flex justify-between pt-2">
        <Button variant="secondary" onClick={onBack}>← Back</Button>
        <Button onClick={onNext} disabled={!valid}>Continue →</Button>
      </div>
    </div>
  )
}

// ── Step 3: Receipts ───────────────────────────────────────────────────────────
const ACCEPTED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".txt"]
const ACCEPTED_ACCEPT     = ACCEPTED_EXTENSIONS.join(",")

const EXT_STYLE = {
  pdf:  "bg-red-50   text-red-600   border-red-100",
  txt:  "bg-gray-100 text-gray-500  border-gray-200",
  jpg:  "bg-green-50 text-green-600 border-green-100",
  jpeg: "bg-green-50 text-green-600 border-green-100",
  png:  "bg-green-50 text-green-600 border-green-100",
  gif:  "bg-green-50 text-green-600 border-green-100",
  webp: "bg-green-50 text-green-600 border-green-100",
}

function FileTypePill({ name }) {
  const ext = name.split(".").pop().toLowerCase()
  const cls = EXT_STYLE[ext] ?? "bg-gray-100 text-gray-500 border-gray-200"
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-lg border ${cls}`}>
      {ext.toUpperCase()}
    </span>
  )
}

function StepReceipts({ files, onChange, onBack, onSubmit, submitting, progress }) {
  const inputRef = useRef()
  const [dragging, setDragging] = useState(false)

  const addFiles = incoming => {
    const next = Array.from(incoming).filter(f => {
      const ext = "." + f.name.split(".").pop().toLowerCase()
      return ACCEPTED_EXTENSIONS.includes(ext)
    })
    onChange(prev => {
      const names = new Set(prev.map(f => f.name))
      return [...prev, ...next.filter(f => !names.has(f.name))]
    })
  }

  const removeFile = name => onChange(prev => prev.filter(f => f.name !== name))

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onClick={() => inputRef.current.click()}
        className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all ${
          dragging
            ? "border-blue-400 bg-blue-50 scale-[1.01]"
            : "border-gray-200 bg-gray-50/50 hover:border-blue-300 hover:bg-blue-50/40"
        }`}
      >
        <div className="w-12 h-12 bg-blue-50 border border-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-3">
          <Upload size={22} className="text-blue-400" />
        </div>
        <p className="text-sm font-semibold text-gray-700">Drop receipts here or click to browse</p>
        <p className="text-xs text-gray-400 mt-1">PDF · JPG · PNG · WEBP · TXT — multiple files supported</p>
        <input ref={inputRef} type="file" accept={ACCEPTED_ACCEPT} multiple className="hidden"
          onChange={e => addFiles(e.target.files)} />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map(f => {
            const state = progress[f.name]
            return (
              <li key={f.name} className="flex items-center justify-between px-4 py-3 bg-white border border-gray-100 rounded-xl shadow-sm">
                <div className="flex items-center gap-3 min-w-0">
                  {state === "done"    && <CheckCircle size={15} className="text-emerald-500 shrink-0" />}
                  {state === "error"   && <AlertCircle size={15} className="text-red-500 shrink-0" />}
                  {state === "loading" && <Spinner className="h-4 w-4 shrink-0" />}
                  {!state             && <div className="w-4 h-4 rounded-full border-2 border-gray-300 shrink-0" />}
                  <span className="text-sm text-gray-700 truncate">{f.name}</span>
                  <FileTypePill name={f.name} />
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-3">
                  <span className="text-xs text-gray-400">{(f.size / 1024).toFixed(0)} KB</span>
                  {!submitting && (
                    <button onClick={() => removeFile(f.name)} className="text-gray-300 hover:text-red-400 transition-colors">
                      <X size={14} />
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}

      <div className="flex justify-between pt-2">
        <Button variant="secondary" onClick={onBack} disabled={submitting}>← Back</Button>
        <Button onClick={onSubmit} disabled={files.length === 0 || submitting}>
          {submitting
            ? <><Spinner /> Submitting…</>
            : `Submit ${files.length} Receipt${files.length !== 1 ? "s" : ""}`
          }
        </Button>
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function NewSubmission() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)

  const [employee, setEmployee] = useState({
    employee_id: "", name: "", grade: "", title: "",
    department: "", manager_id: "", home_base: "",
  })
  const [trip, setTrip]         = useState({ trip_purpose: "", trip_dates: "" })
  const [files, setFiles]       = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [progress, setProgress] = useState({})
  const [error, setError]       = useState("")

  const setFileState = (name, state) =>
    setProgress(p => ({ ...p, [name]: state }))

  const handleSubmit = async () => {
    setSubmitting(true)
    setError("")
    try {
      const emp = await getOrCreateEmployee({
        employee_id: employee.employee_id,
        name: employee.name,
        grade: parseInt(employee.grade),
        title: employee.title,
        department: employee.department,
        manager_id: employee.manager_id || null,
        home_base: employee.home_base || null,
      })
      const sub = await createSubmission({
        employee_id: emp.id,
        trip_purpose: trip.trip_purpose,
        trip_dates: trip.trip_dates,
      })
      for (const file of files) {
        setFileState(file.name, "loading")
        try {
          await uploadReceipt(sub.id, file)
          setFileState(file.name, "done")
        } catch {
          setFileState(file.name, "error")
        }
      }
      navigate(`/submissions/${sub.id}`)
    } catch (e) {
      setError(e.response?.data?.detail ?? "Something went wrong. Please try again.")
    } finally {
      setSubmitting(false)
    }
  }

  const STEP_TITLES = ["Employee Details", "Trip Details", "Upload Receipts"]

  return (
    <div className="min-h-full bg-slate-50 py-10 px-8">
      <div className="max-w-2xl mx-auto">
        {/* Page header */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight">New Submission</h2>
          <p className="text-sm text-gray-400 mt-1">{STEP_TITLES[step]}</p>
        </div>

        <Steps current={step} />

        {/* Form card */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-7">
          {error && (
            <div className="mb-5 flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
              <AlertCircle size={15} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
          {step === 0 && <StepEmployee data={employee} onChange={setEmployee} onNext={() => setStep(1)} />}
          {step === 1 && <StepTrip     data={trip}     onChange={setTrip}     onBack={() => setStep(0)} onNext={() => setStep(2)} />}
          {step === 2 && (
            <StepReceipts
              files={files} onChange={setFiles}
              onBack={() => setStep(1)} onSubmit={handleSubmit}
              submitting={submitting} progress={progress}
            />
          )}
        </div>
      </div>
    </div>
  )
}
