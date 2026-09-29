# Normalization Proof

The normalization bonus is implemented as a separate backend result path rather than a frontend-only visual.

The result bundle exposes:

- raw project score
- normalized project score
- raw rank
- normalized rank
- rank change
- panel mean/std
- per-judge raw score
- per-judge normalized score
- per-judge mean/std and edge-case notes

Use:

```text
GET /api/normalization/proof?event_id=<id>
```

The endpoint returns only values calculated by the backend and highlights projects where normalization changed the score or rank.
