"""QSG append-only SQLite store. Synthetic host only; no process/memory APIs.

One exclusive owner file per retained enrollment. A crash leaves that file;
reopening never steals it. SQLite FULL commits precede the retained head update
and any grant. An uncertain commit/head update poisons the owner. These are
tested process/filesystem failure semantics, not a physical power-loss claim.
"""
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import sqlite3
import threading

from .evidence import canonical, decode, digest, file_hash


class QSGError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise QSGError(code)


def new_file(path, raw):
    with Path(path).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


class Store:
    @staticmethod
    def provision(directory, policy):
        # Provisioning is a deliberate test-host operation, never an open fallback.
        directory = Path(directory)
        directory.mkdir(exist_ok=False)
        enrollment = {"schema": "qsg.enrollment.v1", "policy": deepcopy(policy)}
        new_file(directory / "enrollment.json", canonical(enrollment))
        db = sqlite3.connect(directory / "ledger.sqlite")
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY, body TEXT NOT NULL)")
            db.commit()
        finally:
            db.close()
        new_file(directory / "head.json", canonical({"records": 0, "head": "0" * 64}))
        return file_hash(directory / "enrollment.json")

    def __init__(self, directory, seal, clock_ms, fault=None):
        self.directory, self.seal = Path(directory), seal
        self.clock_ms, self.fault = clock_ms, fault or (lambda _: None)
        self.closed = self.poisoned = False
        self.mutex = threading.Lock()
        self.owner = os.urandom(16).hex()
        self.lock = self.directory / "owner.lock"
        self.db = None
        try:
            new_file(self.lock, self.owner.encode("ascii"))
        except OSError as exc:
            raise QSGError("QSG_LOCKED_OR_MISSING") from exc
        try:
            require(file_hash(self.directory / "enrollment.json") == seal, "QSG_ENROLLMENT")
            self.enrollment = decode((self.directory / "enrollment.json").read_bytes())
            require(self.enrollment["schema"] == "qsg.enrollment.v1", "QSG_VERSION")
            # mode=rw is essential: missing databases must never become empty budgets.
            uri = (self.directory / "ledger.sqlite").resolve().as_uri() + "?mode=rw"
            self.db = sqlite3.connect(uri, uri=True, timeout=0, check_same_thread=False)
            self.db.execute("PRAGMA synchronous=FULL")
            require(self.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "QSG_LEDGER_CORRUPT")
            self.rows = self.read()
        except Exception:
            self.poisoned = True
            if self.db:
                self.db.close()
            raise

    def read(self):
        require(not self.closed and not self.poisoned, "QSG_STORE_CLOSED")
        require(self.lock.read_text() == self.owner, "QSG_OWNER_CHANGED")
        require(file_hash(self.directory / "enrollment.json") == self.seal, "QSG_ENROLLMENT")
        require(not (self.directory / "head.pending").exists(), "QSG_DURABILITY_UNCERTAIN")
        head = decode((self.directory / "head.json").read_bytes())
        stored = self.db.execute("SELECT sequence,body FROM events ORDER BY sequence").fetchall()
        rows = [decode(body) for _, body in stored]
        previous, last = "0" * 64, -1
        for number, row in enumerate(rows, 1):
            require(stored[number-1][0] == number, "QSG_LEDGER_SEQUENCE")
            require(set(row) == {"schema", "origin", "sequence", "clock_ms", "kind", "data", "previous", "digest"}, "QSG_LEDGER_SCHEMA")
            require(row["schema"] == "qsg.store.v1" and row["origin"] == "SYNTHETIC", "QSG_LEDGER_SCHEMA")
            require(type(row["sequence"]) is int and row["sequence"] == number and row["previous"] == previous, "QSG_LEDGER_SEQUENCE")
            require(type(row["clock_ms"]) is int and row["clock_ms"] >= last, "QSG_CLOCK")
            require(row["digest"] == digest({k: v for k, v in row.items() if k != "digest"}), "QSG_LEDGER_DIGEST")
            previous, last = row["digest"], row["clock_ms"]
        require(head == {"records": len(rows), "head": previous}, "QSG_LEDGER_HEAD")
        return rows

    @contextmanager
    def exclusive(self):
        require(self.mutex.acquire(blocking=False), "QSG_REENTRANT_OR_CONCURRENT")
        try:
            try:
                self.rows = self.read()
            except Exception:
                self.poisoned = True
                raise
            yield
        finally:
            self.mutex.release()

    def append(self, kind, data):
        now = self.clock_ms()
        require(type(now) is int and now >= (self.rows[-1]["clock_ms"] if self.rows else 0), "QSG_CLOCK")
        row = {"schema": "qsg.store.v1", "origin": "SYNTHETIC", "sequence": len(self.rows) + 1,
               "clock_ms": now, "kind": kind, "data": deepcopy(data),
               "previous": self.rows[-1]["digest"] if self.rows else "0" * 64}
        row["digest"] = digest(row)
        require(len(canonical(row)) <= 65536, "QSG_EVENT_BOUND")
        try:
            self.fault("before_transaction")
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute("INSERT INTO events VALUES (?,?)", (row["sequence"], canonical(row).decode()))
            self.fault("before_commit")
            self.db.commit()
            self.fault("after_commit")
            self.fault("before_head")
            new_file(self.directory / "head.pending", canonical({"records": row["sequence"], "head": row["digest"]}))
            self.fault("after_head_fsync")
            os.replace(self.directory / "head.pending", self.directory / "head.json")
            self.fault("after_head_replace")
            self.rows.append(row)
            self.fault("before_ack")
        except Exception:
            self.poisoned = True
            self.db.rollback()
            raise QSGError("QSG_DURABILITY_UNCERTAIN") from None
        return deepcopy(row)

    def close(self):
        if self.closed:
            return
        require(self.mutex.acquire(blocking=False), "QSG_REENTRANT_OR_CONCURRENT")
        try:
            self.db.close()
            if not self.poisoned and self.lock.read_text() == self.owner:
                self.lock.unlink()
            self.closed = True
        finally:
            self.mutex.release()
