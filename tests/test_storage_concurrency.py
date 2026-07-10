"""Concurrency tests for :func:`storage.locked_edit` (Issue #45).

Spawns real ``multiprocessing.Process`` workers so ``fcntl.flock`` is
exercised across processes (threads share the same file descriptor and
cannot show the lost-update pattern that this fix targets). Each worker
appends N records; the invariant is that the union of all writes lands
on disk and no record is dropped.

Runs quickly (<2 s) on Linux and macOS. The CI story is spelled out in
``docs/05_data_model.md §3.1``: currently local pytest only.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import shutil
import tempfile
from pathlib import Path

from src.services import parent_links, posts, storage, usage_stats


def _add_posts_worker(
    data_dir: str, user_id: str, count: int, barrier: mp.Barrier  # type: ignore[type-arg]
) -> None:
    """Append ``count`` posts under the parent's tmp DATA_DIR."""
    storage.DATA_DIR = Path(data_dir)
    barrier.wait()
    for i in range(count):
        posts.add_post(
            line_user_id=user_id,
            category="study",
            title=f"t-{i}",
            summary=f"s-{i}",
            learned="",
            area=None,
            share_with_parent=False,
        )


def _record_usage_worker(
    data_dir: str, user_id: str, count: int, barrier: mp.Barrier  # type: ignore[type-arg]
) -> None:
    storage.DATA_DIR = Path(data_dir)
    barrier.wait()
    for _ in range(count):
        usage_stats.record(user_id, "life")


def _link_parent_worker(
    data_dir: str,
    parent_user_id: str,
    student_prefix: str,
    count: int,
    barrier: mp.Barrier,  # type: ignore[type-arg]
) -> None:
    storage.DATA_DIR = Path(data_dir)
    barrier.wait()
    for i in range(count):
        parent_links.link(parent_user_id, f"{student_prefix}-{i}")


class TestConcurrentPostsPreserveEveryAppend:
    def setup_method(self) -> None:
        self._orig = storage.DATA_DIR
        self._tmp = Path(tempfile.mkdtemp(prefix="ai_house_mother_test_"))
        storage.DATA_DIR = self._tmp
        (self._tmp / "posts.json").write_text('{"posts": []}', encoding="utf-8")

    def teardown_method(self) -> None:
        storage.DATA_DIR = self._orig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_four_workers_append_without_lost_updates(self) -> None:
        workers = 4
        per_worker = 15
        # ``spawn`` avoids inheriting the parent's already-open file
        # descriptors, which better simulates independent LINE webhook
        # processes.
        ctx = mp.get_context("spawn")
        barrier = ctx.Barrier(workers)
        procs = [
            ctx.Process(
                target=_add_posts_worker,
                args=(str(self._tmp), f"Uconcurrent-{w}", per_worker, barrier),
            )
            for w in range(workers)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)
            assert p.exitcode == 0, f"worker crashed exitcode={p.exitcode}"

        data = json.loads((self._tmp / "posts.json").read_text(encoding="utf-8"))
        assert len(data["posts"]) == workers * per_worker
        ids = [row["post_id"] for row in data["posts"]]
        assert len(set(ids)) == len(ids), "post_id collision — race not sealed"


class TestConcurrentUsageStatsPreserveCounter:
    def setup_method(self) -> None:
        self._orig = storage.DATA_DIR
        self._tmp = Path(tempfile.mkdtemp(prefix="ai_house_mother_test_"))
        storage.DATA_DIR = self._tmp

    def teardown_method(self) -> None:
        storage.DATA_DIR = self._orig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_counter_reaches_total_under_parallel_writers(self) -> None:
        workers = 4
        per_worker = 20
        ctx = mp.get_context("spawn")
        barrier = ctx.Barrier(workers)
        procs = [
            ctx.Process(
                target=_record_usage_worker,
                args=(str(self._tmp), "Ustats-race", per_worker, barrier),
            )
            for _ in range(workers)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)
            assert p.exitcode == 0

        got = usage_stats.get_month(
            "Ustats-race",
            usage_stats._year_month(usage_stats.datetime.now(usage_stats.JST)),
        )
        assert (
            got["life"] == workers * per_worker
        ), "lost-update — the counter dropped a concurrent increment"


class TestConcurrentParentLinksNoDuplicateRows:
    def setup_method(self) -> None:
        self._orig = storage.DATA_DIR
        self._tmp = Path(tempfile.mkdtemp(prefix="ai_house_mother_test_"))
        storage.DATA_DIR = self._tmp

    def teardown_method(self) -> None:
        storage.DATA_DIR = self._orig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_re_tap_from_two_processes_stays_idempotent(self) -> None:
        """Two workers both call ``link(P, S)`` many times: the record
        must appear exactly once, not once per worker.
        """
        workers = 2
        per_worker = 10
        ctx = mp.get_context("spawn")
        barrier = ctx.Barrier(workers)
        procs = [
            ctx.Process(
                target=_link_parent_worker,
                args=(str(self._tmp), "Prace", "Srace", per_worker, barrier),
            )
            for _ in range(workers)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)
            assert p.exitcode == 0

        data = json.loads((self._tmp / "parent_links.json").read_text(encoding="utf-8"))
        rows = data["links"]
        # Each worker touches Srace-0 .. Srace-9. Total unique pairs =
        # per_worker (parent stays the same). No duplicates.
        assert len(rows) == per_worker
        pairs = {(r["parent_user_id"], r["student_user_id"]) for r in rows}
        assert len(pairs) == per_worker
