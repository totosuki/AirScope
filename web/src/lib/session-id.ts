import { DEFAULT_SESSION_ID } from "./api/client";

type SearchParamsLike = {
  get(name: string): string | null;
};

export function resolveSessionId(
  searchParams: SearchParamsLike,
  fallback = process.env.NEXT_PUBLIC_AIRSCOPE_SESSION_ID ?? DEFAULT_SESSION_ID,
): string {
  const querySessionId = searchParams.get("session_id")?.trim();
  return querySessionId || fallback;
}
