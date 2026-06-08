"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

export default function LeadsPage() {
  const [leads, setLeads] = useState([]);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const data = await api.leads();
      setLeads((data.leads || []).slice().reverse());
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

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return leads;
    return leads.filter((r) =>
      [r.name, r.qualification, r.marks, r.student_number, (r.suggested_programs || []).join(" ")]
        .join(" ")
        .toLowerCase()
        .includes(s)
    );
  }, [leads, q]);

  function exportCsv() {
    const head = ["Name", "Qualification", "Marks", "Suggested Programs", "Number", "Status", "Updated"];
    const rows = filtered.map((r) => [
      r.name, r.qualification, r.marks,
      (r.suggested_programs || []).join("; "),
      r.student_number, r.completed ? "completed" : r.stage,
      r.updated_at,
    ]);
    const csv = [head, ...rows]
      .map((row) => row.map((c) => `"${(c ?? "").toString().replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "darshan-leads.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Leads</h1>
          <p className="text-sm text-slate-500">{filtered.length} of {leads.length} students</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            className="input w-64"
            placeholder="Search name, qualification, number…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <button className="btn-ghost" onClick={exportCsv}>⬇ CSV</button>
        </div>
      </div>

      {err && (
        <div className="card p-4 text-sm text-red-600 bg-red-50 border-red-200">{err}</div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-left">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Qualification</th>
              <th className="px-4 py-3 font-medium">Marks</th>
              <th className="px-4 py-3 font-medium">Suggested Programs</th>
              <th className="px-4 py-3 font-medium">Number</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Loading…</td></tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">No leads yet.</td></tr>
            )}
            {filtered.map((r) => (
              <tr key={r.call_sid} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-800">{r.name || "—"}</td>
                <td className="px-4 py-3">{r.qualification || "—"}</td>
                <td className="px-4 py-3">{r.marks || "—"}</td>
                <td className="px-4 py-3 max-w-xs">
                  <div className="flex flex-wrap gap-1">
                    {(r.suggested_programs || []).map((p) => (
                      <span key={p} className="badge bg-indigo-50 text-indigo-700">{p}</span>
                    ))}
                    {(!r.suggested_programs || r.suggested_programs.length === 0) && "—"}
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs">{r.student_number || "—"}</td>
                <td className="px-4 py-3">
                  <span className={`badge ${r.completed ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>
                    {r.completed ? "completed" : r.stage || "—"}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">{r.updated_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
