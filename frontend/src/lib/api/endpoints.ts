const enc = (id: string | number) => encodeURIComponent(String(id));

export const endpoints = {
  auth: {
    login: "/api/auth/login",
    register: "/api/auth/register",
    me: "/api/auth/me",
    logout: "/api/auth/logout",
  },
  events: {
    list: "/api/events",
    detail: (id: string | number) => `/api/events/${enc(id)}`,
    create: "/api/events",
    update: (id: string | number) => `/api/events/${enc(id)}`,
    tracks: (eventId: string | number) => `/api/events/${enc(eventId)}/tracks`,
    trackDetail: (trackId: string | number) => `/api/events/tracks/${enc(trackId)}`,
    prizes: (eventId: string | number) => `/api/events/${enc(eventId)}/prizes`,
    prizeDetail: (prizeId: string | number) => `/api/events/prizes/${enc(prizeId)}`,
  },
  teams: {
    list: "/api/teams",
    mine: "/api/teams/my",
    detail: (id: string | number) => `/api/teams/${enc(id)}`,
    create: "/api/teams",
    invites: (id: string | number) => `/api/teams/${enc(id)}/invites`,
    join: "/api/teams/join",
  },
  projects: {
    list: "/api/projects",
    mine: "/api/projects/mine",
    detail: (id: string | number) => `/api/projects/${enc(id)}`,
    create: "/api/projects",
    update: (id: string | number) => `/api/projects/${enc(id)}`,
    submit: (id: string | number) => `/api/projects/${enc(id)}/submit`,
  },
  judges: {
    list: "/api/judges",
    invite: "/api/judges/invitations",
    acceptInvite: "/api/judges/accept-invite",
    assign: "/api/judges/assign",
    assignments: "/api/judges/assignments",
  },
  judging: {
    rubric: "/api/rubrics",
    activeRubric: (eventId: string | number) => `/api/rubrics/active?event_id=${enc(eventId)}`,
    rubricDetail: (id: string | number) => `/api/rubrics/${enc(id)}`,
    scores: "/api/judge/scores",
    progress: "/api/judge/progress",
  },
  results: {
    list: (eventId: string | number) => `/api/results?event_id=${enc(eventId)}`,
    project: (id: string | number, eventId: string | number) => `/api/results/${enc(id)}?event_id=${enc(eventId)}`,
    csv: (eventId: string | number) => `/api/export.csv?event_id=${enc(eventId)}`,
  },
} as const;

export const tierEndpoints = {
  community: {
    config: (eventId: string | number) => `/api/community/config?event_id=${enc(eventId)}`,
    projects: (eventId: string | number) => `/api/community/projects?event_id=${enc(eventId)}`,
    vote: "/api/community/vote",
    comments: "/api/community/comments",
    commentsFor: (eventId: string | number, projectId: string | number) => `/api/community/comments?event_id=${enc(eventId)}&project_id=${enc(projectId)}`,
    results: (eventId: string | number) => `/api/community/results?event_id=${enc(eventId)}`,
  },
  pairwise: {
    next: (eventId: string | number) => `/api/pairwise/next?event_id=${enc(eventId)}`,
    vote: "/api/pairwise/vote",
    ranking: (eventId: string | number) => `/api/pairwise/ranking?event_id=${enc(eventId)}`,
  },
  platform: {
    webhooks: "/api/webhooks",
    deleteWebhook: (id: string | number) => `/api/webhooks/${enc(id)}`,
    duplicates: (eventId: string | number) => `/api/integrity/duplicates?event_id=${enc(eventId)}`,
    normalizationProof: (eventId: string | number) => `/api/normalization/proof?event_id=${enc(eventId)}`,
    projectsExport: (eventId?: string | number) => `/api/system/export/projects.csv${eventId ? `?event_id=${enc(eventId)}` : ""}`,
    teamsImport: (eventId: string | number) => `/api/system/import/teams.csv?event_id=${enc(eventId)}`,
    judgeRecord: (judgeId: string | number, eventId: string | number) => `/api/judge-records/${enc(judgeId)}?event_id=${enc(eventId)}`,
    judgeCertificate: (judgeId: string | number, eventId: string | number) => `/api/judge-records/${enc(judgeId)}/certificate?event_id=${enc(eventId)}`,
    publicJudgeRecord: (recordId: string | number) => `/api/public/judge-records/${enc(recordId)}`,
    publicKey: "/api/judge-records/public-key",
  },
} as const;
