import { useState, useRef, useEffect } from "react"
import { MessageCircle, X, Maximize2, Minimize2, Send } from "lucide-react"
import { askPolicy } from "../api/policyQa"
import { Spinner } from "./ui/spinner"

const SUGGESTIONS = [
  "What is the per-meal dinner limit for a grade 4 employee?",
  "Can I expense alcohol at a client dinner?",
  "What class of service is allowed for domestic flights?",
  "What is the hotel rate limit in New York City?",
]

export default function PolicyChatbot() {
  const [open, setOpen]         = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState("")
  const [loading, setLoading]   = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const send = async (question = input.trim()) => {
    if (!question || loading) return
    setInput("")
    setMessages(m => [...m, { role: "user", content: question }])
    setLoading(true)
    try {
      const res = await askPolicy(question)
      setMessages(m => [...m, {
        role: "assistant",
        content: res.answer,
        citations: res.citations,
        is_in_scope: res.is_in_scope,
      }])
    } catch {
      setMessages(m => [...m, { role: "assistant", content: "Error reaching the server. Is the backend running?" }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
      {open && (
        <div
          className={`flex flex-col bg-white border border-gray-200 rounded-2xl shadow-2xl overflow-hidden transition-all duration-200 ${
            expanded ? "w-[680px] h-[640px]" : "w-96 h-[520px]"
          }`}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-blue-600 text-white shrink-0">
            <div>
              <p className="font-semibold text-sm">Policy Assistant</p>
              <p className="text-xs text-blue-200">Ask about Northwind policies</p>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setExpanded(e => !e)}
                className="hover:bg-blue-500 p-1.5 rounded transition-colors"
                title={expanded ? "Collapse" : "Expand"}
              >
                {expanded ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
              </button>
              <button
                onClick={() => setOpen(false)}
                className="hover:bg-blue-500 p-1.5 rounded transition-colors"
                title="Close"
              >
                <X size={13} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-auto px-4 py-4 space-y-3">
            {messages.length === 0 && (
              <div className="space-y-3">
                {/* Welcome bubble */}
                <div className="flex justify-start">
                  <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[90%]">
                    <p className="text-xs font-semibold text-blue-700 mb-1">Policy Assistant</p>
                    <p className="text-xs text-gray-700 leading-relaxed">
                      Hi there! 👋 I can answer questions about Northwind's expense and travel policies — meal limits, hotel caps, flight class rules, and more. What would you like to know?
                    </p>
                  </div>
                </div>
                <p className="text-xs text-gray-400 text-center pt-1">Try one of these:</p>
                {SUGGESTIONS.map(s => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="w-full text-left text-xs px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className="max-w-[85%] space-y-1">
                  <div className={`rounded-2xl px-3 py-2 text-xs leading-relaxed ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white rounded-br-sm"
                      : "bg-gray-100 text-gray-800 rounded-bl-sm"
                  }`}>
                    {msg.content}
                  </div>
                  {msg.citations?.length > 0 && (
                    <div className="space-y-0.5 pl-1">
                      {msg.citations.map((c, ci) => (
                        <div key={ci} className="text-xs text-blue-700 bg-blue-50 border border-blue-100 rounded px-2 py-0.5">
                          {c}
                        </div>
                      ))}
                    </div>
                  )}
                  {msg.is_in_scope === false && (
                    <p className="text-xs text-gray-400 pl-1">Out of scope — only policy questions are supported.</p>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-3 py-2">
                  <Spinner />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="px-3 py-3 border-t border-gray-100 shrink-0">
            <form
              onSubmit={e => { e.preventDefault(); send() }}
              className="flex gap-2"
            >
              <input
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Ask a policy question…"
                value={input}
                onChange={e => setInput(e.target.value)}
                disabled={loading}
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-lg px-3 py-2 transition-colors"
              >
                <Send size={13} />
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Launcher button */}
      <div className="flex flex-col items-end gap-2">
        {!open && (
          <div className="bg-white border border-gray-200 text-gray-700 text-xs font-medium px-3 py-2 rounded-xl shadow-md whitespace-nowrap">
            💬 Ask about policies
          </div>
        )}
        <button
          onClick={() => setOpen(o => !o)}
          className="w-14 h-14 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white rounded-full shadow-xl flex items-center justify-center transition-all"
          title="Policy Assistant"
        >
          {open ? <X size={22} /> : <MessageCircle size={22} />}
        </button>
      </div>
    </div>
  )
}
