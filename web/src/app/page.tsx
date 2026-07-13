import { Suspense } from "react";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";

export default function Home() {
  return (
    <Suspense fallback={<DashboardLoading />}>
      <DashboardShell />
    </Suspense>
  );
}

function DashboardLoading() {
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 text-slate-950">
      <p className="text-sm text-muted-foreground">AirScopeを読み込んでいます…</p>
    </main>
  );
}
