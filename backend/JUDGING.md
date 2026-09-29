# Judging

## Assignment

The backend supports manual all-to-selected assignment and simple round-robin assignment.

## Scoring

Rubrics have configurable criteria. Criterion weights must total 100%. Each criterion uses a configurable maximum score, default 5.

## Cross-judge normalization

Each completed judge/project evaluation first produces a weighted score on a 0-5 scale. For each judge, the mean and standard deviation of that judge's completed project scores are calculated. Scores are converted to z-scores and mapped onto the panel distribution. Constant-score judges are handled explicitly by neutralizing their contribution to the panel mean instead of dividing by zero.

## Transparency

Results expose raw score, normalized score, rank before/after normalization, rank change, judge-level breakdown, judge mean/std, and notes for scoring-pattern anomalies.

This method is intentionally visible to organizers and should be backed by fixture-based examples in the final write-up.
