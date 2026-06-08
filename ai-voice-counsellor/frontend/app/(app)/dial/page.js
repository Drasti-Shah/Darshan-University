"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function DialPage() {
  const [number, setNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function dial(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    const to = number.trim();
    if (!to) return;
    setBusy(true);
    try {
      const r = await api.call(to);
      setResult(r);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dial Up</h1>
        <p className="text-sm text-slate-500">
          Place an outbound counselling call. The agent greets in Gujarati, asks name,
          qualification &amp; marks, then suggests Darshan University programs.
        </p>
      </div>

      <form onSubmit={dial} className="card p-6 space-y-4">
        <div>
          <label className="label">Student phone number</label>
          <input
            className="input text-lg tracking-wide"
            placeholder="9724556935  or  +9197…"
            value={number}
            onChange={(e) => setNumber(e.target.value)}
          />
          <p className="mt-1.5 text-xs text-slate-400">
            10-digit numbers are assumed Indian (+91). Trial Twilio accounts can only
            call verified numbers.
          </p>
        </div>
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Calling…" : "📞 Call now"}
        </button>
      </form>

      {result && (
        <div className="card p-5 border-green-200 bg-green-50">
          <div className="font-medium text-green-800">Call queued ✅</div>
          <dl className="mt-2 text-sm text-green-900 grid grid-cols-[120px_1fr] gap-1">
            <dt className="text-green-700">To</dt>
            <dd>{result.to}</dd>
            <dt className="text-green-700">Status</dt>
            <dd>{result.status}</dd>
            <dt className="text-green-700">Call SID</dt>
            <dd className="font-mono text-xs">{result.sid}</dd>
          </dl>
          <p className="mt-3 text-xs text-green-700">
            The conversation will appear under Leads &amp; Call Logs once it completes.
          </p>
        </div>
      )}

      {error && (
        <div className="card p-5 border-red-200 bg-red-50 text-sm text-red-700">
          Call failed — {error}
        </div>
      )}
    </div>
  );
}
