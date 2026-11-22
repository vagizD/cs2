"""Validate and identify a frozen SQLite snapshot."""

import hashlib
import sqlite3
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ml.config import Version
from ml.features import read_only, setup_source

REQUIRED_COLUMNS = {
    "team": {"team_id", "name"},
    "ranking_snapshot": {"snapshot_date", "team_id", "rank", "points"},
    "match": {"match_id", "datetime_utc", "team1_id", "team2_id",
              "team1_score", "team2_score", "format"},
    "event": {"event_id", "start_date", "end_date"},
    "map_result": {"map_stats_id", "match_id"},
    "player_map_stats": {"map_stats_id", "match_id", "player_id"},
}


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_version: Version
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    row_counts: dict[str, int]
    latest_match_utc: AwareDatetime
    latest_finalized_match_utc: AwareDatetime
    latest_ranking_date: date
    created_at: AwareDatetime
    gcs_uri: str | None = None
    gcs_generation: int | None = Field(default=None, gt=0)

    @property
    def inference_cutoff(self) -> datetime:
        ranking_cutoff = datetime.combine(self.latest_ranking_date, time.min, timezone.utc)
        return max(
            self.latest_finalized_match_utc + timedelta(seconds=1),
            ranking_cutoff + timedelta(days=1),
        )


def sha256_file(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def manifest_path(path: Path) -> Path:
    return path.with_name(path.name + ".manifest.json")


def inspect_snapshot(path: Path, version: str) -> Snapshot:
    wal = path.with_name(path.name + "-wal")
    if wal.is_file() and wal.stat().st_size:
        raise ValueError("Checkpoint the SQLite WAL before using the database as a snapshot.")
    digest = sha256_file(path)
    try:
        with closing(read_only(path)) as conn:
            if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite integrity check failed.")
            row_counts = {}
            for table, required in REQUIRED_COLUMNS.items():
                columns = {row[1] for row in conn.execute(f"PRAGMA main.table_info({table})")}
                if not required <= columns:
                    raise ValueError(f"Table {table} is missing columns: {sorted(required - columns)}")
                row_counts[table] = conn.execute(f"SELECT count(*) FROM main.{table}").fetchone()[0]
            setup_source(conn)
            latest = conn.execute("SELECT max(datetime_utc) FROM match_metadata").fetchone()[0]
            finalized = conn.execute("SELECT max(datetime_utc) FROM finalized_match").fetchone()[0]
            ranking = conn.execute("SELECT max(snapshot_date) FROM valid_ranking").fetchone()[0]
    except sqlite3.Error as exc:
        raise ValueError("Could not validate the SQLite snapshot.") from exc
    if not (latest and finalized and ranking):
        raise ValueError("The snapshot needs valid match results and rankings.")
    if sha256_file(path) != digest:
        raise ValueError("The snapshot changed while it was being validated.")
    return Snapshot(
        snapshot_version=version,
        sha256=digest,
        row_counts=row_counts,
        latest_match_utc=datetime.fromisoformat(latest).replace(tzinfo=timezone.utc),
        latest_finalized_match_utc=datetime.fromisoformat(finalized).replace(tzinfo=timezone.utc),
        latest_ranking_date=ranking,
        created_at=datetime.now(timezone.utc),
    )


def open_snapshot(path: Path, version: str) -> Snapshot:
    sidecar = manifest_path(path)
    if not sidecar.is_file():
        return inspect_snapshot(path, version)
    manifest = Snapshot.model_validate_json(sidecar.read_bytes())
    if manifest.snapshot_version != version:
        raise ValueError(f"Expected snapshot {version}, found {manifest.snapshot_version}.")
    validate_snapshot(path, manifest)
    return manifest


def validate_snapshot(path: Path, manifest: Snapshot) -> None:
    actual = inspect_snapshot(path, manifest.snapshot_version)
    for field in ("sha256", "row_counts", "latest_match_utc",
                  "latest_finalized_match_utc", "latest_ranking_date"):
        if getattr(actual, field) != getattr(manifest, field):
            raise ValueError(f"Snapshot manifest mismatch for {field}.")
