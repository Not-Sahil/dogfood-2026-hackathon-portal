"use client";

import { useCallback, useState } from "react";
import { FixtureBanner } from "@/components/ui/FixtureBanner";
import { MetricCard } from "@/components/ui/MetricCard";
import { Notice } from "@/components/ui/Notice";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatePanel } from "@/components/ui/StatePanel";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/features/auth/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { downloadTextFile } from "@/lib/api/download";
import { getProgress, getResultsBundle, exportResults } from "@/lib/api/portal";
import { listEventRecords } from "@/lib/api/organizer";
import type { EventRecord, ResultsBundle, ReviewProgress } from "@/types/portal";

async function settle<T>(promise: Promise<T>): Promise<{ data: T | null; error: string }> {
  try { return { data: await promise, error: "" }; }
  catch (reason) { return { data: null, error: reason instanceof Error ? reason.message : "The API request failed." }; }
}

interface ResultsLoad {
  events: EventRecord[];
  bundle: ResultsBundle;
  progress: ReviewProgress;
}

const number = (value: number | null, decimals = 2) => value === null ? "—" : value.toFixed(decimals);

export function OrganizerResultsPage() {
  const { token } = useAuth();
  const [selectedEventId, setSelectedEventId] = useState<string>("");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");

  const load = useCallback(async (): Promise<ResultsLoad> => {
    if (!token) throw new Error("Your session has expired.");
    const [events, bundle, progress] = await Promise.all([
      listEventRecords(token),
      getResultsBundle(token),
      getProgress(token),
    ]);
    return { events, bundle, progress };
  }, [token]);

  const resource = useAsyncResource(load);

  async function changeEvent(eventId: string) {
    if (!token || resource.status !== "ready" || !eventId) return;
    try {
      const bundle = await getResultsBundle(token, eventId);
      resource.setData({ ...resource.data, bundle });
      setSelectedEventId(eventId);
    } catch (reason) {
      setExportError(reason instanceof Error ? reason.message : "Could not load results for that event.");
    }
  }

  async function download() {
    setExporting(true);
    setExportError("");
    try {
      if (!token || resource.status !== "ready") throw new Error("Your session has expired.");
      const csv = await exportResults(token, selectedEventId || resource.data.bundle.eventId);
      downloadTextFile(`dogfood-results-event-${selectedEventId || resource.data.bundle.eventId}.csv`, csv);
    } catch (reason) {
      setExportError(reason instanceof Error ? reason.message : "CSV export failed.");
    } finally {
      setExporting(false);
    }
  }

  if (resource.status === "loading") return <><FixtureBanner /><PageHeader eyebrow="ORGANIZER / OUTCOMES" title="Results" description="Rankings and CSV export from the backend." /><StatePanel variant="loading" title="Loading results" description="Retrieving rankings and judging progress." /></>;
  if (resource.status === "error") return <><FixtureBanner /><PageHeader eyebrow="ORGANIZER / OUTCOMES" title="Results" /><StatePanel variant="error" title="Results unavailable" description={resource.error} actionLabel="Retry" onAction={resource.reload} /></>;

  const { bundle, progress, events } = resource.data;
  const results = bundle.results;
  const meanValues = results.filter((row) => row.rawScore !== null).map((row) => row.rawScore as number);
  const mean = meanValues.length ? meanValues.reduce((sum, score) => sum + score, 0) / meanValues.length : null;
  const rankedCount = results.filter((row) => row.rankAfter !== null).length;
  const currentEventId = selectedEventId || bundle.eventId;

  return <>
    <FixtureBanner />
    <PageHeader
      eyebrow="ORGANIZER / OUTCOMES"
      title="Results"
      description="Raw and normalized rankings returned by the backend, with the event context used for the calculation."
      actions={<button type="button" className="button button--primary" onClick={() => void download()} disabled={exporting}>{exporting ? "Preparing CSV…" : "Export CSV ↓"}</button>}
    />

    <div className="content-grid content-grid--two">
      <Panel title="Results event" description="Results are calculated for one event at a time.">
        <label className="field">
          <span>Event</span>
          <select value={currentEventId} onChange={(event) => void changeEvent(event.target.value)}>
            {events.map((event) => <option key={event.id} value={event.id}>{event.name} · #{event.id}</option>)}
          </select>
        </label>
        <div className="mini-stats">
          <span>Panel mean <strong>{bundle.normalization.panelMean.toFixed(3)}</strong></span>
          <span>Panel std <strong>{bundle.normalization.panelStd.toFixed(3)}</strong></span>
          <span>Incomplete projects <strong>{bundle.integrity.projectsWithIncompleteReviews}</strong></span>
        </div>
      </Panel>
      <Panel title="Normalization method" description="This text comes from the backend results response.">
        <div className="normalization-status">
          <StatusBadge tone="blue">Backend supplied</StatusBadge>
          <strong>{bundle.normalization.method}</strong>
          <p>{bundle.normalization.explanation}</p>
          <small>Scale: {bundle.normalization.scale}</small>
        </div>
      </Panel>
    </div>

    {exportError ? <div className="form-error" role="alert">{exportError}</div> : null}

    <div className="metric-grid metric-grid--four">
      <MetricCard label="Ranked projects" value={rankedCount} note={`${results.length} submitted projects returned`} />
      <MetricCard label="Average raw score" value={mean === null ? "—" : mean.toFixed(2)} note="From completed backend evaluations" accent="mint" />
      <MetricCard label="Reviews" value={`${bundle.integrity.completedReviews}/${bundle.integrity.totalReviews}`} note={`${bundle.integrity.pendingReviews} pending`} accent="amber" />
      <MetricCard label="Judge anomalies" value={bundle.integrity.judgeAnomalies} note="Backend integrity flags" accent="coral" />
    </div>

    <Panel title="Project rankings" description="Raw and normalized ranks remain separate so the ranking change is auditable.">
      {!results.length ? <StatePanel variant="empty" title="No submitted projects" description="The selected event has no submitted projects in the results response." /> : <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Raw rank</th><th>Normalized</th><th>Project</th><th>Team</th><th>Track</th><th>Raw score</th><th>Normalized score</th><th>Reviews</th></tr></thead><tbody>{results.map((result) => <tr key={result.projectId}><td>{result.rankBefore ? <strong className="rank-number">#{result.rankBefore}</strong> : "—"}</td><td>{result.rankAfter ? <strong className="rank-number">#{result.rankAfter}</strong> : "—"}</td><td><strong>{result.projectTitle}</strong></td><td>{result.team}</td><td>{result.track}</td><td>{number(result.rawScore)}</td><td>{number(result.normalizedScore)}</td><td>{result.reviewCount}/{result.assignedReviews ?? result.reviewCount}</td></tr>)}</tbody></table></div>}
    </Panel>

    <Panel title="Judging completion" description="Progress is aggregated from the backend judge-progress endpoint and assignment records.">
      <ProgressBar value={progress.completedReviews} max={progress.totalReviews} label="Overall review completion" />
      <div className="mini-stats"><span>Completed <strong>{progress.completedReviews}</strong></span><span>Pending <strong>{progress.pendingReviews}</strong></span><span>Projects complete <strong>{progress.completedProjects}/{progress.assignedProjects || "—"}</strong></span></div>
    </Panel>

    <Notice tone="quiet" title="Score provenance">The browser does not recalculate rankings or normalization. It only renders the backend result bundle and the audit-facing fields it returns.</Notice>
  </>;
}

export function OrganizerIntegrityPage() {
  const { token } = useAuth();
  const load = useCallback(async () => {
    if (!token) throw new Error("Your session has expired.");
    const [results, progress] = await Promise.all([settle(getResultsBundle(token)), settle(getProgress(token))]);
    return { results, progress };
  }, [token]);
  const resource = useAsyncResource(load);

  if (resource.status === "loading") return <><FixtureBanner /><PageHeader eyebrow="ORGANIZER / INTEGRITY" title="Judging integrity" description="Coverage, assignment distribution, and normalization transparency." /><StatePanel variant="loading" title="Loading integrity data" description="Fetching review counts and normalization data." /></>;
  if (resource.status === "error") return <><FixtureBanner /><PageHeader eyebrow="ORGANIZER / INTEGRITY" title="Judging integrity" /><StatePanel variant="error" title="Integrity data unavailable" description={resource.error} actionLabel="Retry" onAction={resource.reload} /></>;

  const progress = resource.data.progress.data;
  const bundle = resource.data.results.data;
  const errors = [resource.data.results.error, resource.data.progress.error].filter(Boolean);

  return <>
    <FixtureBanner />
    <PageHeader eyebrow="ORGANIZER / T2" title="Judging integrity" description="Coverage, reviewer distribution, anomalies, and normalization transparency from the backend." />
    {errors.length ? <Notice tone="amber" title="Integrity API data is partial">{[...new Set(errors)].join(" · ")}</Notice> : null}
    {bundle ? <>
      <div className="metric-grid metric-grid--four"><MetricCard label="Total reviews" value={bundle.integrity.totalReviews} note="Assigned review records" /><MetricCard label="Completed" value={bundle.integrity.completedReviews} note={`${bundle.integrity.totalReviews ? Math.round(bundle.integrity.completedReviews / bundle.integrity.totalReviews * 100) : 0}%`} accent="mint" /><MetricCard label="Pending" value={bundle.integrity.pendingReviews} note="Awaiting judge submission" accent="amber" /><MetricCard label="Judge anomalies" value={bundle.integrity.judgeAnomalies} note="Backend flags" accent="coral" /></div>
      <div className="content-grid content-grid--two"><Panel title="Normalization status" description="Method and distribution values supplied by the result endpoint."><div className="normalization-status"><StatusBadge tone="blue">Backend supplied</StatusBadge><strong>{bundle.normalization.method}</strong><p>{bundle.normalization.explanation}</p><small>Panel mean {bundle.normalization.panelMean.toFixed(3)} · std {bundle.normalization.panelStd.toFixed(3)}</small></div></Panel><Panel title="Review completion" description="Aggregated assignment progress.">{progress ? <><ProgressBar value={progress.completedReviews} max={progress.totalReviews} label="Reviews completed" showPercent={false} /><div className="mini-stats"><span>Pending <strong>{progress.pendingReviews}</strong></span><span>Projects complete <strong>{progress.completedProjects}/{progress.assignedProjects || "—"}</strong></span></div></> : <div className="empty-inline">Progress unavailable.</div>}</Panel></div>
      <Panel title="Judge distribution" description="Assigned and completed reviews for each judge, returned by the backend.">{progress?.judgeDistribution.length ? <div className="distribution-list">{progress.judgeDistribution.map((judge) => <div className="distribution-row" key={judge.judgeName}><span className="distribution-row__name">{judge.judgeName}</span><div className="distribution-row__bar"><ProgressBar value={judge.completed} max={judge.assigned} label={`${judge.completed} of ${judge.assigned} reviews`} showPercent={false} /></div><StatusBadge tone={judge.completed >= judge.assigned ? "mint" : "amber"}>{`${judge.completed}/${judge.assigned}`}</StatusBadge></div>)}</div> : <div className="empty-inline">No judge distribution returned.</div>}</Panel>
      {bundle.results.length ? <Panel title="Normalization breakdown" description="Each row exposes judge-level raw and normalized values when the backend has a completed evaluation."><div className="integrity-result-list">{bundle.results.map((result) => <details className="integrity-result" key={result.projectId}><summary><span><strong>{result.projectTitle}</strong><small>{result.team} · {result.track}</small></span><span className="integrity-scores"><span>Raw <strong>{number(result.rawScore)}</strong></span><span>Normalized <strong>{number(result.normalizedScore)}</strong></span></span><span className="rank-change">{result.rankBefore === null || result.rankAfter === null ? "Rank change unavailable" : `#${result.rankBefore} → #${result.rankAfter}`}</span></summary><div className="integrity-explanation">{result.explanation ?? "The backend did not supply a row-level explanation."}{result.judgeBreakdown?.length ? <div className="compact-list" style={{ marginTop: "1rem" }}>{result.judgeBreakdown.map((judge) => <div className="compact-row" key={`${result.projectId}-${judge.judgeId}`}><div><strong>{judge.judgeName}</strong><small>{judge.note ?? "No judge-specific note"}</small></div><span>{number(judge.rawScore)} → {number(judge.normalizedScore)}</span></div>)}</div> : null}</div></details>)}</div></Panel> : null}
    </> : <StatePanel variant="empty" title="No results bundle" description="The selected event has not produced a results response yet." />}
    <Notice tone="quiet" title="Score provenance">The frontend does not calculate normalized scores. It renders the backend result and integrity fields exactly as returned.</Notice>
  </>;
}
