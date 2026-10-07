import type {
  ChangeEvent,
  CheckedVenue,
  Evidence,
  Membership,
  OverlapResult,
  Participant,
  SearchResult,
  Snapshot,
  SourceHealth,
  Stats,
  Venue,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => get<{ stats: Stats; sources: SourceHealth[]; semantics: string }>("/meta"),
  stats: () => get<Stats>("/stats"),
  sources: () => get<SourceHealth[]>("/sources"),
  source: (id: string) => get<SourceHealth & { snapshots: Snapshot[] }>(`/sources/${id}`),
  snapshots: (source?: string) =>
    get<Snapshot[]>(`/snapshots${source ? `?source=${source}` : ""}`),
  venues: () => get<Venue[]>("/venues"),
  venue: (mic: string) => get<Venue>(`/venues/${mic}`),
  participants: (q?: string) =>
    get<Participant[]>(`/participants${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  participant: (id: string) => get<Participant>(`/participants/${encodeURIComponent(id)}`),
  memberships: (id: string) =>
    get<{ observed: Membership[]; checked: CheckedVenue[]; note: string }>(
      `/participants/${encodeURIComponent(id)}/memberships`,
    ),
  evidence: (id: string) =>
    get<Evidence[]>(`/participants/${encodeURIComponent(id)}/evidence`),
  overlap: (a: string, b: string) => get<OverlapResult>(`/overlap?a=${a}&b=${b}`),
  changes: (since?: string, includeBaseline?: boolean, includeIdentity?: boolean) =>
    get<ChangeEvent[]>(
      `/changes?since=${since ?? "1970-01-01"}` +
        `${includeBaseline ? "&include_baseline=true" : ""}` +
        `${includeIdentity ? "&include_identity=true" : ""}`,
    ),
  search: (q: string) => get<SearchResult>(`/search?q=${encodeURIComponent(q)}`),
};
