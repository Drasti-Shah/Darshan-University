"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { getSession, isAuthed } from "@/lib/auth";

export default function AppLayout({ children }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isAuthed()) router.replace("/login");
    else setReady(true);
  }, [router]);

  if (!ready) {
    return <div className="min-h-screen grid place-items-center text-slate-400">Loading…</div>;
  }

  const user = getSession()?.user || "admin";

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <header className="h-14 bg-white border-b border-slate-200 px-6 flex items-center justify-between sticky top-0 z-10">
          <div className="text-sm text-slate-500">AI Admission Counsellor</div>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-500">Signed in as</span>
            <span className="font-medium text-slate-800">{user}</span>
            <div className="h-8 w-8 grid place-items-center rounded-full bg-brand/10 text-brand font-semibold uppercase">
              {user[0]}
            </div>
          </div>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
