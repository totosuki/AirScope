"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getCurrentAircraft, getRecentTelemetry } from "@/lib/api/client";
import type { CurrentAircraftResponse, RecentTelemetryResponse } from "@/lib/api/types";

const ACTIVE_INTERVAL_MS = 3_000;
const HIDDEN_INTERVAL_MS = 30_000;
const MAX_INTERVAL_MS = 30_000;

type AirScopeDataState = {
  current: CurrentAircraftResponse | null;
  recent: RecentTelemetryResponse | null;
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  failureCount: number;
  lastSucceededAt: Date | null;
};

export function useAirScopeData(sessionId: string) {
  const [state, setState] = useState<AirScopeDataState>({
    current: null,
    recent: null,
    isLoading: true,
    isRefreshing: false,
    error: null,
    failureCount: 0,
    lastSucceededAt: null,
  });
  const controllerRef = useRef<AbortController | null>(null);
  const inFlightRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const failureCountRef = useRef(0);

  const load = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState((previous) => ({ ...previous, isRefreshing: previous.current !== null }));

    try {
      const [current, recent] = await Promise.all([
        getCurrentAircraft(sessionId, controller.signal),
        getRecentTelemetry(sessionId, 50, controller.signal),
      ]);
      failureCountRef.current = 0;
      setState({
        current,
        recent,
        isLoading: false,
        isRefreshing: false,
        error: null,
        failureCount: 0,
        lastSucceededAt: new Date(),
      });
    } catch (error) {
      if (controller.signal.aborted) return;
      failureCountRef.current += 1;
      setState((previous) => ({
        ...previous,
        isLoading: false,
        isRefreshing: false,
        error: error instanceof Error ? error.message : "データを取得できませんでした。",
        failureCount: failureCountRef.current,
      }));
    } finally {
      inFlightRef.current = false;
    }
  }, [sessionId]);

  useEffect(() => {
    let disposed = false;

    const schedule = () => {
      if (disposed) return;
      const failureDelay = ACTIVE_INTERVAL_MS * 2 ** Math.min(failureCountRef.current, 3);
      const delay = document.hidden
        ? HIDDEN_INTERVAL_MS
        : Math.min(MAX_INTERVAL_MS, failureDelay);
      timerRef.current = setTimeout(async () => {
        await load();
        schedule();
      }, delay);
    };

    void load().finally(schedule);
    const handleVisibility = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (!document.hidden) void load().finally(schedule);
      else schedule();
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      disposed = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      controllerRef.current?.abort();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [load]);

  return { ...state, refresh: load };
}
