"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function onSubmit(e) {
    e.preventDefault();
    const res = login(username.trim(), password);
    if (res.ok) router.replace("/dashboard");
    else setError(res.error);
  }

  return (
    <div className="min-h-screen grid place-items-center bg-gradient-to-br from-indigo-600 to-violet-700 p-4">
      <div className="w-full max-w-md card p-8">
        <div className="text-center mb-6">
          <div className="mx-auto mb-3 h-12 w-12 grid place-items-center rounded-xl bg-brand text-white text-xl font-bold">
            D
          </div>
          <h1 className="text-xl font-bold text-slate-900">Darshan University</h1>
          <p className="text-sm text-slate-500">AI Voice Counsellor — Admin Console</p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="label">Username</label>
            <input
              className="input"
              placeholder="admin"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              className="input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>
          )}
          <button type="submit" className="btn-primary w-full">
            Sign in
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-slate-400">
          Demo login — <span className="font-medium text-slate-500">admin / darshan123</span>
        </p>
      </div>
    </div>
  );
}
