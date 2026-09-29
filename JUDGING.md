# Judging

## Assignment

Organizers can create judge invitations and assign submitted projects with `round_robin` or `all` strategies. The backend stores one assignment per judge/project pair.

## Rubric

A rubric has named criteria, a configurable weight per criterion, and a configurable maximum score. Weights must total exactly 100%. Once scoring has started, the existing rubric cannot be destructively replaced because score rows reference its criteria.

## Score isolation

A judge's score endpoint resolves the judge from the authenticated user and returns only that judge's own scores. Organizer/admin access is a separate route. A participant is denied access to judge scores. This is backend-enforced and is the key T2 isolation boundary.

## Normalization

The backend first computes each completed evaluation as a weighted 0–5 score. For a judge with at least two completed project evaluations and non-zero variance, the service uses:

`normalized = panel_mean + ((judge_score - judge_mean) / judge_std) * panel_std`

The result is clamped to 0–5. Judges with insufficient history keep their raw score; judges with zero variance are handled conservatively using the panel mean. The response exposes the method, panel distribution, judge mean/std, raw/normalized values, notes, and rank movement.

The intent is to reduce systematic differences in scoring scale while preserving relative differences within a judge's completed evaluations. It is a calibration policy with explicit edge cases, not a guarantee of statistical fairness.

## Pairwise mode

Judges compare two assigned projects at a time. The backend stores only the pair and winner. Organizers can recover a relative ranking with a Bradley-Terry MM estimator at `/api/pairwise/ranking`.

## T3 public judging controls

Community voting is configured per event with a voting start/end, maximum votes per participant, and a results-hidden policy. The ballot ordering is HMAC-derived from the authenticated participant ID and project ID so the order is randomized per user but stable for one session. The database rejects duplicate participant/project ballots. A short-window address hash rate limit provides another abuse signal.
