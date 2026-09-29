export type AppRole = "participant" | "judge" | "organizer" | "admin";
export type LoadState = "loading" | "ready" | "empty" | "error";
export type EventStatus = "upcoming" | "open" | "closed" | "unknown";
export type ProjectStatus = "draft" | "submitted" | "closed" | "unknown";
export type ReviewStatus = "pending" | "in_progress" | "completed" | "unknown";

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: AppRole;
}

export interface Track { id: string; name: string }
export interface Prize { id: string; title: string; description: string; amount?: number; rank?: number }

export interface EventRecord {
  id: string;
  name: string;
  description: string;
  startDate: string;
  endDate: string;
  submissionDeadline: string;
  rubricId?: string;
  status: EventStatus;
  tracks: Track[];
  prizes: Prize[];
}

export interface TeamMember {
  id: string;
  name: string;
  email?: string;
  isCaptain?: boolean;
}

export interface TeamRecord {
  id: string;
  name: string;
  status: string;
  eventId?: string;
  createdBy?: string;
  members: TeamMember[];
  inviteUrl?: string;
}

export interface ProjectRecord {
  id: string;
  eventId?: string;
  teamId?: string;
  trackId?: string;
  title: string;
  summary: string;
  description: string;
  track: string;
  team: string;
  teamSize: number;
  repositoryUrl: string;
  demoUrl: string;
  submittedAt: string;
  status: ProjectStatus;
}

export interface JudgeRecord {
  id: string;
  userId?: string;
  name: string;
  email: string;
  status: string;
  assignedCount: number;
  completedCount: number;
}

export interface RubricCriterion {
  id: string;
  name: string;
  description: string;
  weight: number;
  maxScore: number;
}

export interface AssignmentRecord {
  id: string;
  project: ProjectRecord;
  status: ReviewStatus;
  rubricId?: string;
  eventId?: string;
  judgeId?: string;
  dueAt?: string;
  submittedAt?: string;
  scoresCompleted?: number;
  scoresRequired?: number;
}

export interface ScoreRecord {
  id: string;
  projectId: string;
  criterionId: string;
  score: number;
  comment: string;
}

export interface JudgeBreakdownRecord {
  judgeId: string;
  judgeName: string;
  rawScore: number | null;
  normalizedScore: number | null;
  judgeMean: number | null;
  judgeStd: number | null;
  note?: string;
}

export interface NormalizationRecord {
  method: string;
  scale: string;
  panelMean: number;
  panelStd: number;
  explanation: string;
}

export interface ResultsIntegrity {
  totalReviews: number;
  completedReviews: number;
  pendingReviews: number;
  judgeAnomalies: number;
  projectsWithIncompleteReviews: number;
}

export interface ResultRecord {
  projectId: string;
  projectTitle: string;
  team: string;
  track: string;
  rank: number | null;
  rawScore: number | null;
  normalizedScore: number | null;
  rankBefore: number | null;
  rankAfter: number | null;
  reviewCount: number;
  assignedReviews?: number;
  explanation?: string;
  judgeBreakdown?: JudgeBreakdownRecord[];
}

export interface ResultsBundle {
  eventId: string;
  results: ResultRecord[];
  normalization: NormalizationRecord;
  integrity: ResultsIntegrity;
}

export interface ReviewProgress {
  totalReviews: number;
  completedReviews: number;
  pendingReviews: number;
  assignedProjects: number;
  completedProjects: number;
  judgeDistribution: Array<{ judgeName: string; assigned: number; completed: number }>;
  scoreVariance: number | null;
  normalizationStatus: string;
}

export interface CommunityProject {
  id: number;
  title: string;
  summary: string;
  team_name?: string;
  track_name?: string;
  repo_url?: string | null;
  demo_url?: string | null;
  voting_open: boolean;
}

export interface CommunityConfig {
  id: number;
  event_id: number;
  voting_start: string;
  voting_end: string;
  results_hidden_until_close: boolean;
  max_votes_per_user: number;
  active: boolean;
}

export interface PairwisePair {
  event_id: number;
  project_a: { id: number; title: string; summary: string };
  project_b: { id: number; title: string; summary: string };
}
