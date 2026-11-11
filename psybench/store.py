"""Append-only attempts, with at most one canonical completed trial per identity."""

import json
import sqlite3


class Store:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                manifest TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY,
                trial_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                repetition INTEGER NOT NULL,
                status TEXT NOT NULL,
                record TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );
            CREATE INDEX IF NOT EXISTS trial_lookup ON attempts(trial_id);
            CREATE TABLE IF NOT EXISTS targets (
                run_id TEXT PRIMARY KEY,
                repetitions INTEGER NOT NULL
            );
        """)

    def add_run(self, run_id, manifest):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO runs VALUES (?, ?)", (run_id, json.dumps(manifest)))

    def completed(self, trial_id):
        return self.db.execute(
            "SELECT 1 FROM attempts WHERE trial_id=? AND status != 'error' LIMIT 1",
            (trial_id,),
        ).fetchone() is not None

    def set_target(self, run_id, repetitions):
        with self.db:
            self.db.execute(
                "INSERT INTO targets VALUES (?, ?) ON CONFLICT(run_id) DO UPDATE SET repetitions=MAX(repetitions,excluded.repetitions)",
                (run_id, repetitions),
            )

    def targets(self):
        return dict(self.db.execute("SELECT run_id,repetitions FROM targets"))

    def save(self, trial_id, run_id, item_id, repetition, status, record):
        with self.db:
            self.db.execute(
                "INSERT INTO attempts(trial_id,run_id,item_id,repetition,status,record) VALUES (?,?,?,?,?,?)",
                (trial_id, run_id, item_id, repetition, status, json.dumps(record)),
            )

    def runs(self):
        return {row["id"]: json.loads(row["manifest"]) for row in self.db.execute("SELECT * FROM runs ORDER BY id")}

    def attempts(self):
        return [dict(row) | {"record": json.loads(row["record"])} for row in self.db.execute("SELECT * FROM attempts ORDER BY id")]

    def close(self):
        self.db.close()
