import { sampleProjects } from "@/data/sample-business-data";
import { apiRequest } from "@/lib/api/client";
import { FIXTURE_DATA_ENABLED } from "@/lib/api/config";
import { endpoints } from "@/lib/api/endpoints";
import { readFixtureState } from "@/lib/api/fixture-store";
import { normalizeEvent, normalizeEvents, normalizePrize, normalizeProjects, normalizeTeam, normalizeTrack } from "@/lib/api/normalizers";
import type { EventRecord, Prize, ProjectRecord, TeamRecord, Track } from "@/types/portal";

function fixture(token: string): boolean {
  if (!FIXTURE_DATA_ENABLED) return false;
  if (!token) throw new Error("A real authenticated account is required before synthetic data can be used.");
  return true;
}

export async function getAllProjects(token: string): Promise<ProjectRecord[]> {
  if (fixture(token)) return readFixtureState().projects.length ? readFixtureState().projects : sampleProjects;
  return normalizeProjects(await apiRequest<unknown>(endpoints.projects.list, { token }));
}

export async function getAllTeams(token: string, eventId?: string): Promise<TeamRecord[]> {
  if (fixture(token)) {
    const team = readFixtureState().team;
    return team ? [team] : [];
  }
  const query = eventId ? `?event_id=${encodeURIComponent(eventId)}` : "";
  return (await import("@/lib/api/normalizers")).normalizeTeams(
    await apiRequest<unknown>(`${endpoints.teams.list}${query}`, { token }),
  );
}

export async function addEventTrack(token: string, eventId: string, name: string): Promise<Track> {
  if (fixture(token)) return { id: `sample-track-${Date.now()}`, name };
  return normalizeTrack(await apiRequest<unknown>(endpoints.events.tracks(eventId), {
    method: "POST", token, body: JSON.stringify({ name }),
  }));
}

export async function updateEventTrack(token: string, trackId: string, name: string): Promise<Track> {
  if (fixture(token)) return { id: trackId, name };
  return normalizeTrack(await apiRequest<unknown>(endpoints.events.trackDetail(trackId), {
    method: "PUT", token, body: JSON.stringify({ name }),
  }));
}

export async function deleteEventTrack(token: string, trackId: string): Promise<void> {
  if (fixture(token)) return;
  await apiRequest<void>(endpoints.events.trackDetail(trackId), { method: "DELETE", token });
}

export async function addEventPrize(token: string, eventId: string, prize: Omit<Prize, "id">): Promise<Prize> {
  if (fixture(token)) return { id: `sample-prize-${Date.now()}`, ...prize };
  return normalizePrize(await apiRequest<unknown>(endpoints.events.prizes(eventId), {
    method: "POST", token,
    body: JSON.stringify({ title: prize.title, description: prize.description || null, amount: prize.amount ?? null, rank: prize.rank ?? null }),
  }));
}

export async function updateEventPrize(token: string, prizeId: string, prize: Omit<Prize, "id">): Promise<Prize> {
  if (fixture(token)) return { id: prizeId, ...prize };
  return normalizePrize(await apiRequest<unknown>(endpoints.events.prizeDetail(prizeId), {
    method: "PUT", token,
    body: JSON.stringify({ title: prize.title, description: prize.description || null, amount: prize.amount ?? null, rank: prize.rank ?? null }),
  }));
}

export async function deleteEventPrize(token: string, prizeId: string): Promise<void> {
  if (fixture(token)) return;
  await apiRequest<void>(endpoints.events.prizeDetail(prizeId), { method: "DELETE", token });
}

export async function listEventRecords(token: string): Promise<EventRecord[]> {
  if (fixture(token)) return [normalizeEvent({
    id: "sample-event-2026",
    name: "Sample Hack 2026",
    description: "Synthetic development fixture",
    start_date: "2026-02-22T18:00:00Z",
    end_date: "2026-03-01T18:00:00Z",
    submission_deadline: "2026-03-01T18:00:00Z",
    status: "closed",
    tracks: [],
    prizes: [],
  })];
  return normalizeEvents(await apiRequest<unknown>(endpoints.events.list, { token }));
}
