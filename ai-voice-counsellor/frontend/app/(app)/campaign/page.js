"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

// Pull phone numbers out of pasted text or a CSV/TXT file. Handles header rows
// and multi-column CSVs by taking the first cell on each line that has >=10 digits.
function extractNumbers(text) {
  const out = [];
  for (const line of text.split(/\r?\n/)) {
    for (const cell of line.split(/[,;\t]/)) {
      const cleaned = cell.replace(/[^\d+]/g, "");
      const digitCount = cleaned.replace(/\D/g, "").length;
      if (digitCount >= 10) {
        out.push(cleaned);
        break;
      }
    }
  }
  return out;
}

export default function CampaignPage() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [fileInfo, setFileInfo] = useState("");
  const [history, setHistory] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const fileRef = useRef(null);

  const numbers = extractNumbers(text);

  async function loadHistory() {
    try {
      const r = await api.campaigns();
      setHistory(r.campaigns || []);
    } catch (_) {}
  }

  useEffect(() => {
    loadHistory();
    const t = setInterval(loadHistory, 8000);
    return () => clearInterval(t);
  }, []);

  async function onFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    try {
      const content = await file.text();
      const found = extractNumbers(content);
      if (found.length === 0) {
        setError(`No phone numbers found in "${file.name}".`);
        setFileInfo("");
      } else {
        // Merge with whatever is already in the box, de-duplicated.
        const merged = Array.from(new Set([...numbers, ...found]));
        setText(merged.join("\n"));
        setFileInfo(`Loaded ${found.length} number(s) from "${file.name}"`);
      }
    } catch (err) {
      setError("Could not read the file.");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function start(e) {
    e.preventDefault();
    setError("");
    setSummary(null);
    if (numbers.length === 0) return;
    setBusy(true);
    try {
      const r = await api.campaign(numbers);
      setSummary(r);
      loadHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Campaign</h1>
        <p className="text-sm text-slate-500">
          Bulk-dial a list of students. Upload a CSV/TXT file or paste numbers.
        </p>
      </div>

      <form onSubmit={start} className="card p-6 space-y-5">
        {/* CSV upload */}
        <div>
          <label className="label">Upload list (CSV or TXT)</label>
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="btn-ghost"
              onClick={() => fileRef.current?.click()}
            >
              📄 Choose file
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.txt"
              className="hidden"
              onChange={onFile}
            />
            {fileInfo && <span className="text-sm text-green-600">{fileInfo}</span>}
          </div>
          <p className="mt-1.5 text-xs text-slate-400">
            Any CSV works — numbers are auto-detected (header rows &amp; extra
            columns are ignored).
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-400">
          <div className="h-px bg-slate-200 flex-1" /> OR PASTE
          <div className="h-px bg-slate-200 flex-1" />
        </div>

        {/* Manual paste */}
        <div>
          <label className="label">Phone numbers (one per line or comma-separated)</label>
          <textarea
            className="input font-mono text-sm h-40"
            placeholder={"9724556935\n9913000000\n+919876543210"}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="mt-1.5 flex items-center justify-between">
            <p className="text-xs text-slate-400">{numbers.length} number(s) ready</p>
            {text && (
              <button
                type="button"
                className="text-xs text-slate-400 hover:text-red-500"
                onClick={() => { setText(""); setFileInfo(""); }}
              >
                Clear
              </button>
            )}
          </div>
        </div>

        <button type="submit" className="btn-primary" disabled={busy || numbers.length === 0}>
          {busy ? "Dialling…" : `📣 Start campaign (${numbers.length})`}
        </button>
        <p className="text-xs text-amber-600">
          ⚠️ This places real calls. On a trial Twilio account only verified numbers connect.
        </p>
      </form>

      {error && (
        <div className="card p-5 border-red-200 bg-red-50 text-sm text-red-700">{error}</div>
      )}

      {summary && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h2 className="font-semibold text-slate-800">Campaign result</h2>
            <span className="badge bg-green-100 text-green-700">
              {summary.queued}/{summary.total} queued
            </span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="px-4 py-2.5 font-medium">Number</th>
                <th className="px-4 py-2.5 font-medium">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {summary.results.map((r, i) => (
                <tr key={i}>
                  <td className="px-4 py-2.5 font-mono text-xs">{r.to}</td>
                  <td className="px-4 py-2.5">
                    {r.sid ? (
                      <span className="badge bg-green-100 text-green-700">queued · {r.status}</span>
                    ) : (
                      <span className="badge bg-red-100 text-red-700">{r.error}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Campaign history */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-800">Campaign history</h2>
          <p className="text-xs text-slate-400">{history.length} campaign(s) run</p>
        </div>
        {history.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-slate-400">
            No campaigns yet.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {history.map((c) => {
              const done = c.completed >= c.queued && c.queued > 0;
              return (
                <div key={c.id}>
                  <button
                    className="w-full px-5 py-3 flex items-center justify-between text-sm hover:bg-slate-50"
                    onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                  >
                    <div className="text-left">
                      <div className="font-medium text-slate-800">
                        {c.total} number(s) · {c.queued} queued
                      </div>
                      <div className="text-xs text-slate-400">{c.created_at}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`badge ${done ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>
                        {done ? "completed" : `${c.completed}/${c.queued} done`}
                      </span>
                      <span className="text-slate-400">{expanded === c.id ? "▲" : "▼"}</span>
                    </div>
                  </button>
                  {expanded === c.id && (
                    <div className="px-5 pb-4">
                      <table className="w-full text-sm border-t border-slate-100">
                        <tbody className="divide-y divide-slate-100">
                          {(c.results || []).map((r, i) => (
                            <tr key={i}>
                              <td className="py-2 font-mono text-xs">{r.to}</td>
                              <td className="py-2 text-right">
                                {r.sid ? (
                                  <span className="badge bg-slate-100 text-slate-600">queued</span>
                                ) : (
                                  <span className="badge bg-red-100 text-red-700">{r.error}</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
