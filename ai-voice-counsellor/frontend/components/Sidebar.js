"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "@/lib/auth";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/dial", label: "Dial Up", icon: "📞" },
  { href: "/leads", label: "Leads", icon: "🧑‍🎓" },
  { href: "/campaign", label: "Campaign", icon: "📣" },
  { href: "/analytics", label: "Analytics", icon: "📈" },
  { href: "/call-logs", label: "Call Logs", icon: "🗂️" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <aside className="w-60 shrink-0 bg-slate-900 text-slate-300 flex flex-col min-h-screen sticky top-0">
      <div className="px-5 py-5 flex items-center gap-3 border-b border-white/10">
        <div className="h-9 w-9 grid place-items-center rounded-lg bg-brand text-white font-bold">
          D
        </div>
        <div>
          <div className="text-white font-semibold leading-tight">Darshan</div>
          <div className="text-[11px] text-slate-400">Voice Counsellor</div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                active
                  ? "bg-brand text-white"
                  : "hover:bg-white/5 hover:text-white"
              }`}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-3 py-4 border-t border-white/10">
        <button
          onClick={() => {
            logout();
            router.replace("/login");
          }}
          className="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm hover:bg-white/5 hover:text-white"
        >
          <span>🚪</span> Sign out
        </button>
      </div>
    </aside>
  );
}
