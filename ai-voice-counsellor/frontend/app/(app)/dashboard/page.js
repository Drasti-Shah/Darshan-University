"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

function Stat({ label, value, sub, icon }) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-500">{label}</span>
        <span className="text-xl">{icon}</span>
      </div>
      <div className="mt-2 text-3xl font-bold text-slate-900">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [leads, setLeads] = useState([]);
  const [online, setOnline] = useState(null);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const [s, l] = await Promise.all([api.stats(), api.leads()]);
      setStats(s);
      setLeads((l.leads || []).slice().reverse());
      setOnline(true);
      setErr("");
    } catch (e) {
      setOnline(false);
      setErr(e.message);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500">Overview of your AI counselling calls</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              online ? "bg-green-500" : online === false ? "bg-red-500" : "bg-slate-300"
            }`}
          />
          <span className="text-slate-500">
            Backend {online ? "online" : online === false ? "offline" : "…"}
          </span>
        </div>
      </div>

      {err && (
        <div className="card p-4 text-sm text-red-600 bg-red-50 border-red-200">
          Could not reach the backend at <code>{api.base}</code> — {err}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Total Calls" value={stats?.total_calls ?? "—"} icon="📞" />
        <Stat
          label="Completed"
          value={stats?.completed_calls ?? "—"}
          icon="✅"
          sub={stats ? `${stats.total_calls} dialled` : ""}
        />
        <Stat
          label="Leads Captured"
          value={stats?.leads_captured ?? "—"}
          icon="🧑‍🎓"
          sub={stats ? `${stats.conversion_pct}% conversion` : ""}
        />
        <Stat
          label="Avg Call Time"
          value={stats ? `${stats.avg_duration_sec}s` : "—"}
          icon="⏱️"
        />
      </div>

      <div className="card">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-800">Recent calls</h2>
          <Link href="/call-logs" className="text-sm text-brand hover:underline">
            View all →
          </Link>
        </div>
        <div className="divide-y divide-slate-100">
          {leads.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-slate-400">
              No calls yet. Place one from the Dial Up page.
            </div>
          )}
          {leads.slice(0, 6).map((r) => (
            <div key={r.call_sid} className="px-5 py-3 flex items-center justify-between text-sm">
              <div>
                <div className="font-medium text-slate-800">{r.name || "Unknown caller"}</div>
                <div className="text-slate-400">
                  {r.qualification || "—"} {r.marks ? `· ${r.marks}` : ""}
                </div>
              </div>
              <div className="text-right">
                <span
                  className={`badge ${
                    r.completed ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {r.completed ? "completed" : r.stage || "in progress"}
                </span>
                <div className="text-xs text-slate-400 mt-1">{r.updated_at}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
