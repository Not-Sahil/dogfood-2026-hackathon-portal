# Pairwise Mode

Pairwise judging is an optional second judging methodology.

A judge requests an unreviewed pair:

```text
GET /api/pairwise/next?event_id=<id>
```

The judge records the winner:

```text
POST /api/pairwise/vote
{
  "event_id": 1,
  "project_a_id": 10,
  "project_b_id": 11,
  "winner_id": 10
}
```

Organizers recover a ranking:

```text
GET /api/pairwise/ranking?event_id=<id>
```

The backend uses a Bradley-Terry MM estimator and returns the number of comparisons, relative strength, and rank per project.
