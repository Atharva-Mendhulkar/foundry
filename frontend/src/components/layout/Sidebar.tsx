"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Bot, Network, FileUp, Clock, AlertTriangle, LogOut } from "lucide-react";
import { useAuthStore } from "@/stores/auth";

const navItems = [
  { name: "Copilot", href: "/dashboard/copilot", icon: Bot },
  { name: "Knowledge Graph", href: "/dashboard/graph", icon: Network },
  { name: "Ingestion", href: "/dashboard/ingest", icon: FileUp },
  { name: "Shift Handover", href: "/dashboard/shift", icon: Clock },
  { name: "Risk Heatmap", href: "/dashboard/risk", icon: AlertTriangle },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  return (
    <div className="flex h-screen w-64 flex-col border-r bg-zinc-950 px-4 py-6">
      <div className="mb-8 flex items-center px-2">
        <h1 className="text-xl font-bold tracking-tight">FOUNDRY</h1>
      </div>
      <nav className="flex-1 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-zinc-800 text-zinc-50" : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-50"
              )}
            >
              <Icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto border-t pt-4">
        <div className="mb-4 px-2">
          <p className="text-sm font-medium text-zinc-200">{user?.username}</p>
          <p className="text-xs text-zinc-500 capitalize">{user?.role}</p>
        </div>
        <button
          onClick={() => logout()}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-zinc-400 transition-colors hover:bg-zinc-800/50 hover:text-red-400"
        >
          <LogOut className="h-5 w-5" />
          Logout
        </button>
      </div>
    </div>
  );
}
