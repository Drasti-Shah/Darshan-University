"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isAuthed } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(isAuthed() ? "/dashboard" : "/login");
  }, [router]);
  return (
    <div className="min-h-screen grid place-items-center text-slate-400">
      Loading…
    </div>
  );
}
