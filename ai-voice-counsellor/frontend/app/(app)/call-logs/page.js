"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function CallLogsPage() {
  const [calls, setCalls] = useState([]);
  const [active, setActive] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const data = await api.leads();
      setCalls((data.leads || []).slice().reverse());
      setErr("");
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Call Logs</h1>
        <p className="text-sm text-slate-500">{calls.length} calls · click a row to view the transcript</p>
      </div>

      {err && <div className="card p-4 text-sm text-red-600 bg-red-50 border-red-200">{err}</div>}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-left">
            <tr>
              <th className="px-4 py-3 font-medium">Caller</th>
              <th className="px-4 py-3 font-medium">Number</th>
              <th className="px-4 py-3 font-medium">Outcome</th>
              <th className="px-4 py-3 font-medium">Duration</th>
              <th className="px-4 py-3 font-medium">Turns</th>
              <th className="px-4 py-3 font-medium">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Loading…</td></tr>}
            {!loading && calls.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">No calls yet.</td></tr>
            )}
            {calls.map((c) => (
              <tr key={c.call_sid} className="hover:bg-slate-50 cursor-pointer" onClick={() => setActive(c)}>
                <td className="px-4 py-3 font-medium text-slate-800">{c.name || "Unknown"}</td>
                <td className="px-4 py-3 font-mono text-xs">{c.student_number || "—"}</td>
                <td className="px-4 py-3">
                  <span className={`badge ${c.completed ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>
                    {c.call_status || (c.completed ? "completed" : c.stage || "—")}
                  </span>
                </td>
                <td className="px-4 py-3">{c.call_duration ? `${c.call_duration}s` : "—"}</td>
                <td className="px-4 py-3">{(c.conversation || []).length}</td>
                <td className="px-4 py-3 text-xs text-slate-400">{c.updated_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {active && <TranscriptModal call={active} onClose={() => setActive(null)} />}
    </div>
  );
}

function TranscriptModal({ call, onClose }) {
  return (
    <div className="fixed inset-0 z-30 bg-black/40 grid place-items-center p-4" onClick={onClose}>
      <div className="card w-full max-w-2xl max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-slate-800">{call.name || "Unknown caller"}</h2>
            <p className="text-xs text-slate-400">
              {call.student_number} · {call.qualification || "—"}
              {call.marks ? ` · ${call.marks}` : ""} · {call.call_duration || 0}s
            </p>
          </div>
          <button className="btn-ghost px-3 py-1.5" onClick={onClose}>✕</button>
        </div>
        <div className="p-5 overflow-y-auto space-y-3">
          {(call.conversation || []).map((m, i) => (
            <div key={i} className={`flex ${m.role === "assistant" ? "justify-start" : "justify-end"}`}>
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                  m.role === "assistant"
                    ? "bg-slate-100 text-slate-800 rounded-tl-sm"
                    : "bg-brand text-white rounded-tr-sm"
                }`}
              >
                <div className="text-[10px] uppercase tracking-wide opacity-60 mb-0.5">
                  {m.role === "assistant" ? "Agent" : "Student"}
                </div>
                {m.content}
              </div>
            </div>
          ))}
          {(call.conversation || []).length === 0 && (
            <div className="text-center text-sm text-slate-400 py-6">No transcript.</div>
          )}
        </div>
      </div>
    </div>
  );
}
