"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";
import { Sidebar } from "@/components/layout/Sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { token } = useAuthStore();

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (!token) {
      router.push("/login");
    }
  }, [token, router]);

  if (!mounted || !token) return null;

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
