"use client";

import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Activity, Clock3, Gauge, ListFilter, MapPinned, Plane, Radio, RefreshCw, TriangleAlert } from "lucide-react";

import { AltitudeChart } from "./altitude-chart";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAirScopeData } from "@/hooks/use-airscope-data";
import type { Aircraft, Telemetry } from "@/lib/api/types";
import { formatDateTime, formatNumber, formatRelativeTime } from "@/lib/format";
import { resolveSessionId } from "@/lib/session-id";

const AircraftMap = dynamic(() => import("@/components/map/aircraft-map"), {
  ssr: false,
  loading: () => <Skeleton className="h-[420px] w-full rounded-none" />,
});
export function DashboardShell() {
  const searchParams = useSearchParams();
  const sessionId = resolveSessionId(searchParams);
  const data = useAirScopeData(sessionId);
  const aircraft = data.current?.aircraft ?? [];
  const [selectedIcao, setSelectedIcao] = useState<string | null>(null);
  const effectiveSelectedIcao = aircraft.some((item) => item.icao24 === selectedIcao)
    ? selectedIcao
    : aircraft[0]?.icao24 ?? null;
  const selected = aircraft.find((item) => item.icao24 === effectiveSelectedIcao) ?? null;
  const connectionState = data.error ? "更新停止" : data.isLoading ? "接続中" : "受信中";

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <header className="border-b border-slate-800 bg-slate-950 text-white">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-cyan-400 text-slate-950"><Radio className="size-5" /></span><div><p className="text-xs font-semibold tracking-[0.28em] text-cyan-300">ADS-B RECEIVER</p><h1 className="text-xl font-semibold">AirScope</h1></div></div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge variant="outline" className="border-slate-700 bg-slate-900 text-slate-200">session: {sessionId}</Badge>
            <Badge className={data.error ? "bg-amber-500 text-slate-950" : "bg-emerald-500 text-slate-950"}><span className="mr-1.5 size-1.5 rounded-full bg-current" />{connectionState}</Badge>
            <Tooltip><TooltipTrigger render={<Button size="icon" variant="outline" className="border-slate-700 bg-slate-900 hover:bg-slate-800" onClick={() => void data.refresh()} disabled={data.isRefreshing} aria-label="データを更新" />}><RefreshCw className={`size-4 ${data.isRefreshing ? "animate-spin" : ""}`} /></TooltipTrigger><TooltipContent>今すぐ更新</TooltipContent></Tooltip>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1600px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {data.error && <Alert className="border-amber-300 bg-amber-50 text-amber-950"><TriangleAlert className="size-4" /><AlertTitle>APIからの更新が停止しています</AlertTitle><AlertDescription className="flex flex-wrap items-center justify-between gap-3"><span>{data.error} 取得済みデータはそのまま表示しています（連続失敗: {data.failureCount}回）。</span><Button size="sm" variant="outline" onClick={() => void data.refresh()}>再試行</Button></AlertDescription></Alert>}

        <section aria-label="受信状況" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryCard icon={<Plane />} label="表示中の機体" value={data.isLoading ? null : `${aircraft.length} 機`} detail="1日以内の最新状態" />
          <SummaryCard icon={<Activity />} label="API ステータス" value={data.isLoading ? null : connectionState} detail={data.error ? "自動的に再接続します" : "3秒ごとに更新"} />
          <SummaryCard icon={<Clock3 />} label="API 生成時刻" value={data.isLoading ? null : formatDateTime(data.current?.generated_at ?? null)} detail="日本標準時（JST）" />
          <SummaryCard icon={<Gauge />} label="ブラウザ更新" value={data.isLoading ? null : data.lastSucceededAt?.toLocaleTimeString("ja-JP") ?? "—"} detail="最後に取得成功した時刻" />
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Card className="overflow-hidden border-slate-200 shadow-sm">
            <CardHeader className="flex-row items-center justify-between border-b py-4"><div><CardTitle className="flex items-center gap-2 text-base"><MapPinned className="size-4 text-cyan-600" />リアルタイム航空機地図</CardTitle><CardDescription>機影を選択すると詳細を確認できます</CardDescription></div><Sheet><SheetTrigger render={<Button variant="outline" size="sm" className="xl:hidden" />}><ListFilter className="size-4" />機体一覧</SheetTrigger><SheetContent className="w-[90vw] overflow-y-auto sm:max-w-md"><SheetHeader><SheetTitle>受信機体</SheetTitle><SheetDescription>{aircraft.length}機を表示中</SheetDescription></SheetHeader><div className="space-y-4 p-4"><AircraftList aircraft={aircraft} selectedIcao={effectiveSelectedIcao} onSelect={setSelectedIcao} /><AircraftDetails aircraft={selected} /></div></SheetContent></Sheet></CardHeader>
            <CardContent className="p-0">{data.isLoading ? <Skeleton className="h-[520px] rounded-none" /> : aircraft.length === 0 ? <EmptyState /> : <AircraftMap aircraft={aircraft} selectedIcao={effectiveSelectedIcao} onSelect={setSelectedIcao} />}</CardContent>
          </Card>
          <div className="hidden space-y-6 xl:block"><Card className="border-slate-200 shadow-sm"><CardHeader><CardTitle className="text-base">受信機体</CardTitle><CardDescription>最新観測順・{aircraft.length}機</CardDescription></CardHeader><CardContent className="max-h-[280px] overflow-y-auto"><AircraftList aircraft={aircraft} selectedIcao={effectiveSelectedIcao} onSelect={setSelectedIcao} /></CardContent></Card><AircraftDetails aircraft={selected} /></div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
          <TelemetryCard telemetry={data.recent?.telemetry ?? []} loading={data.isLoading} />
          <Card className="border-slate-200 shadow-sm"><CardHeader><CardTitle className="text-base">高度帯サマリー</CardTitle><CardDescription>現在表示している機体の分布</CardDescription></CardHeader><CardContent>{data.isLoading ? <Skeleton className="h-56" /> : aircraft.length ? <AltitudeChart aircraft={aircraft} /> : <p className="py-20 text-center text-sm text-muted-foreground">集計対象の機体がありません</p>}</CardContent></Card>
        </section>

        <footer className="rounded-xl border border-slate-200 bg-white p-5 text-sm leading-6 text-slate-600"><p className="font-medium text-slate-900">データ利用について</p><p>本画面は公開ブロードキャストであるADS-B信号の受信結果を、学習・実験目的で可視化しています。個人追跡や運航安全に関わる判断には使用できません。</p></footer>
      </div>
    </main>
  );
}

function SummaryCard({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string | null; detail: string }) {
  return <Card className="border-slate-200 shadow-sm"><CardContent className="flex items-start gap-4 p-5"><span className="grid size-10 shrink-0 place-items-center rounded-lg bg-cyan-50 text-cyan-700 [&_svg]:size-5">{icon}</span><div className="min-w-0"><p className="text-sm text-muted-foreground">{label}</p>{value === null ? <Skeleton className="my-2 h-7 w-28" /> : <p className="truncate text-xl font-semibold tabular-nums">{value}</p>}<p className="text-xs text-muted-foreground">{detail}</p></div></CardContent></Card>;
}

function AircraftList({ aircraft, selectedIcao, onSelect }: { aircraft: Aircraft[]; selectedIcao: string | null; onSelect: (icao: string) => void }) {
  if (!aircraft.length) return <p className="py-8 text-center text-sm text-muted-foreground">表示できる機体がありません</p>;
  return <div className="space-y-2">{aircraft.map((item) => <button type="button" key={item.icao24} onClick={() => onSelect(item.icao24)} className={`w-full rounded-lg border p-3 text-left transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 ${selectedIcao === item.icao24 ? "border-cyan-500 bg-cyan-50" : "border-slate-200 hover:bg-slate-50"}`}><span className="flex items-center justify-between gap-2"><strong className="truncate text-sm">{item.callsign ?? "コールサイン不明"}</strong><Badge variant={item.status === "current" ? "default" : "secondary"}>{item.status}</Badge></span><span className="mt-1 flex justify-between text-xs text-muted-foreground"><span className="font-mono uppercase">{item.icao24}</span><span>{formatNumber(item.altitude_ft, " ft")}</span></span></button>)}</div>;
}

function AircraftDetails({ aircraft }: { aircraft: Aircraft | null }) {
  return <Card className="border-slate-200 shadow-sm"><CardHeader><CardTitle className="text-base">機体詳細</CardTitle><CardDescription>{aircraft ? `${aircraft.callsign ?? "コールサイン不明"} / ${aircraft.icao24}` : "地図または一覧から機体を選択"}</CardDescription></CardHeader>{aircraft && <CardContent className="space-y-3 text-sm"><DetailRow label="位置" value={`${aircraft.lat.toFixed(4)}, ${aircraft.lon.toFixed(4)}`} /><DetailRow label="高度" value={formatNumber(aircraft.altitude_ft, " ft")} /><DetailRow label="対地速度" value={formatNumber(aircraft.ground_speed_kt, " kt")} /><DetailRow label="進行方向" value={formatNumber(aircraft.track_deg, "°")} /><DetailRow label="垂直速度" value={formatNumber(aircraft.vertical_rate_fpm, " ft/min")} /><DetailRow label="Squawk" value={aircraft.squawk ?? "—"} /><DetailRow label="受信距離" value={formatNumber(aircraft.distance_km, " km")} /><Separator /><DetailRow label="最終観測" value={`${formatRelativeTime(aircraft.freshness_at)} (${formatDateTime(aircraft.freshness_at)})`} /></CardContent>}</Card>;
}
function DetailRow({ label, value }: { label: string; value: string }) { return <div className="flex items-start justify-between gap-4"><span className="text-muted-foreground">{label}</span><span className="text-right font-medium tabular-nums">{value}</span></div>; }
function EmptyState() { return <div className="grid min-h-[420px] place-items-center p-8 text-center"><div><Plane className="mx-auto mb-4 size-10 text-slate-300" /><h2 className="font-semibold">表示できる機体がありません</h2><p className="mt-2 max-w-md text-sm text-muted-foreground">session_id とデータの観測時刻を確認してください。現在は1日以内の機体を表示対象としています。</p></div></div>; }

function TelemetryCard({ telemetry, loading }: { telemetry: Telemetry[]; loading: boolean }) {
  return <Card className="min-w-0 border-slate-200 shadow-sm"><CardHeader><CardTitle className="text-base">最新テレメトリ</CardTitle><CardDescription>直近{telemetry.length}件の受信履歴</CardDescription></CardHeader><CardContent>{loading ? <div className="space-y-2">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-10" />)}</div> : telemetry.length === 0 ? <p className="py-16 text-center text-sm text-muted-foreground">受信履歴がありません</p> : <div className="max-h-[420px] overflow-auto"><Table><TableHeader className="sticky top-0 bg-white"><TableRow><TableHead>時刻</TableHead><TableHead>Callsign / ICAO</TableHead><TableHead className="text-right">高度</TableHead><TableHead className="text-right">速度</TableHead><TableHead>受信局</TableHead></TableRow></TableHeader><TableBody>{telemetry.map((item) => <TableRow key={item.id}><TableCell className="whitespace-nowrap tabular-nums">{formatDateTime(item.ingested_at)}</TableCell><TableCell><span className="block font-medium">{item.telemetry.callsign ?? "—"}</span><span className="font-mono text-xs uppercase text-muted-foreground">{item.telemetry.icao24}</span></TableCell><TableCell className="text-right tabular-nums">{formatNumber(item.telemetry.altitude_ft, " ft")}</TableCell><TableCell className="text-right tabular-nums">{formatNumber(item.telemetry.ground_speed_kt, " kt")}</TableCell><TableCell>{item.telemetry.receiver_id ?? "—"}</TableCell></TableRow>)}</TableBody></Table></div>}</CardContent></Card>;
}
