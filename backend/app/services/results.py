from collections import defaultdict
from math import sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models.event import Event
from app.db.models.judge import Judge, JudgeAssignment
from app.db.models.project import Project, ProjectStatus
from app.db.models.project_judging import Criterion, Rubric, Score


NORMALIZATION_METHOD = (
    "Per-judge z-score calibration to the panel distribution"
)

NORMALIZATION_SCALE = "0-5 weighted judging scale"

NORMALIZATION_EXPLANATION = (
    "Each completed judge evaluation is first converted to the "
    "rubric's weighted 0-5 score. For judges with sufficient "
    "history, the score is standardized using that judge's mean "
    "and standard deviation, then mapped onto the panel mean and "
    "standard deviation. This reduces systematic harsh/generous "
    "scoring differences while preserving relative differences "
    "between projects. Judges with insufficient history are not "
    "aggressively calibrated."
)


def _active_rubric(
    db: Session,
    event_id: int,
) -> Rubric | None:

    return db.scalar(
        select(Rubric)
        .options(
            joinedload(Rubric.criteria)
        )
        .where(
            Rubric.event_id == event_id,
            Rubric.active.is_(True),
        )
        .order_by(
            Rubric.id.desc()
        )
    )


def _evaluation_total(
    score_map: dict[int, Score],
    criteria: dict[int, Criterion],
) -> float | None:

    # Evaluation is incomplete.
    if set(score_map.keys()) != set(criteria.keys()):
        return None

    weighted_total = 0.0

    for criterion_id, criterion in criteria.items():

        score_record = score_map.get(
            criterion_id
        )

        if not score_record:
            return None

        score = score_record.score

        if score < 0 or score > criterion.max_score:
            return None

        normalized_criterion_score = (
            score / criterion.max_score
        )

        weighted_total += (
            normalized_criterion_score
            * criterion.weight
        )

    # Convert 0-100 weighted percentage to 0-5.
    final_score = (
        weighted_total / 100.0
    ) * 5.0

    return round(final_score, 4)


def _mean(values: list[float]) -> float:

    if not values:
        return 0.0

    return sum(values) / len(values)


def _population_std(
    values: list[float],
    mean: float,
) -> float:

    if not values:
        return 0.0

    variance = sum(
        (value - mean) ** 2
        for value in values
    ) / len(values)

    return sqrt(variance)


def _clamp_score(
    value: float,
) -> float:

    return round(
        max(
            0.0,
            min(
                5.0,
                value,
            ),
        ),
        4,
    )


def build_results(
    db: Session,
    event_id: int,
) -> dict:

    # ---------------------------------------------------------
    # Event
    # ---------------------------------------------------------

    event = db.get(
        Event,
        event_id,
    )

    if not event:
        raise ValueError(
            "Event not found"
        )

    # ---------------------------------------------------------
    # Active rubric
    # ---------------------------------------------------------

    rubric = _active_rubric(
        db,
        event_id,
    )

    if not rubric or not rubric.criteria:
        raise ValueError(
            "Active rubric not configured"
        )

    criteria = {
        criterion.id: criterion
        for criterion in rubric.criteria
    }

    # ---------------------------------------------------------
    # Submitted projects
    # ---------------------------------------------------------

    projects = db.scalars(
        select(Project)
        .options(
            joinedload(Project.team),
            joinedload(Project.track),
        )
        .where(
            Project.event_id == event_id,
            Project.status == ProjectStatus.SUBMITTED,
        )
        .order_by(
            Project.id
        )
    ).all()

    if not projects:
        return {
            "event_id": event_id,
            "normalization": {
                "method": NORMALIZATION_METHOD,
                "scale": NORMALIZATION_SCALE,
                "panel_mean": 0.0,
                "panel_std": 0.0,
                "explanation": NORMALIZATION_EXPLANATION,
            },
            "rows": [],
            "integrity": {
                "total_reviews": 0,
                "completed_reviews": 0,
                "pending_reviews": 0,
                "judge_anomalies": 0,
                "projects_with_incomplete_reviews": 0,
            },
        }

    project_ids = {
        project.id
        for project in projects
    }

    # ---------------------------------------------------------
    # Judge assignments
    # ---------------------------------------------------------

    assignments = db.scalars(
        select(JudgeAssignment)
        .options(
            joinedload(
                JudgeAssignment.judge
            ).joinedload(
                Judge.user
            )
        )
        .join(
            JudgeAssignment.project
        )
        .where(
            Project.event_id == event_id
        )
    ).all()

    assigned_by_project: dict[
        int,
        list[Judge]
    ] = defaultdict(list)

    judges: dict[
        int,
        Judge
    ] = {}

    for assignment in assignments:

        if assignment.project_id not in project_ids:
            continue

        assigned_by_project[
            assignment.project_id
        ].append(
            assignment.judge
        )

        judges[
            assignment.judge.id
        ] = assignment.judge

    # ---------------------------------------------------------
    # Scores
    # ---------------------------------------------------------

    raw_scores = db.scalars(
        select(Score)
        .options(
            joinedload(
                Score.judge
            ).joinedload(
                Judge.user
            )
        )
        .where(
            Score.project_id.in_(
                project_ids
            )
        )
    ).all()

    # (judge_id, project_id) -> criterion_id -> Score
    by_evaluation: dict[
        tuple[int, int],
        dict[int, Score]
    ] = defaultdict(dict)

    for score in raw_scores:

        if score.criterion_id not in criteria:
            continue

        if score.project_id not in project_ids:
            continue

        by_evaluation[
            (
                score.judge_id,
                score.project_id,
            )
        ][
            score.criterion_id
        ] = score

    # ---------------------------------------------------------
    # Completed evaluation totals
    # ---------------------------------------------------------

    evaluation_totals: dict[
        tuple[int, int],
        float
    ] = {}

    for key, score_map in by_evaluation.items():

        total = _evaluation_total(
            score_map,
            criteria,
        )

        if total is not None:
            evaluation_totals[key] = total

    # ---------------------------------------------------------
    # Per-judge statistics
    # ---------------------------------------------------------

    judge_values: dict[
        int,
        list[float]
    ] = defaultdict(list)

    for (
        judge_id,
        _project_id,
    ), value in evaluation_totals.items():

        judge_values[
            judge_id
        ].append(value)

    panel_values = list(
        evaluation_totals.values()
    )

    panel_mean = _mean(
        panel_values
    )

    panel_std = _population_std(
        panel_values,
        panel_mean,
    )

    judge_stats: dict[
        int,
        tuple[float, float]
    ] = {}

    anomaly_flags: dict[
        int,
        str
    ] = {}

    for judge_id, values in judge_values.items():

        mean = _mean(values)

        std = _population_std(
            values,
            mean,
        )

        judge_stats[
            judge_id
        ] = (
            mean,
            std,
        )

        # Don't call a judge anomalous from only one/two
        # evaluations. We need enough observations.
        if len(values) >= 3:

            if std < 1e-8:

                anomaly_flags[
                    judge_id
                ] = (
                    "constant scoring pattern"
                )

            elif (
                panel_values
                and abs(
                    mean - panel_mean
                )
                >= max(
                    panel_std,
                    0.25,
                )
            ):

                direction = (
                    "above"
                    if mean > panel_mean
                    else "below"
                )

                anomaly_flags[
                    judge_id
                ] = (
                    f"mean score {direction} "
                    "panel average"
                )

    # ---------------------------------------------------------
    # Project scores
    # ---------------------------------------------------------

    raw_by_project: dict[
        int,
        list[tuple[int, float]]
    ] = defaultdict(list)

    normalized_by_project: dict[
        int,
        list[tuple[int, float]]
    ] = defaultdict(list)

    breakdown_by_project: dict[
        int,
        list[dict]
    ] = defaultdict(list)

    # ---------------------------------------------------------
    # Normalize every assigned judge/project evaluation
    # ---------------------------------------------------------

    for project in projects:

        assigned_judges = (
            assigned_by_project.get(
                project.id,
                [],
            )
        )

        for judge in assigned_judges:

            key = (
                judge.id,
                project.id,
            )

            raw = evaluation_totals.get(
                key
            )

            mean, std = judge_stats.get(
                judge.id,
                (None, None),
            )

            normalized = None
            note = None

            if raw is None:

                note = (
                    "review pending or incomplete"
                )

            elif mean is None or std is None:

                # No judge history.
                normalized = raw

                note = (
                    "insufficient judge history; "
                    "raw score retained"
                )

            elif len(
                judge_values.get(
                    judge.id,
                    [],
                )
            ) < 2:

                # A single review is not enough to estimate
                # a judge's scoring tendency.
                normalized = raw

                note = (
                    "insufficient judge history; "
                    "raw score retained"
                )

            elif std < 1e-8:

                # A constant-scoring judge cannot be
                # z-normalized because division by zero
                # would occur.
                normalized = panel_mean

                note = (
                    "constant scoring pattern "
                    "neutralized to panel mean"
                )

            elif panel_std < 1e-8:

                # Panel has effectively no variation.
                normalized = raw

                note = (
                    "panel variance too low; "
                    "raw score retained"
                )

            else:

                z_score = (
                    raw - mean
                ) / std

                normalized = (
                    panel_mean
                    + (
                        z_score
                        * panel_std
                    )
                )

                normalized = _clamp_score(
                    normalized
                )

                if judge.id in anomaly_flags:
                    note = anomaly_flags[
                        judge.id
                    ]

            if raw is not None:

                raw_by_project[
                    project.id
                ].append(
                    (
                        judge.id,
                        raw,
                    )
                )

            if normalized is not None:

                normalized_by_project[
                    project.id
                ].append(
                    (
                        judge.id,
                        normalized,
                    )
                )

            breakdown_by_project[
                project.id
            ].append(
                {
                    "judge_id": judge.id,
                    "judge_name": judge.user.name,
                    "raw_score": (
                        round(raw, 4)
                        if raw is not None
                        else None
                    ),
                    "normalized_score": (
                        round(
                            normalized,
                            4,
                        )
                        if normalized is not None
                        else None
                    ),
                    "judge_mean": (
                        round(mean, 4)
                        if mean is not None
                        else None
                    ),
                    "judge_std": (
                        round(std, 4)
                        if std is not None
                        else None
                    ),
                    "note": note,
                }
            )

    # ---------------------------------------------------------
    # Aggregate project scores
    # ---------------------------------------------------------

    raw_project_score: dict[
        int,
        float
    ] = {}

    normalized_project_score: dict[
        int,
        float
    ] = {}

    for project_id, values in raw_by_project.items():

        if values:

            raw_project_score[
                project_id
            ] = round(
                sum(
                    value
                    for _judge_id, value in values
                )
                / len(values),
                4,
            )

    for project_id, values in normalized_by_project.items():

        if values:

            normalized_project_score[
                project_id
            ] = round(
                sum(
                    value
                    for _judge_id, value in values
                )
                / len(values),
                4,
            )

    # ---------------------------------------------------------
    # Ranking
    # ---------------------------------------------------------

    # Only projects with completed evaluations receive
    # an actual rank.
    raw_ranked = sorted(
        raw_project_score.keys(),
        key=lambda project_id: (
            -raw_project_score[project_id],
            project_id,
        ),
    )

    normalized_ranked = sorted(
        normalized_project_score.keys(),
        key=lambda project_id: (
            -normalized_project_score[
                project_id
            ],
            project_id,
        ),
    )

    raw_rank = {
        project_id: index + 1
        for index, project_id
        in enumerate(raw_ranked)
    }

    normalized_rank = {
        project_id: index + 1
        for index, project_id
        in enumerate(normalized_ranked)
    }

    # ---------------------------------------------------------
    # Final rows
    # ---------------------------------------------------------

    rows = []

    # Final output is ordered by normalized ranking.
    project_order = sorted(
        projects,
        key=lambda project: (
            normalized_rank.get(
                project.id,
                999999,
            ),
            -(
                normalized_project_score.get(
                    project.id,
                    -1,
                )
            ),
            project.id,
        ),
    )

    for project in project_order:

        assigned_count = len(
            assigned_by_project.get(
                project.id,
                [],
            )
        )

        completed_count = len(
            raw_by_project.get(
                project.id,
                [],
            )
        )

        raw_position = raw_rank.get(
            project.id
        )

        normalized_position = normalized_rank.get(
            project.id
        )

        rank_change = None

        if (
            raw_position is not None
            and normalized_position is not None
        ):
            rank_change = (
                raw_position
                - normalized_position
            )

        rows.append(
            {
                "rank_raw": raw_position,
                "rank_normalized": normalized_position,
                "project_id": project.id,
                "project_title": project.title,
                "team_name": project.team.name if project.team else None,
                "track_name": project.track.name if project.track else None,
                "raw_score": raw_project_score.get(
                    project.id
                ),
                "normalized_score": normalized_project_score.get(
                    project.id
                ),
                "completed_reviews": completed_count,
                "assigned_reviews": assigned_count,
                "rank_change": rank_change,
                "judge_breakdown": (
                    breakdown_by_project.get(
                        project.id,
                        [],
                    )
                ),
            }
        )

    # ---------------------------------------------------------
    # Integrity summary
    # ---------------------------------------------------------

    total_reviews = sum(
        len(values)
        for values
        in assigned_by_project.values()
    )

    completed_reviews = sum(
        len(values)
        for values
        in raw_by_project.values()
    )

    incomplete_projects = sum(
        1
        for project in projects
        if len(
            raw_by_project.get(
                project.id,
                [],
            )
        )
        < len(
            assigned_by_project.get(
                project.id,
                [],
            )
        )
    )

    return {
        "event_id": event_id,

        "normalization": {
            "method": NORMALIZATION_METHOD,
            "scale": NORMALIZATION_SCALE,
            "panel_mean": round(
                panel_mean,
                4,
            ),
            "panel_std": round(
                panel_std,
                4,
            ),
            "explanation": NORMALIZATION_EXPLANATION,
        },

        "rows": rows,

        "integrity": {
            "total_reviews": total_reviews,
            "completed_reviews": completed_reviews,
            "pending_reviews": (
                total_reviews
                - completed_reviews
            ),
            "judge_anomalies": len(
                anomaly_flags
            ),
            "projects_with_incomplete_reviews": (
                incomplete_projects
            ),
        },
    }