import { useState, useRef, useEffect } from "react"
import { askPolicy } from "../api/policyQa"
import { Button } from "../components/ui/button"
import { Spinner } from "../components/ui/spinner"
import { Send } from "lucide-react"

const SUGGESTIONS = [
  "What is the per-meal dinner limit for a grade 4 employee?",
  "Can I expense alcohol at a client dinner?",
  "What class of service is allowed for domestic flights?",
  "What is the hotel rate limit in New York City?",
]

function Message({ msg }) {
  if (msg.role === "user") return (
    <div className="flex justify-end">
      <div className="bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2 max-w-md text-sm">
        {msg.content}
      </div>
    </div>
  )

  return (
    <div className="flex justify-start">
      <div className="max-w-2xl space-y-3">
        <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 text-sm text-gray-800 leading-relaxed shadow-sm">
          {msg.content}
        </div>
        {msg.citations?.length > 0 && (
          <div className="space-y-1 pl-1">
            {msg.citations.map((c, i) => (
              <div key={i} className="text-xs text-blue-700 bg-blue-50 border border-blue-100 rounded px-2 py-1">
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
  )
}

export default function PolicyQA() {
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
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-8 py-5 border-b border-gray-200 bg-white">
        <h2 className="text-xl font-semibold text-gray-900">Policy Q&amp;A</h2>
        <p className="text-sm text-gray-500 mt-0.5">Ask anything about Northwind expense and travel policies.</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto px-8 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full space-y-6">
            <p className="text-gray-400 text-sm">Try one of these questions:</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl w-full">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left px-4 py-3 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:border-blue-400 hover:text-blue-700 transition-colors shadow-sm"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => <Message key={i} msg={m} />)}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
              <Spinner />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-8 py-4 border-t border-gray-200 bg-white">
        <form
          onSubmit={e => { e.preventDefault(); send() }}
          className="flex gap-3 max-w-3xl mx-auto"
        >
          <input
            className="flex-1 border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Ask a policy question…"
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={loading}
          />
          <Button type="submit" disabled={!input.trim() || loading}>
            <Send size={14} /> Send
          </Button>
        </form>
      </div>
    </div>
  )
}
