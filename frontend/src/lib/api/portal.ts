import galleryFixture from "@/data/project-fixtures.json";
import {
  sampleAssignments,
  sampleEvent,
  sampleJudges,
  sampleProgress,
  sampleResults,
  sampleRubric,
  sampleTeam,
} from "@/data/sample-business-data";
import { apiRequest } from "@/lib/api/client";
import { FIXTURE_DATA_ENABLED } from "@/lib/api/config";
import { endpoints } from "@/lib/api/endpoints";
import { readFixtureState, saveFixtureProject, saveFixtureTeam } from "@/lib/api/fixture-store";
import {
  asList,
  normalizeAssignments,
  normalizeEvent,
  normalizeEvents,
  normalizeIntegrity,
  normalizeJudges,
  normalizeNormalization,
  normalizeProject,
  normalizeProjects,
  normalizeProgress,
  normalizeResults,
  normalizeRubric,
  normalizeTeam,
  normalizeTeams,
} from "@/lib/api/normalizers";
import type {
  AssignmentRecord,
  EventRecord,
  JudgeRecord,
  ProjectRecord,
  ResultRecord,
  ResultsBundle,
  ReviewProgress,
  RubricCriterion,
  TeamRecord,
} from "@/types/portal";

function fixtureSession(token?: string | null): boolean {
  if (!FIXTURE_DATA_ENABLED) return false;
  if (!token) throw new Error("Synthetic business fixtures are available only after a real JudgeForge login.");
  return true;
}

export const DOGFOOD_EVENT: EventRecord = {
  id: "dogfood-2026",
  name: "DOGFOOD 2026",
  description: "Build the platform that will judge you. A 72-hour hackathon to build an open, self-hostable submission and judging platform.",
  startDate: "2026-09-26T18:00:00Z",
  endDate: "2026-09-29T18:00:00Z",
  submissionDeadline: "2026-09-29T18:00:00Z",
  status: "open",
  tracks: [],
  prizes: [],
};


export function chooseDefaultEvent(events: EventRecord[]): EventRecord | undefined {
  return (
    events.find((event) => event.status === "open")
    ?? events.find((event) => event.status === "upcoming")
    ?? events[0]
  );
}

export async function getEvents(): Promise<EventRecord[]> {
  if (FIXTURE_DATA_ENABLED) return [sampleEvent];
  return normalizeEvents(await apiRequest<unknown>(endpoints.events.list));
}

export async function getEvent(id: string, token?: string | null): Promise<EventRecord> {
  if (fixtureSession(token)) return sampleEvent;
  return normalizeEvent(await apiRequest<unknown>(endpoints.events.detail(id), { token }));
}

export async function getPublicProjects(): Promise<ProjectRecord[]> {
  if (FIXTURE_DATA_ENABLED) return galleryFixture.map((item) => normalizeProject(item));
  return normalizeProjects(await apiRequest<unknown>(endpoints.projects.list));
}

export async function getMyProjects(token: string): Promise<ProjectRecord[]> {
  if (fixtureSession(token)) return readFixtureState().projects;
  return normalizeProjects(await apiRequest<unknown>(endpoints.projects.mine, { token }));
}

export async function getProject(id: string, token?: string | null, _publicAccess = false): Promise<ProjectRecord> {
  if (FIXTURE_DATA_ENABLED) {
    if (!token) {
      const item = galleryFixture.find((project) => project.id === id);
      if (!item) throw new Error("Sample project not found.");
      return normalizeProject(item);
    }
    const found = readFixtureState().projects.find((project) => project.id === id);
    if (!found) throw new Error("Sample project not found.");
    return found;
  }
  return normalizeProject(await apiRequest<unknown>(endpoints.projects.detail(id), { token }));
}

export async function getMyTeam(token: string): Promise<TeamRecord | null> {
  if (fixtureSession(token)) return readFixtureState().team;
  const payload = await apiRequest<unknown>(endpoints.teams.mine, { token });
  return normalizeTeams(payload)[0] ?? null;
}

export async function createTeam(token: string, payload: { name: string; event_id: string | number }): Promise<TeamRecord> {
  if (fixtureSession(token)) return saveFixtureTeam({ ...sampleTeam, name: payload.name });
  return normalizeTeam(await apiRequest<unknown>(endpoints.teams.create, {
    method: "POST",
    token,
    body: JSON.stringify({ name: payload.name.trim(), event_id: Number(payload.event_id) }),
  }));
}

export async function joinTeam(token: string, inviteToken: string): Promise<TeamRecord> {
  if (fixtureSession(token)) return saveFixtureTeam({ ...sampleTeam, inviteUrl: undefined });
  const response = await apiRequest<{ team_id: number }>(endpoints.teams.join, {
    method: "POST",
    token,
    body: JSON.stringify({ token: inviteToken.trim() }),
  });
  return normalizeTeam(await apiRequest<unknown>(endpoints.teams.detail(response.team_id), { token }));
}

interface SaveProjectPayload {
  id?: string;
  title: string;
  description: string;
  track_id: string;
  repo_url: string;
  demo_url: string;
}

export async function saveProject(token: string, payload: SaveProjectPayload): Promise<ProjectRecord> {
  if (fixtureSession(token)) {
    const existing = payload.id ? readFixtureState().projects.find((item) => item.id === payload.id) : undefined;
    return saveFixtureProject({
      id: payload.id ?? `sample-project-${Date.now()}`,
      title: payload.title,
      summary: payload.description,
      description: payload.description,
      track: payload.track_id || "Unassigned",
      team: readFixtureState().team?.name ?? "No team",
      teamSize: readFixtureState().team?.members.length ?? 0,
      repositoryUrl: payload.repo_url,
      demoUrl: payload.demo_url,
      submittedAt: existing?.submittedAt ?? "",
      status: existing?.status === "submitted" ? "submitted" : "draft",
    });
  }

  const trackId = Number(payload.track_id);
  if (!Number.isInteger(trackId) || trackId <= 0) {
    throw new Error("Select a valid event track before saving the project.");
  }

  const common = {
    title: payload.title.trim(),
    summary: payload.description.trim(),
    track_id: trackId,
    repo_url: payload.repo_url.trim() || null,
    demo_url: payload.demo_url.trim() || null,
  };

  if (payload.id) {
    return normalizeProject(await apiRequest<unknown>(endpoints.projects.update(payload.id), {
      method: "PUT",
      token,
      body: JSON.stringify(common),
    }));
  }

  const [events, team] = await Promise.all([getEvents(), getMyTeam(token)]);
  const event = chooseDefaultEvent(events);
  if (!event) throw new Error("No event is configured for project creation.");
  if (!team) throw new Error("Create or join a team before creating a project.");

  return normalizeProject(await apiRequest<unknown>(endpoints.projects.create, {
    method: "POST",
    token,
    body: JSON.stringify({
      ...common,
      event_id: Number(event.id),
      team_id: Number(team.id),
    }),
  }));
}

export async function submitProject(token: string, id: string): Promise<ProjectRecord> {
  if (fixtureSession(token)) {
    const project = readFixtureState().projects.find((item) => item.id === id);
    if (!project) throw new Error("Sample project not found.");
    return saveFixtureProject({ ...project, status: "submitted" });
  }
  return normalizeProject(await apiRequest<unknown>(endpoints.projects.submit(id), { method: "POST", token }));
}

export async function getJudges(token: string): Promise<JudgeRecord[]> {
  if (fixtureSession(token)) return sampleJudges;
  return normalizeJudges(await apiRequest<unknown>(endpoints.judges.list, { token }));
}

export async function inviteJudge(token: string, email: string, _eventId?: string): Promise<unknown> {
  if (fixtureSession(token)) return { invited: true, email };
  return apiRequest<unknown>(endpoints.judges.invite, {
    method: "POST",
    token,
    body: JSON.stringify({ email: email.trim() }),
  });
}

export async function getAssignments(token: string): Promise<AssignmentRecord[]> {
  if (fixtureSession(token)) return sampleAssignments;
  return normalizeAssignments(await apiRequest<unknown>(endpoints.judges.assignments, { token }));
}

export async function assignJudges(
  token: string,
  payload: { judge_id?: string; judge_ids?: string[]; project_ids: string[]; strategy?: "round_robin" | "all" },
): Promise<unknown> {
  if (fixtureSession(token)) return { assigned: payload.project_ids.length };
  const judgeIds = payload.judge_ids?.length ? payload.judge_ids : payload.judge_id ? [payload.judge_id] : [];
  if (!judgeIds.length) throw new Error("Choose at least one judge.");
  return apiRequest<unknown>(endpoints.judges.assign, {
    method: "POST",
    token,
    body: JSON.stringify({
      judge_ids: judgeIds.map(Number),
      project_ids: payload.project_ids.map(Number),
      strategy: payload.strategy ?? "all",
    }),
  });
}

export async function getRubric(token: string, id?: string, eventId?: string): Promise<RubricCriterion[]> {
  if (fixtureSession(token)) return sampleRubric;

  if (id) {
    return normalizeRubric(await apiRequest<unknown>(endpoints.judging.rubricDetail(id), { token }));
  }
  if (!eventId) throw new Error("An event ID is required to resolve the active rubric.");
  return normalizeRubric(await apiRequest<unknown>(endpoints.judging.activeRubric(eventId), { token }));
}

export async function saveRubric(token: string, criteria: RubricCriterion[], id?: string, eventId?: string): Promise<RubricCriterion[]> {
  if (fixtureSession(token)) return criteria;
  if (!eventId && !id) throw new Error("An event is required to save a rubric.");

  let rubricId = id;
  let rubricName = "Judging Rubric";

  if (rubricId) {
    const existing = await apiRequest<Record<string, unknown>>(endpoints.judging.rubricDetail(rubricId), { token });
    if (typeof existing.name === "string" && existing.name.trim()) rubricName = existing.name;
  } else if (eventId) {
    try {
      const active = await apiRequest<Record<string, unknown>>(endpoints.judging.activeRubric(eventId), { token });
      rubricId = typeof active.id === "number" || typeof active.id === "string" ? String(active.id) : undefined;
      if (typeof active.name === "string" && active.name.trim()) rubricName = active.name;
    } catch {
      rubricId = undefined;
    }
  }

  const body = JSON.stringify({
    ...(eventId ? { event_id: Number(eventId) } : {}),
    name: rubricName,
    criteria: criteria.map(({ name, weight, maxScore }) => ({ name: name.trim(), weight: Number(weight), max_score: Number(maxScore) })),
  });

  const raw = await apiRequest<unknown>(
    rubricId ? endpoints.judging.rubricDetail(rubricId) : endpoints.judging.rubric,
    { method: rubricId ? "PUT" : "POST", token, body },
  );
  return normalizeRubric(raw);
}

export async function submitScores(
  token: string,
  projectId: string,
  scores: Array<{ criterion_id: string; score: number; comment: string }>,
): Promise<unknown> {
  if (fixtureSession(token)) return { submitted: true };
  return apiRequest<unknown>(endpoints.judging.scores, {
    method: "POST",
    token,
    body: JSON.stringify({
      project_id: Number(projectId),
      scores: scores.map((item) => ({
        criterion_id: Number(item.criterion_id),
        score: Number(item.score),
        comment: item.comment.trim() || null,
      })),
    }),
  });
}

export async function getProgress(token: string): Promise<ReviewProgress> {
  if (fixtureSession(token)) return sampleProgress;
  const [rawProgress, assignments] = await Promise.all([
    apiRequest<unknown>(endpoints.judging.progress, { token }),
    getAssignments(token),
  ]);
  const normalized = normalizeProgress(rawProgress);
  const uniqueProjects = new Set(assignments.map((item) => item.project.id));
  const completedProjects = new Set(assignments.filter((item) => item.status === "completed").map((item) => item.project.id));
  return {
    ...normalized,
    assignedProjects: uniqueProjects.size,
    completedProjects: completedProjects.size,
  };
}

export async function getOrganizerAssignments(token: string): Promise<AssignmentRecord[]> {
  return getAssignments(token);
}

export async function getResultsBundle(token: string, eventId?: string): Promise<ResultsBundle> {
  if (fixtureSession(token)) {
    return {
      eventId: sampleEvent.id,
      results: sampleResults,
      normalization: {
        method: "Sample fixture normalization",
        scale: "0-5",
        panelMean: 0,
        panelStd: 0,
        explanation: "Synthetic fixture data is enabled for development only.",
      },
      integrity: {
        totalReviews: sampleProgress.totalReviews,
        completedReviews: sampleProgress.completedReviews,
        pendingReviews: sampleProgress.pendingReviews,
        judgeAnomalies: 0,
        projectsWithIncompleteReviews: 0,
      },
    };
  }

  if (eventId) {
    const raw = await apiRequest<unknown>(endpoints.results.list(eventId), { token });
    const root = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
    return {
      eventId: String(root.event_id ?? eventId),
      results: normalizeResults(raw),
      normalization: normalizeNormalization(root.normalization),
      integrity: normalizeIntegrity(root.integrity),
    };
  }

  const events = await getEvents();
  let lastBundle: ResultsBundle | null = null;
  for (const event of events) {
    try {
      const bundle = await getResultsBundle(token, event.id);
      lastBundle = bundle;
      if (bundle.integrity.totalReviews > 0 || bundle.results.some((row) => row.rawScore !== null || row.normalizedScore !== null)) {
        return bundle;
      }
    } catch {
      // Some events may not have an active rubric/results set yet. Try the next event.
    }
  }
  if (lastBundle) return lastBundle;
  throw new Error("No event results are currently available.");
}

export async function getResults(token: string, eventId?: string): Promise<ResultRecord[]> {
  return (await getResultsBundle(token, eventId)).results;
}

export async function getProjectResult(token: string, id: string, eventId?: string): Promise<ResultRecord> {
  const bundle = await getResultsBundle(token, eventId);
  const found = bundle.results.find((result) => result.projectId === id);
  if (!found) throw new Error(`Project ${id} is not present in the selected event results.`);
  return found;
}

export async function exportResults(token: string, eventId?: string): Promise<string> {
  if (fixtureSession(token)) return "rank_raw,rank_normalized,project_id,project_title,raw_score,normalized_score,completed_reviews,assigned_reviews,rank_change\n1,1,Project A,4.72,4.70,4,4,0\n";
  const bundle = await getResultsBundle(token, eventId);
  return apiRequest<string>(endpoints.results.csv(bundle.eventId), { token, headers: { Accept: "text/csv" } });
}

export async function saveEvent(token: string, payload: { id?: string; name: string; description: string; start_date: string; end_date: string; submission_deadline: string }): Promise<EventRecord> {
  if (fixtureSession(token)) return { ...sampleEvent, ...payload, startDate: payload.start_date, endDate: payload.end_date, submissionDeadline: payload.submission_deadline };
  const raw = await apiRequest<unknown>(payload.id ? endpoints.events.update(payload.id) : endpoints.events.create, {
    method: payload.id ? "PUT" : "POST",
    token,
    body: JSON.stringify(payload),
  });
  return normalizeEvent(raw);
}

export function apiListForDisplay(payload: unknown): unknown[] { return asList(payload); }

import type { CommunityConfig, CommunityProject, PairwisePair } from "@/types/portal";
import { tierEndpoints } from "@/lib/api/endpoints";

export async function getCommunityConfig(eventId: string, token: string): Promise<CommunityConfig> {
  return apiRequest<CommunityConfig>(tierEndpoints.community.config(eventId), { token });
}

export async function getCommunityProjects(eventId: string, token: string): Promise<CommunityProject[]> {
  return apiRequest<CommunityProject[]>(tierEndpoints.community.projects(eventId), { token });
}

export async function castCommunityVote(eventId: string, projectId: number, token: string): Promise<unknown> {
  return apiRequest(tierEndpoints.community.vote, { method: "POST", token, body: JSON.stringify({ event_id: Number(eventId), project_id: projectId }) });
}

export async function addCommunityComment(eventId: string, projectId: number, body: string, token: string): Promise<unknown> {
  return apiRequest(tierEndpoints.community.comments, { method: "POST", token, body: JSON.stringify({ event_id: Number(eventId), project_id: projectId, body }) });
}

export async function getCommunityComments(eventId: string, projectId: number): Promise<Array<{ id: number; body: string; author: string; created_at: string }>> {
  return apiRequest(tierEndpoints.community.commentsFor(eventId, projectId));
}

export async function getCommunityResults(eventId: string): Promise<Array<{ project_id: number; votes: number; rank: number }>> {
  return apiRequest(tierEndpoints.community.results(eventId));
}

export async function configureCommunityVoting(token: string, payload: { event_id: string; voting_start: string; voting_end: string; results_hidden_until_close: boolean; max_votes_per_user: number; active: boolean }): Promise<CommunityConfig> {
  return apiRequest(tierEndpoints.community.config(payload.event_id), { method: "POST", token, body: JSON.stringify({ ...payload, event_id: Number(payload.event_id) }) });
}

export async function getPairwiseNext(eventId: string, token: string): Promise<PairwisePair> {
  return apiRequest(tierEndpoints.pairwise.next(eventId), { token });
}

export async function submitPairwiseVote(payload: { event_id: string; project_a_id: number; project_b_id: number; winner_id: number }, token: string): Promise<unknown> {
  return apiRequest(tierEndpoints.pairwise.vote, { method: "POST", token, body: JSON.stringify({ ...payload, event_id: Number(payload.event_id) }) });
}

export async function getPairwiseRanking(eventId: string, token: string): Promise<{ event_id: number; method: string; comparisons: number; rankings: Array<{ project_id: number; project_title: string; bt_score: number; relative_score: number; rank: number }> }> {
  return apiRequest(tierEndpoints.pairwise.ranking(eventId), { token });
}

export async function getWebhooks(token: string): Promise<Array<{ id: number; event_id: number | null; url: string; active: boolean; created_at: string }>> {
  return apiRequest(tierEndpoints.platform.webhooks, { token });
}

export async function createWebhook(token: string, eventId: string, url: string, secret: string): Promise<unknown> {
  return apiRequest(tierEndpoints.platform.webhooks, { method: "POST", token, body: JSON.stringify({ event_id: Number(eventId), url, secret }) });
}

export async function deleteWebhook(token: string, id: number): Promise<unknown> {
  return apiRequest(tierEndpoints.platform.deleteWebhook(id), { method: "DELETE", token });
}

export async function getDuplicateScan(token: string, eventId: string): Promise<{ event_id: number; groups: Array<{ type: string; fingerprint: string; project_ids: number[] }> }> {
  return apiRequest(tierEndpoints.platform.duplicates(eventId), { token });
}


export async function getNormalizationProof(token: string, eventId: string): Promise<unknown> {
  return apiRequest(tierEndpoints.platform.normalizationProof(eventId), { token });
}
