"""Owned disposable Bazaar processes: no reset API on an arbitrary target URL."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

from detect.invariants import SQLInvariantRunner


class BazaarTarget:
    def __init__(
        self,
        directory: Path,
        *,
        version: str = "v1",
        database_url: str | None = None,
        bug_overrides: dict | None = None,
        seed_fixture: str | None = None,
    ):
        from apps.bazaar.bazaar.seed import seed_database

        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database_url = database_url or f"sqlite:///{self.directory / 'target.sqlite3'}"
        self._seed = seed_database
        self.seed_fixture = seed_fixture
        self.version = version
        self.bug_overrides = bug_overrides or {}
        self.process = None
        self.log = None
        self.url = ""
        self.engine = create_engine(self.database_url)
        self.reset(1)

    def reset(self, seed: int, *, clear_reports: bool = False) -> None:
        # Only a target object explicitly constructed by the launcher can reset.
        self._seed(self.database_url, seed, self.seed_fixture, preserve_reports=not clear_reports)
        if self.engine.dialect.name == "sqlite":
            with self.engine.connect() as db:
                db.exec_driver_sql("PRAGMA journal_mode=WAL")

    def start(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        self.log = (self.directory / "server.log").open("w")
        env = {
            **os.environ,
            "DATABASE_URL": self.database_url,
            "BAZAAR_VERSION": self.version,
            "BAZAAR_BUG_OVERRIDES": json.dumps(self.bug_overrides),
        }
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "apps.bazaar.bazaar.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "error",
            ],
            env=env,
            stdout=self.log,
            stderr=self.log,
        )
        for _ in range(100):
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"Bazaar failed to start; inspect {self.directory / 'server.log'}"
                )
            try:
                if httpx.get(self.url + "/health", timeout=0.5).status_code == 200:
                    return
            except httpx.RequestError:
                pass
            time.sleep(0.1)
        raise TimeoutError("owned Bazaar did not start")

    def rows(self, query: str) -> list[dict]:
        with self.engine.connect() as db:
            return [dict(row) for row in db.execute(text(query)).mappings()]

    def invariant_runner(self) -> SQLInvariantRunner:
        if self.engine.dialect.name == "sqlite":
            return SQLInvariantRunner.sqlite(self.engine.url.database)
        url = self.database_url.replace("postgresql+psycopg://", "postgresql://")
        return SQLInvariantRunner.postgres(url)

    def close(self) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.log is not None:
            self.log.close()
        self.engine.dispose()


class BazaarEnvironment:
    def __init__(
        self,
        directory: str | Path = "artifacts/phase1",
        *,
        version: str = "v1",
        seed_fixture: str | None = None,
    ):
        base = Path(directory).resolve()
        base.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix="targets-", dir=base))
        self.live = BazaarTarget(
            self.directory / "live", version=version, seed_fixture=seed_fixture
        )
        self.replay = BazaarTarget(
            self.directory / "replay", version=version, seed_fixture=seed_fixture
        )

    def __enter__(self):
        try:
            self.live.start()
            self.replay.start()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        self.live.close()
        self.replay.close()

    def reset_workspace(self, seed: int):
        """Full reset is explicit; ordinary benchmark resets retain published reports."""
        for target in (self.live, self.replay):
            target.reset(seed, clear_reports=True)
            if target.log is not None:
                target.log.seek(0)
                target.log.truncate()
                target.log.flush()
