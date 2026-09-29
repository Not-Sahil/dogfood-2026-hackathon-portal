import type {
  AssignmentRecord,
  EventRecord,
  EventStatus,
  JudgeBreakdownRecord,
  JudgeRecord,
  NormalizationRecord,
  Prize,
  ProjectRecord,
  ProjectStatus,
  ResultRecord,
  ResultsIntegrity,
  ReviewProgress,
  ReviewStatus,
  RubricCriterion,
  TeamRecord,
  Track,
} from "@/types/portal";

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

function list(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  const wrapper = record(value);
  if (Array.isArray(wrapper.data)) return wrapper.data;
  if (Array.isArray(wrapper.items)) return wrapper.items;
  if (Array.isArray(wrapper.results)) return wrapper.results;
  if (Array.isArray(wrapper.rows)) return wrapper.rows;
  return [];
}

const numberOr = (value: unknown, fallback = 0): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const nullableNumber = (value: unknown): number | null => {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

function statusOf(value: unknown): EventStatus {
  const status = text(value).toLowerCase();
  if (["open", "active", "registration_open"].includes(status)) return "open";
  if (["closed", "complete", "completed"].includes(status)) return "closed";
  if (["upcoming", "draft", "scheduled"].includes(status)) return "upcoming";
  return "unknown";
}

function projectStatus(value: unknown): ProjectStatus {
  const status = text(value).toLowerCase();
  if (["draft", "in_progress"].includes(status)) return "draft";
  if (["submitted", "published", "complete"].includes(status)) return "submitted";
  if (["closed", "locked"].includes(status)) return "closed";
  return "unknown";
}

function reviewStatus(value: unknown): ReviewStatus {
  const status = text(value).toLowerCase();
  if (["completed", "submitted", "complete"].includes(status)) return "completed";
  if (["in_progress", "started"].includes(status)) return "in_progress";
  if (["pending", "assigned", "open"].includes(status)) return "pending";
  return "unknown";
}

export function asList(value: unknown): unknown[] { return list(value); }

export function normalizeTrack(value: unknown): Track {
  const raw = record(value);
  return { id: text(raw.id ?? raw.track_id ?? raw.name), name: text(raw.name ?? raw.title, "Track") };
}

export function normalizePrize(value: unknown): Prize {
  const raw = record(value);
  const amount = nullableNumber(raw.amount ?? raw.value);
  const rank = nullableNumber(raw.rank);
  return {
    id: text(raw.id ?? raw.prize_id ?? raw.title),
    title: text(raw.title ?? raw.name, "Prize"),
    description: text(raw.description),
    ...(amount !== null ? { amount } : {}),
    ...(rank !== null ? { rank } : {}),
  };
}

export function normalizeEvent(value: unknown): EventRecord {
  const raw = record(value);
  return {
    id: text(raw.id ?? raw.event_id),
    name: text(raw.name ?? raw.title, "Untitled event"),
    description: text(raw.description),
    startDate: text(raw.start_date ?? raw.startDate),
    endDate: text(raw.end_date ?? raw.endDate),
    submissionDeadline: text(raw.submission_deadline ?? raw.submissionDeadline ?? raw.submissions_close),
    rubricId: text(raw.rubric_id ?? raw.rubricId) || undefined,
    status: statusOf(raw.status),
    tracks: list(raw.tracks).map(normalizeTrack),
    prizes: list(raw.prizes).map(normalizePrize),
  };
}

export function normalizeEvents(value: unknown): EventRecord[] { return list(value).map(normalizeEvent); }

export function normalizeProject(value: unknown): ProjectRecord {
  const raw = record(value);
  const team = record(raw.team);
  const track = record(raw.track);
  const title = text(raw.title ?? raw.name, "Untitled project");
  const description = text(raw.description ?? raw.summary);
  const teamName = text(raw.team_name ?? team.name ?? (typeof raw.team === "string" ? raw.team : ""), "Independent");
  const teamSize = numberOr(raw.team_size ?? raw.teamSize ?? (Array.isArray(team.members) ? team.members.length : 1), 1);

  return {
    id: text(raw.id ?? raw.project_id),
    eventId: text(raw.event_id ?? raw.eventId) || undefined,
    teamId: text(raw.team_id ?? raw.teamId) || undefined,
    trackId: text(raw.track_id ?? raw.trackId) || undefined,
    title,
    summary: text(raw.summary ?? raw.description, "No summary provided."),
    description,
    track: text(raw.track_name ?? track.name ?? (typeof raw.track === "string" ? raw.track : ""), "Unassigned"),
    team: teamName,
    teamSize,
    repositoryUrl: text(raw.repo_url ?? raw.repository_url ?? raw.repositoryUrl ?? raw.repoUrl),
    demoUrl: text(raw.demo_url ?? raw.demoUrl),
    submittedAt: text(raw.submission?.submitted_at ?? raw.submitted_at ?? raw.submittedAt ?? raw.updated_at ?? raw.created_at),
    status: projectStatus(raw.status),
  };
}

export function normalizeProjects(value: unknown): ProjectRecord[] { return list(value).map(normalizeProject); }

export function normalizeTeam(value: unknown): TeamRecord {
  const raw = record(value);
  const members = list(raw.members ?? raw.team_members).map((item) => {
    const member = record(item);
    return {
      id: text(member.user_id ?? member.id),
      name: text(member.name ?? member.full_name ?? member.email, "Member"),
      ...(member.email ? { email: text(member.email) } : {}),
      ...(typeof member.is_captain === "boolean" ? { isCaptain: member.is_captain } : {}),
    };
  });

  return {
    id: text(raw.id ?? raw.team_id),
    name: text(raw.name, "Untitled team"),
    status: text(raw.status, "Active"),
    eventId: text(raw.event_id ?? raw.eventId) || undefined,
    createdBy: text(raw.created_by ?? raw.createdBy) || undefined,
    members,
    inviteUrl: text(raw.invite_url ?? raw.join_url ?? raw.inviteUrl) || undefined,
  };
}

export function normalizeTeams(value: unknown): TeamRecord[] {
  const rows = list(value);
  if (rows.length) return rows.map(normalizeTeam);
  const raw = record(value);
  if (raw.id || raw.team_id) return [normalizeTeam(value)];
  return [];
}

export function normalizeJudge(value: unknown): JudgeRecord {
  const raw = record(value);
  return {
    id: text(raw.id ?? raw.judge_id ?? raw.user_id),
    userId: text(raw.user_id ?? raw.userId) || undefined,
    name: text(raw.name ?? raw.full_name ?? raw.email, "Judge"),
    email: text(raw.email),
    status: text(raw.status, "Active"),
    assignedCount: numberOr(raw.assigned_count ?? raw.assignedCount),
    completedCount: numberOr(raw.completed_count ?? raw.completedCount),
  };
}

export function normalizeJudges(value: unknown): JudgeRecord[] { return list(value).map(normalizeJudge); }

export function normalizeCriterion(value: unknown): RubricCriterion {
  const raw = record(value);
  return {
    id: text(raw.id ?? raw.criterion_id ?? raw.name),
    name: text(raw.name ?? raw.title, "Criterion"),
    description: text(raw.description),
    weight: numberOr(raw.weight ?? raw.weight_percent),
    maxScore: numberOr(raw.max_score ?? raw.maxScore, 5),
  };
}

export function normalizeRubric(value: unknown): RubricCriterion[] {
  const raw = record(value);
  return list(Array.isArray(value) ? value : raw.criteria ?? raw.items ?? raw.data).map(normalizeCriterion);
}

export function normalizeAssignment(value: unknown): AssignmentRecord {
  const raw = record(value);
  const projectValue = raw.project ?? {
    id: raw.project_id,
    event_id: raw.event_id,
    title: raw.project_title,
    summary: raw.project_summary,
    team_name: raw.team_name,
    track_name: raw.track_name,
    repo_url: raw.repo_url,
    demo_url: raw.demo_url,
    status: "submitted",
  };
  const project = normalizeProject(projectValue);
  const completed = raw.completed === true || text(raw.status).toLowerCase() === "completed";

  return {
    id: text(raw.id ?? raw.assignment_id ?? `${project.id}-assignment`),
    project,
    status: completed ? "completed" : reviewStatus(raw.status ?? raw.review_status),
    rubricId: text(raw.rubric_id ?? raw.rubricId) || undefined,
    eventId: text(raw.event_id ?? raw.eventId ?? project.eventId) || undefined,
    judgeId: text(raw.judge_id ?? raw.judgeId) || undefined,
    dueAt: text(raw.due_at ?? raw.dueAt) || undefined,
    submittedAt: text(raw.submitted_at ?? raw.submittedAt) || undefined,
    scoresCompleted: numberOr(raw.scores_completed),
    scoresRequired: numberOr(raw.scores_required),
  };
}

export function normalizeAssignments(value: unknown): AssignmentRecord[] { return list(value).map(normalizeAssignment); }

function normalizeJudgeBreakdown(value: unknown): JudgeBreakdownRecord {
  const raw = record(value);
  return {
    judgeId: text(raw.judge_id ?? raw.judgeId),
    judgeName: text(raw.judge_name ?? raw.judgeName, "Judge"),
    rawScore: nullableNumber(raw.raw_score ?? raw.rawScore),
    normalizedScore: nullableNumber(raw.normalized_score ?? raw.normalizedScore),
    judgeMean: nullableNumber(raw.judge_mean ?? raw.judgeMean),
    judgeStd: nullableNumber(raw.judge_std ?? raw.judgeStd),
    note: text(raw.note) || undefined,
  };
}

export function normalizeResult(value: unknown, normalization?: NormalizationRecord): ResultRecord {
  const raw = record(value);
  const project = record(raw.project);
  const breakdown = list(raw.judge_breakdown ?? raw.judgeBreakdown).map(normalizeJudgeBreakdown);
  const rawScore = nullableNumber(raw.raw_score ?? raw.rawScore ?? raw.average_score);
  const normalizedScore = nullableNumber(raw.normalized_score ?? raw.normalizedScore);
  const rankBefore = nullableNumber(raw.rank_raw ?? raw.rank_before ?? raw.rankBefore);
  const rankAfter = nullableNumber(raw.rank_normalized ?? raw.rank_after ?? raw.rankAfter ?? raw.rank);

  const notes = breakdown.map((item) => item.note).filter(Boolean).join("; ");
  const explanation = text(raw.explanation ?? raw.normalization_explanation) || notes || normalization?.explanation;

  return {
    projectId: text(raw.project_id ?? raw.projectId ?? project.id),
    projectTitle: text(raw.project_title ?? raw.title ?? project.title, "Project"),
    team: text(raw.team_name ?? raw.team ?? project.team, "—"),
    track: text(raw.track_name ?? raw.track ?? project.track, "—"),
    rank: rankAfter,
    rawScore,
    normalizedScore,
    rankBefore,
    rankAfter,
    reviewCount: numberOr(raw.completed_reviews ?? raw.review_count ?? raw.reviewCount),
    assignedReviews: numberOr(raw.assigned_reviews ?? raw.assignedReviews),
    explanation: explanation || undefined,
    judgeBreakdown: breakdown.length ? breakdown : undefined,
  };
}

export function normalizeResults(value: unknown): ResultRecord[] {
  const raw = record(value);
  const normalization = normalizeNormalization(raw.normalization);
  return list(Array.isArray(value) ? value : raw.rows ?? raw.results ?? raw.data).map((item) => normalizeResult(item, normalization));
}

export function normalizeNormalization(value: unknown): NormalizationRecord {
  const raw = record(value);
  return {
    method: text(raw.method, "Not provided"),
    scale: text(raw.scale, "Not provided"),
    panelMean: numberOr(raw.panel_mean ?? raw.panelMean),
    panelStd: numberOr(raw.panel_std ?? raw.panelStd),
    explanation: text(raw.explanation, "The backend did not provide a normalization explanation."),
  };
}

export function normalizeIntegrity(value: unknown): ResultsIntegrity {
  const raw = record(value);
  return {
    totalReviews: numberOr(raw.total_reviews ?? raw.totalReviews),
    completedReviews: numberOr(raw.completed_reviews ?? raw.completedReviews),
    pendingReviews: numberOr(raw.pending_reviews ?? raw.pendingReviews),
    judgeAnomalies: numberOr(raw.judge_anomalies ?? raw.judgeAnomalies),
    projectsWithIncompleteReviews: numberOr(raw.projects_with_incomplete_reviews ?? raw.projectsWithIncompleteReviews),
  };
}

export function normalizeProgress(value: unknown): ReviewProgress {
  const rows = list(value).map((item) => {
    const row = record(item);
    return {
      judgeId: text(row.judge_id),
      judgeName: text(row.name ?? row.judge_name, "Judge"),
      assigned: numberOr(row.assigned),
      completed: numberOr(row.completed),
      pending: numberOr(row.pending ?? numberOr(row.assigned) - numberOr(row.completed)),
    };
  });

  if (rows.length) {
    const total = rows.reduce((sum, row) => sum + row.assigned, 0);
    const completed = rows.reduce((sum, row) => sum + row.completed, 0);
    return {
      totalReviews: total,
      completedReviews: completed,
      pendingReviews: rows.reduce((sum, row) => sum + row.pending, 0),
      assignedProjects: 0,
      completedProjects: 0,
      judgeDistribution: rows.map((row) => ({ judgeName: row.judgeName, assigned: row.assigned, completed: row.completed })),
      scoreVariance: null,
      normalizationStatus: completed > 0 ? "Reviews available" : "No completed reviews",
    };
  }

  const raw = record(value);
  const total = numberOr(raw.total_reviews ?? raw.totalReviews);
  const completed = numberOr(raw.completed_reviews ?? raw.completedReviews);
  return {
    totalReviews: total,
    completedReviews: completed,
    pendingReviews: numberOr(raw.pending_reviews ?? raw.pendingReviews, Math.max(0, total - completed)),
    assignedProjects: numberOr(raw.assigned_projects ?? raw.assignedProjects),
    completedProjects: numberOr(raw.completed_projects ?? raw.completedProjects),
    judgeDistribution: list(raw.judge_distribution ?? raw.judgeDistribution).map((item) => {
      const row = record(item);
      return { judgeName: text(row.judge_name ?? row.judgeName, "Judge"), assigned: numberOr(row.assigned), completed: numberOr(row.completed) };
    }),
    scoreVariance: nullableNumber(raw.score_variance ?? raw.scoreVariance),
    normalizationStatus: text(raw.normalization_status ?? raw.normalizationStatus, "Not provided by API"),
  };
}

export function normalizeProjectStatus(value: unknown): ProjectStatus { return projectStatus(value); }
export function normalizeEventStatus(value: unknown): EventStatus { return statusOf(value); }
