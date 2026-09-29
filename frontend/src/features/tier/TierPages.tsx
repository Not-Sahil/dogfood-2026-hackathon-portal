"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FixtureBanner } from "@/components/ui/FixtureBanner";
import { MetricCard } from "@/components/ui/MetricCard";
import { Notice } from "@/components/ui/Notice";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { StatePanel } from "@/components/ui/StatePanel";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/features/auth/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { chooseDefaultEvent, getEvents, getCommunityConfig, getCommunityProjects, castCommunityVote, addCommunityComment, getCommunityComments, getCommunityResults, getPairwiseNext, submitPairwiseVote, getPairwiseRanking, getWebhooks, getJudges, createWebhook, deleteWebhook, getDuplicateScan, configureCommunityVoting } from "@/lib/api/portal";
import { apiUrl } from "@/lib/api/config";
import { endpoints } from "@/lib/api/endpoints";
import type { CommunityConfig, CommunityProject, EventRecord } from "@/types/portal";

function timeText(value: string) {
  return new Date(value).toLocaleString();
}

export function CommunityVotingPage() {
  const { token } = useAuth();
  const [event, setEvent] = useState<EventRecord | null>(null);
  const [projects, setProjects] = useState<CommunityProject[]>([]);
  const [config, setConfig] = useState<CommunityConfig | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [comments, setComments] = useState<Record<number, Array<{ id: number; body: string; author: string; created_at: string }>>>({});
  const [commentDraft, setCommentDraft] = useState<Record<number, string>>({});
  const [voted, setVoted] = useState<Set<number>>(new Set());
  const [communityResults, setCommunityResults] = useState<Array<{ project_id: number; votes: number; rank: number }> | null>(null);
  const [resultsError, setResultsError] = useState("");

  const load = useCallback(async () => {
    if (!token) throw new Error("Your session has expired.");
    const events = await getEvents();
    const current = chooseDefaultEvent(events);
    if (!current) throw new Error("No event is available.");
    const [cfg, list] = await Promise.all([getCommunityConfig(current.id, token), getCommunityProjects(current.id, token)]);
    return { event: current, config: cfg, projects: list };
  }, [token]);
  const resource = useAsyncResource(load);

  useEffect(() => {
    if (resource.status === "ready") {
      setEvent(resource.data.event);
      setConfig(resource.data.config);
      setProjects(resource.data.projects);
    }
  }, [resource.status, resource.status === "ready" ? resource.data : null]);

  const openCount = useMemo(() => projects.filter((p) => p.voting_open).length, [projects]);

  async function vote(id: number) {
    if (!token || !event) return;
    setError(""); setNotice("");
    try {
      await castCommunityVote(event.id, id, token);
      setVoted((current) => new Set(current).add(id));
      setNotice("Your community vote was recorded. Duplicate votes for the same project are blocked by the backend.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Vote failed."); }
  }

  async function submitComment(id: number) {
    if (!token || !event) return;
    const body = (commentDraft[id] ?? "").trim();
    if (!body) return;
    setError("");
    try {
      await addCommunityComment(event.id, id, body, token);
      const rows = await getCommunityComments(event.id, id);
      setComments((current) => ({ ...current, [id]: rows }));
      setCommentDraft((current) => ({ ...current, [id]: "" }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Comment failed."); }
  }

  async function loadComments(id: number) {
    if (!event || comments[id]) return;
    try { setComments((current) => ({ ...current, [id]: [] })); const rows = await getCommunityComments(event.id, id); setComments((current) => ({ ...current, [id]: rows })); }
    catch { /* Comments are supplementary to voting. */ }
  }

  async function loadResults() {
    if (!event) return;
    setResultsError("");
    try {
      setCommunityResults(await getCommunityResults(event.id));
    } catch (reason) {
      setCommunityResults(null);
      setResultsError(reason instanceof Error ? reason.message : "Results are not available yet.");
    }
  }

  const votingClosed = Boolean(config && new Date(config.voting_end).getTime() < Date.now());

  return <>
    <FixtureBanner />
    <PageHeader eyebrow="PARTICIPANT / T3 PUBLIC" title="Community voting" description="Projects are presented in a user-specific randomized order. Results stay hidden until the configured voting window closes." actions={<Link className="button button--quiet" href="/participant">Overview</Link>} />
    {resource.status === "loading" ? <StatePanel variant="loading" title="Preparing the ballot" description="Loading the event voting window and submitted projects." /> : null}
    {resource.status === "error" ? <StatePanel variant="error" title="Voting unavailable" description={resource.error} actionLabel="Retry" onAction={resource.reload} /> : null}
    {event && config && resource.status === "ready" ? <>
      <div className="metric-grid metric-grid--four">
        <MetricCard label="Voting window" value={config.active ? "ACTIVE" : "OFF"} note={`${timeText(config.voting_start)} → ${timeText(config.voting_end)}`} accent="mint" />
        <MetricCard label="Ballot size" value={projects.length} note="Submitted projects in randomized order" />
        <MetricCard label="Your allowance" value={config.max_votes_per_user} note="Maximum projects per account" accent="amber" />
        <MetricCard label="Results" value="HIDDEN" note="Until the voting window closes" accent="coral" />
      </div>
      {notice ? <Notice tone="mint" title="Ballot update">{notice}</Notice> : null}
      {error ? <div className="form-error" role="alert">{error}</div> : null}
      <Panel title={`Ballot · ${event.name}`} description={`${openCount} projects are currently available for community voting.`}>
        <div className="tier-card-grid">
          {projects.map((project) => <article className="tier-card" key={project.id}>
            <div className="tier-card__top"><span className="eyebrow">PROJECT {String(project.id).padStart(2, "0")}</span><StatusBadge tone={voted.has(project.id) ? "mint" : "blue"}>{voted.has(project.id) ? "Voted" : "Open"}</StatusBadge></div>
            <h2>{project.title}</h2><p>{project.summary}</p>
            <div className="tier-card__facts"><span>{project.team_name ?? "Team"}</span><span>{project.track_name ?? "Track"}</span></div>
            <div className="tier-card__links">{project.repo_url ? <a href={project.repo_url} target="_blank" rel="noreferrer">Repository ↗</a> : null}{project.demo_url ? <a href={project.demo_url} target="_blank" rel="noreferrer">Demo ↗</a> : null}</div>
            <div className="tier-card__actions"><button className="button button--primary" type="button" disabled={!project.voting_open || voted.has(project.id)} onClick={() => void vote(project.id)}>{voted.has(project.id) ? "Vote recorded" : "Vote for project"}</button><button className="button button--quiet" type="button" onClick={() => void loadComments(project.id)}>Comments</button></div>
            {comments[project.id] ? <div className="comment-stream"><div className="comment-stream__header">Community comments <span>{comments[project.id].length}</span></div>{comments[project.id].map((comment) => <div className="comment-row" key={comment.id}><strong>{comment.author}</strong><p>{comment.body}</p></div>)}<textarea rows={3} value={commentDraft[project.id] ?? ""} onChange={(e) => setCommentDraft((current) => ({ ...current, [project.id]: e.target.value }))} placeholder="Add a constructive comment" /><button type="button" className="button button--quiet" onClick={() => void submitComment(project.id)}>Post comment</button></div> : null}
          </article>)}
        </div>
      </Panel>
      <Notice tone="quiet" title="Anti-abuse controls">The backend enforces authenticated participant voting, one vote per participant/project, a per-event vote allowance, and a short-window address rate limit. These controls mitigate common ballot stuffing patterns without claiming to identify real-world people.</Notice>
      <Panel title="Community results" description={votingClosed ? "The voting window is closed, so public results can now be requested." : "Results remain hidden while the configured voting window is open."}>
        <div className="form-actions">
          <button type="button" className="button button--quiet" disabled={!votingClosed} onClick={() => void loadResults()}>Load final results</button>
          {!votingClosed ? <span className="panel-footnote">Results are intentionally unavailable until {timeText(config.voting_end)}.</span> : null}
        </div>
        {resultsError ? <div className="form-error" role="alert">{resultsError}</div> : null}
        {communityResults ? <div className="compact-list tier-results-list" style={{ marginTop: "1rem" }}>{communityResults.map((row) => { const project = projects.find((item) => item.id === row.project_id); return <div className="compact-row" key={row.project_id}><div><strong>#{row.rank} {project?.title ?? `Project ${row.project_id}`}</strong><small>{row.votes} community votes</small></div><span>Rank {row.rank}</span></div>; })}</div> : null}
      </Panel>
    </> : null}
  </>;
}

export function PairwiseJudgePage() {
  const { token } = useAuth();
  const [event, setEvent] = useState<EventRecord | null>(null);
  const [pair, setPair] = useState<{ event_id: number; project_a: { id: number; title: string; summary: string }; project_b: { id: number; title: string; summary: string } } | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!token) throw new Error("Your session has expired.");
    const current = chooseDefaultEvent(await getEvents());
    if (!current) throw new Error("No event is available.");
    const next = await getPairwiseNext(current.id, token);
    return { event: current, pair: next };
  }, [token]);
  const resource = useAsyncResource(load);
  useEffect(() => { if (resource.status === "ready") { setEvent(resource.data.event); setPair(resource.data.pair); } }, [resource.status, resource.status === "ready" ? resource.data : null]);

  async function choose(winnerId: number) {
    if (!token || !event || !pair) return;
    setError(""); setMessage("");
    try {
      await submitPairwiseVote({ event_id: event.id, project_a_id: pair.project_a.id, project_b_id: pair.project_b.id, winner_id: winnerId }, token);
      setMessage("Preference recorded. Loading the next comparison.");
      setPair(null);
      const next = await getPairwiseNext(event.id, token);
      setPair(next);
      setMessage("Preference recorded.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Pairwise comparison failed."); }
  }

  return <>
    <FixtureBanner />
    <PageHeader eyebrow="JUDGE / PAIRWISE BONUS" title="Pairwise judging" description="Compare two assigned projects at a time. The organizer can recover a ranking using a Bradley-Terry estimator." actions={<Link className="button button--quiet" href="/judge">Overview</Link>} />
    {resource.status === "loading" ? <StatePanel variant="loading" title="Finding your next comparison" description="Only projects assigned to your authenticated judge account are eligible." /> : null}
    {resource.status === "error" ? <StatePanel variant="error" title="Pairwise mode unavailable" description={resource.error} actionLabel="Retry" onAction={resource.reload} /> : null}
    {message ? <Notice tone="mint" title="Comparison saved">{message}</Notice> : null}{error ? <div className="form-error" role="alert">{error}</div> : null}
    {pair ? <Panel title="Which project is stronger?" description="Choose one project. The backend records only the pair and winner, never peer rubric scores." >
      <div className="pairwise-grid">
        {[pair.project_a, pair.project_b].map((project, index) => <article className="pairwise-choice" key={project.id}><span className="eyebrow">OPTION {index === 0 ? "A" : "B"}</span><h2>{project.title}</h2><p>{project.summary}</p><button type="button" className="button button--primary" onClick={() => void choose(project.id)}>Choose {project.title}</button></article>)}
      </div>
    </Panel> : null}
    <Notice tone="quiet" title="Estimator">Bradley-Terry scores are computed from recorded pairwise preferences by the backend. The organizer ranking endpoint exposes the comparison count, relative score, and recovered rank.</Notice>
  </>;
}

export function OrganizerPlatformPage() {
  const { token } = useAuth();
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [eventId, setEventId] = useState("");
  const [webhooks, setWebhooks] = useState<Array<{ id: number; event_id: number | null; url: string; active: boolean; created_at: string }>>([]);
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [duplicates, setDuplicates] = useState<Array<{ type: string; fingerprint: string; project_ids: number[] }>>([]);
  const [pairwise, setPairwise] = useState<{ event_id: number; method: string; comparisons: number; rankings: Array<{ project_id: number; project_title: string; bt_score: number; relative_score: number; rank: number }> } | null>(null);
  const [community, setCommunity] = useState<CommunityConfig | null>(null);
  const [voteStart, setVoteStart] = useState("");
  const [voteEnd, setVoteEnd] = useState("");
  const [maxVotes, setMaxVotes] = useState(5);
  const [hidden, setHidden] = useState(true);
  const [selectedJudge, setSelectedJudge] = useState("");
  const [judges, setJudges] = useState<Array<{ id: string; name: string }>>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    if (!token) throw new Error("Your session has expired.");
    const [eventList, hooks, judgeList] = await Promise.all([getEvents(), getWebhooks(token), getJudges(token)]);
    const first = chooseDefaultEvent(eventList);
    return { eventList, first, hooks, judgeList };
  }, [token]);
  const resource = useAsyncResource(load);
  useEffect(() => {
    if (resource.status !== "ready") return;
    const first = resource.data.first;
    setEvents(resource.data.eventList);
    setEventId(first?.id ?? "");
    setWebhooks(resource.data.hooks);
    setJudges(resource.data.judgeList.map((judge) => ({ id: judge.id, name: judge.name })));
    setSelectedJudge(resource.data.judgeList[0]?.id ?? "");
  }, [resource.status, resource.status === "ready" ? resource.data : null]);
  useEffect(() => {
    if (!token || !eventId) return;
    void getCommunityConfig(eventId, token).then((cfg) => {
      setCommunity(cfg);
      setVoteStart(cfg.voting_start.slice(0, 16));
      setVoteEnd(cfg.voting_end.slice(0, 16));
      setMaxVotes(cfg.max_votes_per_user);
      setHidden(cfg.results_hidden_until_close);
    }).catch(() => { setCommunity(null); });
  }, [token, eventId]);

  async function addHook() {
    if (!token || !eventId || !url.trim() || !secret.trim()) return;
    setBusy(true); setMessage("");
    try { await createWebhook(token, eventId, url.trim(), secret.trim()); setWebhooks(await getWebhooks(token)); setUrl(""); setSecret(""); setMessage("Webhook registered."); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "Webhook creation failed."); }
    finally { setBusy(false); }
  }
  async function removeHook(id: number) { if (!token) return; await deleteWebhook(token, id); setWebhooks(await getWebhooks(token)); }
  async function scanDuplicates() { if (!token || !eventId) return; const result = await getDuplicateScan(token, eventId); setDuplicates(result.groups); }
  async function saveCommunity() {
    if (!token || !eventId || !voteStart || !voteEnd) return;
    setBusy(true); setMessage("");
    try {
      const start = new Date(voteStart).toISOString(); const end = new Date(voteEnd).toISOString();
      const cfg = await configureCommunityVoting(token, { event_id: eventId, voting_start: start, voting_end: end, results_hidden_until_close: hidden, max_votes_per_user: maxVotes, active: true });
      setCommunity(cfg); setMessage("Community voting configuration saved.");
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Voting configuration failed."); }
    finally { setBusy(false); }
  }
  async function loadPairwise() {
    if (!token || !eventId) return;
    try { setPairwise(await getPairwiseRanking(eventId, token)); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "Pairwise ranking unavailable."); }
  }

  return <>
    <FixtureBanner />
    <PageHeader eyebrow="ORGANIZER / T4 OPERATIONS" title="Platform operations" description="Community controls, pairwise recovery, webhooks, integrity scans, signed judge records, certificates, embeds, and bulk data paths." />
    {resource.status === "loading" ? <StatePanel variant="loading" title="Loading platform controls" description="Reading local event, judge, and webhook configuration." /> : null}
    {resource.status === "error" ? <StatePanel variant="error" title="Platform controls unavailable" description={resource.error} actionLabel="Retry" onAction={resource.reload} /> : null}
    {resource.status === "ready" ? <>
      <div className="metric-grid metric-grid--four"><MetricCard label="Events" value={events.length} note="Local event records" /><MetricCard label="Webhooks" value={webhooks.length} note="Signed event delivery endpoints" accent="mint" /><MetricCard label="Pairwise" value={pairwise?.comparisons ?? 0} note="Recorded comparisons" accent="blue" /><MetricCard label="Signed records" value="Ed25519" note="Public verification key available" accent="coral" /></div>
      {message ? <Notice tone={message.includes("failed") || message.includes("unavailable") ? "amber" : "mint"} title="Platform update">{message}</Notice> : null}
      <div className="content-grid content-grid--two">
        <Panel title="Community voting controls" description="The organizer chooses the voting window, result visibility policy, and per-account allowance.">
          <label className="field"><span>Event</span><select value={eventId} onChange={(e) => setEventId(e.target.value)}>{events.map((event) => <option value={event.id} key={event.id}>{event.name} · #{event.id}</option>)}</select></label>
          <div className="form-grid"><label className="field"><span>Voting start</span><input type="datetime-local" value={voteStart} onChange={(e) => setVoteStart(e.target.value)} /></label><label className="field"><span>Voting end</span><input type="datetime-local" value={voteEnd} onChange={(e) => setVoteEnd(e.target.value)} /></label></div>
          <label className="field"><span>Max votes per participant</span><input type="number" min="1" max="100" value={maxVotes} onChange={(e) => setMaxVotes(Number(e.target.value))} /></label>
          <label className="check-field"><input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} /><span>Hide community results until voting closes</span></label>
          <button type="button" className="button button--primary" disabled={busy || !eventId} onClick={() => void saveCommunity()}>{busy ? "Saving…" : community ? "Save voting policy" : "Create voting policy"}</button>
          {community ? <div className="mini-stats"><span>Status <strong>{community.active ? "Active" : "Off"}</strong></span><span>Limit <strong>{community.max_votes_per_user}</strong></span><span>Hidden <strong>{community.results_hidden_until_close ? "Yes" : "No"}</strong></span></div> : null}
        </Panel>
        <Panel title="Pairwise ranking" description="Recover a Bradley-Terry ranking from the pairwise preference records collected by judges.">
          <button type="button" className="button button--quiet" onClick={() => void loadPairwise()}>Refresh pairwise ranking</button>
          {pairwise ? <><div className="mini-stats"><span>Comparisons <strong>{pairwise.comparisons}</strong></span><span>Estimator <strong>{pairwise.method}</strong></span></div><div className="compact-list" style={{ marginTop: "1rem" }}>{pairwise.rankings.slice(0, 8).map((row) => <div className="compact-row" key={row.project_id}><div><strong>#{row.rank} {row.project_title}</strong><small>Relative strength {row.relative_score}</small></div><span>{row.bt_score.toFixed(3)}</span></div>)}</div></> : <div className="empty-inline">No pairwise ranking has been loaded.</div>}
        </Panel>
      </div>
      <div className="content-grid content-grid--two">
        <Panel title="Webhook delivery" description="Event-scoped webhook endpoints receive signed JSON when supported actions occur.">
          <label className="field"><span>Endpoint URL</span><input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://localhost:9000/hooks/dogfood" /></label>
          <label className="field"><span>Signing secret</span><input value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="minimum 8 characters" /></label>
          <button type="button" className="button button--primary" disabled={busy || !url || !secret} onClick={() => void addHook()}>{busy ? "Saving…" : "Add webhook"}</button>
          {webhooks.length ? <div className="compact-list" style={{ marginTop: "1.2rem" }}>{webhooks.map((hook) => <div className="compact-row" key={hook.id}><div><strong>{hook.url}</strong><small>{hook.event_id ? `Event #${hook.event_id}` : "All events"}</small></div><button type="button" className="text-button text-button--danger" onClick={() => void removeHook(hook.id)}>Remove</button></div>)}</div> : <div className="empty-inline" style={{ marginTop: "1rem" }}>No webhooks configured.</div>}
        </Panel>
        <Panel title="Submission integrity" description="Repository/title fingerprint scan gives organizers a concrete duplicate-signal report.">
          <button type="button" className="button button--quiet" onClick={() => void scanDuplicates()}>Run duplicate scan</button>
          {duplicates.length ? duplicates.map((group, index) => <div className="warning-row" key={`${group.type}-${index}`}><strong>{group.type}</strong><span>Projects {group.project_ids.join(", ")}</span></div>) : <div className="empty-inline" style={{ marginTop: "1rem" }}>No duplicate groups detected by the current fingerprints.</div>}
        </Panel>
      </div>
      <Panel title="Signed records, certificates, and export" description="Generated entirely by the local API. No cloud account is required.">
        <div className="form-grid"><label className="field"><span>Judge</span><select value={selectedJudge} onChange={(e) => setSelectedJudge(e.target.value)}>{judges.map((judge) => <option key={judge.id} value={judge.id}>{judge.name} · #{judge.id}</option>)}</select></label><div className="field"><span>Event</span><div className="static-field">#{eventId}</div></div></div>
        <div className="link-grid">
          {eventId && selectedJudge ? <a className="operation-link" href={apiUrl(endpoints.platform.judgeRecord(selectedJudge, eventId))} target="_blank" rel="noreferrer">Signed judge record<span>JSON record + signature</span></a> : null}
          {eventId && selectedJudge ? <a className="operation-link" href={apiUrl(endpoints.platform.judgeCertificate(selectedJudge, eventId))} target="_blank" rel="noreferrer">Judge certificate<span>Generated printable certificate</span></a> : null}
          <a className="operation-link" href={apiUrl(endpoints.platform.publicKey)} target="_blank" rel="noreferrer">Verification key<span>Ed25519 public key</span></a>
          {eventId ? <a className="operation-link" href={apiUrl(endpoints.platform.projectsExport(eventId))} target="_blank" rel="noreferrer">Projects CSV<span>Bulk export project records</span></a> : null}
          {eventId ? <a className="operation-link" href={apiUrl("/api/embed/gallery?event_id=" + encodeURIComponent(eventId))} target="_blank" rel="noreferrer">Gallery embed<span>Standalone HTML widget</span></a> : null}
        </div>
      </Panel>
      <Panel title="Bulk import" description="Teams can be imported from a CSV with name and participant_email columns." action={<StatusBadge tone="blue">CSV</StatusBadge>}>
        <p className="panel-footnote">Endpoint: POST /api/system/import/teams.csv?event_id=&lt;id&gt; with a CSV file. Only existing participant accounts are imported; missing participant accounts are reported in the response instead of being created implicitly.</p>
      </Panel>
    </> : null}
  </>;
}
