"""Transactional, source-backed local memory; no Blender or model dependency.

Models propose candidates. Only explicit user review promotes durable facts.
Scopes are enforced before ranking; old revisions never silently win a race.
"""

from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import time
import uuid
import unicodedata

SCOPES = {"session", "project", "user"}
KINDS = {"preference", "constraint", "decision", "fact", "procedure", "open_question"}
STATUSES = {"candidate", "verified", "conflict", "superseded", "rejected"}
SECRET = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]{12,})|"
    r"(?i:api[_ -]?key|password|secret)\s*[:=]\s*[^\s,;]{6,}"
)


def clean(text, maximum=32000):
    if not isinstance(text, str) or not text.strip() or len(text) > maximum:
        raise ValueError(f"Text must contain 1-{maximum} characters")
    return SECRET.sub("[redacted credential]", text.strip())


def encode_record(value, maximum=64000):
    """Redact values before JSON encoding; regex replacement on JSON breaks quoting."""

    def redact(item):
        if isinstance(item, str):
            return SECRET.sub("[redacted credential]", item)
        if isinstance(item, (list, tuple)):
            return [redact(v) for v in item]
        if isinstance(item, dict):
            return {
                k: "[redacted credential]"
                if re.fullmatch(
                    r"api[_ -]?key|password|secret|authorization", str(k), re.IGNORECASE
                )
                else redact(v)
                for k, v in item.items()
            }
        return item

    encoded = json.dumps(redact(value), ensure_ascii=False, allow_nan=False)
    if len(encoded) > maximum:
        raise ValueError("Structured memory record exceeds its size limit")
    return encoded


def terms(text):
    result = set(re.findall(r"[a-z0-9_]{2,}", text.lower()))
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        result.update(run[i : i + 2] for i in range(max(1, len(run) - 1)))
    return result


def tokens(text):
    # Conservative budgeting, deliberately not advertised as a model tokenizer.
    return max(1, (len(str(text).encode("utf-8")) + 2) // 3)


class RevisionConflict(ValueError):
    pass


class MemoryStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if self.db.execute("PRAGMA user_version").fetchone()[0] > 3:
            self.db.close()
            raise ValueError(
                "Memory database was created by a newer add-on; refusing to downgrade it"
            )
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, user_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS threads(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), title TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS turns(id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id TEXT NOT NULL REFERENCES threads(id), role TEXT NOT NULL, content TEXT NOT NULL, created REAL NOT NULL, state TEXT NOT NULL, metadata TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS turns_thread ON turns(thread_id,id);
        CREATE TABLE IF NOT EXISTS summaries(id INTEGER PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(id), through_id INTEGER NOT NULL, body TEXT NOT NULL, source_ids TEXT NOT NULL, mode TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, scope TEXT NOT NULL, owner TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, status TEXT NOT NULL, revision INTEGER NOT NULL, sources TEXT NOT NULL, importance REAL NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, expires REAL);
        CREATE INDEX IF NOT EXISTS memory_scope ON memories(scope,owner,status);
        CREATE TABLE IF NOT EXISTS memory_versions(memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE, revision INTEGER NOT NULL, snapshot TEXT NOT NULL, reason TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(memory_id,revision));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), kind TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS memory_blocks(scope TEXT NOT NULL, owner TEXT NOT NULL, key TEXT NOT NULL, digest TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(scope,owner,key,digest));
        CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), run_id TEXT NOT NULL, task_id TEXT NOT NULL, goal TEXT NOT NULL, outcome TEXT NOT NULL, evidence TEXT NOT NULL, attempts INTEGER NOT NULL, updated REAL NOT NULL, UNIQUE(project_id,run_id,task_id));
        CREATE INDEX IF NOT EXISTS episodes_project ON episodes(project_id,updated);
        CREATE TABLE IF NOT EXISTS memory_state(id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL);
        INSERT OR IGNORE INTO memory_state VALUES(1,0);
        CREATE TABLE IF NOT EXISTS episode_events(id INTEGER PRIMARY KEY, episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE, outcome TEXT NOT NULL, evidence TEXT NOT NULL, attempts INTEGER NOT NULL, created REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS episode_events_owner ON episode_events(episode_id,id);
        INSERT INTO episode_events(episode_id,outcome,evidence,attempts,created)
            SELECT id,outcome,evidence,attempts,updated FROM episodes e
            WHERE NOT EXISTS(SELECT 1 FROM episode_events h WHERE h.episode_id=e.id);
        PRAGMA user_version=3;
        COMMIT;
        """)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def project(self, ident, name="Untitled", user_id="local"):
        if not ident or not user_id:
            raise ValueError("Project and user identity are required")
        old = self.db.execute("SELECT * FROM projects WHERE id=?", (ident,)).fetchone()
        if old and old["user_id"] != user_id:
            raise ValueError("Project belongs to a different local user profile")
        self.db.execute(
            "INSERT OR IGNORE INTO projects VALUES(?,?,?)", (ident, name[:200], user_id)
        )
        return ident

    def new_thread(self, project_id, title="New conversation"):
        ident = uuid.uuid4().hex
        self.db.execute(
            "INSERT INTO threads VALUES(?,?,?,?)", (ident, project_id, title[:200], time.time())
        )
        return ident

    def projects(self, user_id="local"):
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM projects WHERE user_id=? ORDER BY rowid DESC", (user_id,)
            )
        ]

    def thread(self, ident, project_id=None):
        row = self.db.execute("SELECT * FROM threads WHERE id=?", (ident,)).fetchone()
        if not row or (project_id and row["project_id"] != project_id):
            raise ValueError("Conversation does not belong to this project")
        return dict(row)

    def threads(self, project_id):
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM threads WHERE project_id=? ORDER BY created DESC", (project_id,)
            )
        ]

    def append(self, thread_id, role, content, *, state="complete", metadata=None):
        self.thread(thread_id)
        if role not in {"user", "assistant", "tool"} or state not in {
            "complete",
            "failed",
            "pending",
        }:
            raise ValueError("Invalid conversation role/state")
        content = clean(content, 250000)
        ident = self.db.execute(
            "INSERT INTO turns(thread_id,role,content,created,state,metadata) VALUES(?,?,?,?,?,?)",
            (
                thread_id,
                role,
                content,
                time.time(),
                state,
                encode_record(metadata or {}, maximum=2_000_000),
            ),
        ).lastrowid
        if role == "user":
            self.db.execute(
                "UPDATE threads SET title=? WHERE id=? AND title='New conversation'",
                (" ".join(content.split())[:100], thread_id),
            )
        return ident

    def turns(self, thread_id, *, after=0, limit=10000, complete_only=False, oldest_first=False):
        query = "SELECT * FROM turns WHERE thread_id=? AND id>?"
        if complete_only:
            query += " AND state='complete'"
        rows = self.db.execute(
            query + (" ORDER BY id ASC LIMIT ?" if oldest_first else " ORDER BY id DESC LIMIT ?"),
            (thread_id, after, limit if limit is not None else -1),
        )
        result = [dict(r) for r in rows]
        return result if oldest_first else list(reversed(result))

    def turn_count(self, thread_id, *, complete_only=False):
        return self.db.execute(
            "SELECT COUNT(*) FROM turns WHERE thread_id=?"
            + (" AND state='complete'" if complete_only else ""),
            (thread_id,),
        ).fetchone()[0]

    def event(self, project_id, kind, data):
        self.db.execute(
            "INSERT INTO events(project_id,kind,data,created) VALUES(?,?,?,?)",
            (project_id, kind, encode_record(data), time.time()),
        )

    def _owner(self, scope, project_id, thread_id):
        if scope not in SCOPES:
            raise ValueError("Invalid memory scope")
        self.thread(thread_id, project_id)
        user = self.db.execute("SELECT user_id FROM projects WHERE id=?", (project_id,)).fetchone()[
            0
        ]
        return {"session": thread_id, "project": project_id, "user": user}[scope]

    def _sources(self, sources, project_id, thread_id):
        if not isinstance(sources, list) or not 1 <= len(sources) <= 12:
            raise ValueError("Memory needs 1-12 source quotes")
        output = []
        for item in sources:
            if not isinstance(item, dict):
                raise ValueError("Invalid source")
            row = self.db.execute(
                "SELECT * FROM turns WHERE id=? AND thread_id=?", (item.get("turn_id"), thread_id)
            ).fetchone()
            quote = item.get("quote", "")
            if (
                not row
                or row["role"] != "user"
                or row["state"] != "complete"
                or not isinstance(quote, str)
                or len(quote.strip()) < 3
                or quote not in row["content"]
            ):
                raise ValueError("Memory evidence must quote a real user turn in this conversation")
            output.append(
                {
                    "turn_id": row["id"],
                    "thread_id": thread_id,
                    "project_id": project_id,
                    "quote": quote[:4000],
                }
            )
        return output

    @staticmethod
    def decode(row):
        item = dict(row)
        item["sources"] = json.loads(item["sources"])
        return item

    def get(self, ident):
        row = self.db.execute("SELECT * FROM memories WHERE id=?", (ident,)).fetchone()
        if not row:
            raise ValueError("Memory no longer exists")
        return self.decode(row)

    def _version(self, ident, reason):
        item = self.get(ident)
        self.db.execute(
            "INSERT INTO memory_versions VALUES(?,?,?,?,?)",
            (ident, item["revision"], json.dumps(item, ensure_ascii=False), reason, time.time()),
        )
        return item

    def propose(self, project_id, thread_id, *, scope, kind, key, value, sources, importance=0.5):
        owner = self._owner(scope, project_id, thread_id)
        if kind not in KINDS:
            raise ValueError("Invalid memory kind")
        key = " ".join(unicodedata.normalize("NFKC", clean(key, 120)).casefold().split())
        value = clean(value, 4000)
        if (
            type(importance) not in {int, float}
            or not math.isfinite(importance)
            or not 0 <= importance <= 1
        ):
            raise ValueError("Memory importance must be a finite number between 0 and 1")
        if key.startswith("observed:"):
            raise ValueError("Native observation keys cannot be proposed by a model")
        sources = self._sources(sources, project_id, thread_id)
        if SECRET.search(value) or "[redacted credential]" in value:
            raise ValueError("Credentials cannot become memories")
        with self.transaction():
            if self.db.execute(
                "SELECT 1 FROM memory_blocks WHERE scope=? AND owner=? AND key=? AND digest=?",
                (scope, owner, key, self.value_digest(value)),
            ).fetchone():
                raise ValueError(
                    "This memory was explicitly rejected or forgotten; automatic re-proposal is suppressed"
                )
            existing = [
                self.decode(r)
                for r in self.db.execute(
                    "SELECT * FROM memories WHERE scope=? AND owner=? AND key=? AND status IN ('verified','candidate','conflict') AND (expires IS NULL OR expires>?)",
                    (scope, owner, key, time.time()),
                )
            ]
            for item in existing:
                if item["value"].casefold() == value.casefold():
                    merged = item["sources"] + [s for s in sources if s not in item["sources"]]
                    if merged != item["sources"]:
                        # Confirmation confidence comes from independent evidence,
                        # not repeated extraction of the very same user turn.
                        self.db.execute(
                            "UPDATE memories SET sources=?,revision=revision+1,updated=? WHERE id=?",
                            (json.dumps(merged[-24:], ensure_ascii=False), time.time(), item["id"]),
                        )
                        return self._version(
                            item["id"], "additional user evidence; authority unchanged"
                        )
                    return item
            ident, now = uuid.uuid4().hex, time.time()
            status = "conflict" if existing else "candidate"
            expires = now + 86400 if scope == "session" else None
            self.db.execute(
                "INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ident,
                    scope,
                    owner,
                    kind,
                    key,
                    value,
                    status,
                    1,
                    json.dumps(sources, ensure_ascii=False),
                    min(1.0, max(0.0, float(importance))),
                    now,
                    now,
                    expires,
                ),
            )
            return self._version(ident, "source-checked model/user proposal")

    def observe(self, project_id, key, value, evidence):
        """Called only by the host after native validation, never from model JSON."""
        if not key.startswith("observed:") or not evidence.get("fingerprint"):
            raise ValueError("Native observations require a reserved key and verified fingerprint")
        if not self.db.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone():
            raise ValueError("Unknown project")
        value = clean(value, 4000)
        with self.transaction():
            row = self.db.execute(
                "SELECT id FROM memories WHERE scope='project' AND owner=? AND key=?",
                (project_id, key),
            ).fetchone()
            sources = encode_record([dict(evidence, kind="native_quality")])
            now = time.time()
            if row:
                ident = row[0]
                self.db.execute(
                    "UPDATE memories SET value=?,sources=?,revision=revision+1,updated=?,status='verified' WHERE id=?",
                    (value, sources, now, ident),
                )
            else:
                ident = uuid.uuid4().hex
                self.db.execute(
                    "INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        ident,
                        "project",
                        project_id,
                        "fact",
                        key,
                        value,
                        "verified",
                        1,
                        sources,
                        0.4,
                        now,
                        now,
                        None,
                    ),
                )
            return self._version(ident, "native structural verification; not aesthetic judgement")

    def review(self, ident, expected_revision, *, action, value=None):
        if action not in {"verify", "reject", "restore"}:
            raise ValueError("Invalid review action")
        with self.transaction():
            item = self.get(ident)
            if item["revision"] != expected_revision:
                raise RevisionConflict("Memory changed since it was opened; reload before editing")
            if action == "verify":
                # The user explicitly chooses which conflicting version is authoritative.
                conflicts = list(
                    self.db.execute(
                        "SELECT id FROM memories WHERE scope=? AND owner=? AND key=? AND id<>? AND status IN ('verified','candidate','conflict')",
                        (item["scope"], item["owner"], item["key"], ident),
                    )
                )
                for old in conflicts:
                    self.db.execute(
                        "UPDATE memories SET status='superseded',revision=revision+1,updated=? WHERE id=?",
                        (time.time(), old[0]),
                    )
                    self._version(old[0], "superseded by explicit user decision " + ident)
            value = clean(value, 4000) if value is not None else item["value"]
            if "[redacted credential]" in value:
                raise ValueError("Credentials cannot become memories")
            status = {"verify": "verified", "reject": "rejected", "restore": "candidate"}[action]
            if action == "reject":
                self._block(item)
            elif action == "restore":
                self.db.execute(
                    "DELETE FROM memory_blocks WHERE scope=? AND owner=? AND key=? AND digest=?",
                    (item["scope"], item["owner"], item["key"], self.value_digest(item["value"])),
                )
            self.db.execute(
                "UPDATE memories SET value=?,status=?,revision=revision+1,updated=?,expires=? WHERE id=?",
                (
                    value,
                    status,
                    time.time(),
                    time.time() + 86400 if item["scope"] == "session" else None,
                    ident,
                ),
            )
            self.db.execute("UPDATE memory_state SET epoch=epoch+1 WHERE id=1")
            return self._version(ident, "explicit user " + action)

    def versions(self, ident):
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM memory_versions WHERE memory_id=? ORDER BY revision", (ident,)
            )
        ]

    def forget(self, ident, expected_revision):
        with self.transaction():
            item = self.get(ident)
            if item["revision"] != expected_revision:
                raise RevisionConflict("Reload memory before forgetting")
            self._block(item)
            # Summaries are derived data and may repeat a removed fact. Regenerate
            # from originals, which have their own explicit project-erasure control.
            for source in item["sources"]:
                if source.get("thread_id"):
                    self.db.execute(
                        "DELETE FROM summaries WHERE thread_id=?", (source["thread_id"],)
                    )
            self.db.execute("DELETE FROM memories WHERE id=?", (ident,))
            self.db.execute("UPDATE memory_state SET epoch=epoch+1 WHERE id=1")
        # Checkpoint reduces recoverable WAL content; filesystem backups are outside this service.
        self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def visible(self, project_id, thread_id, *, verified=False, include_user=True, limit=2000):
        user = self._owner("user", project_id, thread_id)
        args = [project_id, thread_id]
        query = "SELECT * FROM memories WHERE ((scope='project' AND owner=?) OR (scope='session' AND owner=?)"
        if include_user:
            query += " OR (scope='user' AND owner=?)"
            args.append(user)
        query += ")"
        if verified:
            query += " AND status='verified' AND (expires IS NULL OR expires>?)"
            args.append(time.time())
        return [
            self.decode(r)
            for r in self.db.execute(
                query + " ORDER BY importance DESC,updated DESC LIMIT ?",
                args + [limit if limit is not None else -1],
            )
        ]

    def retrieve(
        self, project_id, thread_id, query, *, budget=1200, include_user=True, require_pinned=False
    ):
        words = terms(query)
        candidates = self.resolved(project_id, thread_id, include_user=include_user)
        scored = []
        for item in candidates:
            vocabulary = terms(item["key"] + " " + item["value"])
            overlap = len(words & vocabulary)
            pinned = item["kind"] == "constraint" and item["importance"] >= 0.9
            if not overlap and not pinned:
                continue
            age_days = max(0, (time.time() - item["updated"]) / 86400)
            score = overlap / max(1, math.sqrt(len(vocabulary))) * 3 + item["importance"]
            score += (2 if pinned else 0) + 0.2 / (1 + age_days)
            scored.append(
                (
                    score,
                    dict(
                        item,
                        retrieval_reason="pinned constraint"
                        if pinned
                        else f"{overlap} matching terms; scope precedence applied",
                    ),
                )
            )
        ranked = [
            m
            for _, m in sorted(
                scored,
                key=lambda pair: (
                    not (require_pinned and pair[1]["retrieval_reason"] == "pinned constraint"),
                    -pair[0],
                    pair[1]["id"],
                ),
            )
        ]
        result, used = [], 0
        for item in ranked:
            cost = tokens(
                json.dumps(
                    {k: item[k] for k in ("id", "revision", "scope", "kind", "key", "value")},
                    ensure_ascii=False,
                )
            )
            if used + cost <= budget:
                result.append(item)
                used += cost
            elif require_pinned and item["retrieval_reason"] == "pinned constraint":
                raise ValueError(
                    "Pinned constraints exceed the expert memory budget; increase context budget"
                )
        return result

    @staticmethod
    def value_digest(value):
        return hashlib.sha256(
            unicodedata.normalize("NFKC", value).casefold().strip().encode()
        ).hexdigest()

    def _block(self, item):
        self.db.execute(
            "INSERT OR IGNORE INTO memory_blocks VALUES(?,?,?,?,?)",
            (
                item["scope"],
                item["owner"],
                item["key"],
                self.value_digest(item["value"]),
                time.time(),
            ),
        )

    def resolved(self, project_id, thread_id, *, include_user=True):
        """More specific verified intent overrides a personal default with the same key."""
        priority = {"session": 3, "project": 2, "user": 1}
        visible = self.visible(
            project_id, thread_id, verified=True, include_user=include_user, limit=None
        )
        result = {}
        for item in sorted(
            visible, key=lambda m: (priority[m["scope"]], m["updated"]), reverse=True
        ):
            result.setdefault(item["key"], item)
        return list(result.values())

    def conflicts(self, project_id, thread_id, *, include_user=True):
        return [
            {k: m[k] for k in ("id", "key", "value", "scope", "revision")}
            for m in self.visible(project_id, thread_id, include_user=include_user)
            if m["status"] == "conflict" and (m["expires"] is None or m["expires"] > time.time())
        ]

    def record_episode(self, project_id, run_id, task_id, goal, outcome, evidence, *, attempts=1):
        """Execution history, never promoted to a universal procedure or user preference."""
        if (
            outcome not in {"succeeded", "failed", "cancelled"}
            or type(attempts) is not int
            or attempts < 1
        ):
            raise ValueError("Invalid execution outcome")
        if not isinstance(evidence, dict):
            raise ValueError("Execution evidence must be an object")
        encoded = encode_record(evidence)
        with self.transaction():
            previous = self.db.execute(
                "SELECT * FROM episodes WHERE project_id=? AND run_id=? AND task_id=?",
                (project_id, run_id, task_id),
            ).fetchone()
            if previous and attempts < previous["attempts"]:
                raise RevisionConflict("Execution episode cannot regress to an earlier attempt")
            if previous and (previous["outcome"], previous["evidence"], previous["attempts"]) == (
                outcome,
                encoded,
                attempts,
            ):
                return
            ident = previous["id"] if previous else uuid.uuid4().hex
            updated = time.time()
            self.db.execute(
                """INSERT INTO episodes VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(project_id,run_id,task_id) DO UPDATE SET outcome=excluded.outcome,
            evidence=excluded.evidence,attempts=excluded.attempts,updated=excluded.updated""",
                (
                    ident,
                    project_id,
                    run_id,
                    task_id,
                    clean(goal, 20000),
                    outcome,
                    encoded,
                    attempts,
                    updated,
                ),
            )
            self.db.execute(
                "INSERT INTO episode_events(episode_id,outcome,evidence,attempts,created) VALUES(?,?,?,?,?)",
                (ident, outcome, encoded, attempts, updated),
            )

    def episode_history(self, ident, *, limit=20):
        rows = self.db.execute(
            "SELECT outcome,evidence,attempts,created FROM episode_events WHERE episode_id=? "
            "ORDER BY id DESC LIMIT ?",
            (ident, limit if limit is not None else -1),
        )
        return [dict(r, evidence=json.loads(r["evidence"])) for r in reversed(list(rows))]

    def recall_episodes(self, project_id, query, *, limit=4):
        words = terms(query)
        found = []
        for row in self.db.execute(
            "SELECT * FROM episodes WHERE project_id=? ORDER BY updated DESC LIMIT 1000",
            (project_id,),
        ):
            overlap = len(words & terms(row["goal"] + " " + row["task_id"]))
            if overlap or not words:
                item = dict(row)
                item["evidence"] = json.loads(item["evidence"])
                found.append((overlap, item))
        result = [item for _, item in sorted(found, key=lambda pair: -pair[0])[:limit]]
        for item in result:
            item["history"] = self.episode_history(item["id"])
        return result

    def memory_epoch(self):
        return self.db.execute("SELECT epoch FROM memory_state WHERE id=1").fetchone()[0]

    def summary(self, thread_id):
        row = self.db.execute(
            "SELECT * FROM summaries WHERE thread_id=? ORDER BY through_id DESC,id DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
        return dict(row) if row else None

    def save_summary(self, thread_id, source_ids, body, *, mode="semantic", expected_epoch=None):
        self.thread(thread_id)
        if not source_ids or mode not in {"semantic", "extractive"}:
            raise ValueError("Summary requires sources and a valid mode")
        if any(type(i) is not int for i in source_ids):
            raise ValueError("Summary source IDs must be integers")
        encoded = encode_record(body)
        with self.transaction():
            if expected_epoch is not None and expected_epoch != self.memory_epoch():
                raise RevisionConflict(
                    "Memory was reviewed or forgotten while compression was running"
                )
            actual = {
                r[0]
                for r in self.db.execute(
                    "SELECT id FROM turns WHERE thread_id=? AND state='complete' AND id<=?",
                    (thread_id, max(source_ids)),
                )
            }
            if set(source_ids) != actual:
                raise ValueError(
                    "Summary coverage must be a contiguous prefix of complete turns in this conversation"
                )
            previous = self.summary(thread_id)
            if previous and max(source_ids) <= previous["through_id"]:
                raise RevisionConflict("Summary checkpoint is stale")
            self.db.execute(
                "INSERT INTO summaries(thread_id,through_id,body,source_ids,mode,created) VALUES(?,?,?,?,?,?)",
                (
                    thread_id,
                    max(source_ids),
                    encoded,
                    json.dumps(sorted(set(source_ids))),
                    mode,
                    time.time(),
                ),
            )

    def export_project(self, project_id):
        threads = self.threads(project_id)
        episodes = []
        for row in self.db.execute(
            "SELECT * FROM episodes WHERE project_id=? ORDER BY updated", (project_id,)
        ):
            episodes.append(
                dict(
                    row,
                    evidence=json.loads(row["evidence"]),
                    history=self.episode_history(row["id"], limit=None),
                )
            )
        return {
            "schema": 3,
            "project_id": project_id,
            "episodes": episodes,
            "threads": [
                dict(
                    t,
                    turns=self.turns(t["id"], limit=None),
                    summaries=[
                        dict(r)
                        for r in self.db.execute(
                            "SELECT * FROM summaries WHERE thread_id=? ORDER BY id", (t["id"],)
                        )
                    ],
                )
                for t in threads
            ],
            "memories": [
                dict(self.decode(r), versions=self.versions(r["id"]))
                for r in self.db.execute(
                    "SELECT * FROM memories WHERE (scope='project' AND owner=?) OR (scope='session' AND owner IN (SELECT id FROM threads WHERE project_id=?))",
                    (project_id, project_id),
                )
            ],
        }

    def forget_project(self, project_id):
        """Erase project originals and any memory that cites them, including personal copies."""
        threads = {t["id"] for t in self.threads(project_id)}
        with self.transaction():
            for row in list(self.db.execute("SELECT * FROM memories")):
                item = self.decode(row)
                owns = (item["scope"] == "project" and item["owner"] == project_id) or (
                    item["scope"] == "session" and item["owner"] in threads
                )
                cites = any(
                    s.get("project_id") == project_id or s.get("thread_id") in threads
                    for s in item["sources"]
                )
                if owns or cites:
                    self.db.execute("DELETE FROM memories WHERE id=?", (item["id"],))
            for thread in threads:
                self.db.execute("DELETE FROM summaries WHERE thread_id=?", (thread,))
                self.db.execute("DELETE FROM turns WHERE thread_id=?", (thread,))
            self.db.execute("DELETE FROM threads WHERE project_id=?", (project_id,))
            self.db.execute("DELETE FROM events WHERE project_id=?", (project_id,))
            self.db.execute("DELETE FROM episodes WHERE project_id=?", (project_id,))
            self.db.execute(
                "DELETE FROM memory_blocks WHERE scope='project' AND owner=?", (project_id,)
            )
            for thread in threads:
                self.db.execute(
                    "DELETE FROM memory_blocks WHERE scope='session' AND owner=?", (thread,)
                )
            self.db.execute("DELETE FROM projects WHERE id=?", (project_id,))
            self.db.execute("UPDATE memory_state SET epoch=epoch+1 WHERE id=1")
        self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def backup(self, destination):
        target = sqlite3.connect(str(destination))
        try:
            self.db.backup(target)
        finally:
            target.close()

    def fingerprint(self, project_id, thread_id):
        return hashlib.sha256(
            json.dumps(self.visible(project_id, thread_id), sort_keys=True).encode()
        ).hexdigest()
