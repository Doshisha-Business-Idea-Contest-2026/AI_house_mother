"""Unit tests for :mod:`scripts.reset_demo` service-guard helpers.

Audit finding M1 (B-2) called out that ``_service_is_running`` is the
single line of defence keeping the demo reset from stomping on live
``data/*.json`` while the systemd unit is running. A reversed check or a
missing ``check=False`` would silently reopen the exact hazard the guard
was written to close.

Style follows ``tests/test_handlers_quickreply.py``: no pytest fixtures,
class-based, ``unittest.mock.patch`` for the two subprocess boundaries.
"""

from __future__ import annotations

import io
import subprocess
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from scripts import reset_demo


class TestServiceIsRunning:
    def test_returns_false_when_systemctl_missing(self) -> None:
        """Dev containers and macOS have no systemctl; the script must
        still be usable, and the guard must not treat 'unknown' as 'up'."""
        with (
            patch.object(reset_demo.shutil, "which", return_value=None),
            patch.object(reset_demo.subprocess, "run") as run_mock,
        ):
            assert reset_demo._service_is_running() is False
            # We should short-circuit before ever shelling out.
            run_mock.assert_not_called()

    def test_returns_true_when_returncode_zero(self) -> None:
        with (
            patch.object(reset_demo.shutil, "which", return_value="/bin/systemctl"),
            patch.object(reset_demo.subprocess, "run") as run_mock,
        ):
            run_mock.return_value = SimpleNamespace(returncode=0)

            assert reset_demo._service_is_running() is True

            # Confirm the exact invocation shape so a typo in the args
            # (dropping --quiet, wrong unit name, shell=True) trips the
            # test.
            run_mock.assert_called_once()
            args, kwargs = run_mock.call_args
            assert args[0] == [
                "systemctl",
                "is-active",
                "--quiet",
                reset_demo.SERVICE_NAME,
            ]
            assert kwargs.get("check") is False
            assert kwargs.get("timeout") == 5

    def test_returns_false_when_returncode_nonzero(self) -> None:
        with (
            patch.object(reset_demo.shutil, "which", return_value="/bin/systemctl"),
            patch.object(reset_demo.subprocess, "run") as run_mock,
        ):
            run_mock.return_value = SimpleNamespace(returncode=3)
            assert reset_demo._service_is_running() is False

    def test_returns_false_on_subprocess_error(self) -> None:
        """A CalledProcessError / TimeoutExpired / OSError must not leak
        — otherwise the script crashes before deciding to reset."""
        cases: list[BaseException] = [
            subprocess.SubprocessError("boom"),
            subprocess.TimeoutExpired(cmd=["systemctl"], timeout=5),
            OSError("permission denied"),
        ]
        for exc in cases:
            with (
                patch.object(reset_demo.shutil, "which", return_value="/bin/systemctl"),
                patch.object(reset_demo.subprocess, "run", side_effect=exc),
            ):
                assert reset_demo._service_is_running() is False


class TestMainDryRunIsReadOnly:
    """`--dry-run` must never write files and never consult systemctl."""

    def test_dry_run_short_circuits_before_service_check(self) -> None:
        with (
            patch.object(reset_demo, "_service_is_running") as guard_mock,
            patch("builtins.open") as open_mock,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            rc = reset_demo.main(["--dry-run"])

        assert rc == 0
        # Dry-run is safe by construction: the service check is
        # irrelevant and file writes are forbidden.
        guard_mock.assert_not_called()
        open_mock.assert_not_called()
        assert "[dry-run]" in stdout.getvalue()


class TestMainAbortsWhenServiceActive:
    """Live-service guard: return code 2 and no writes when the unit is up."""

    def test_active_service_aborts_with_return_code_2(self) -> None:
        with (
            patch.object(reset_demo, "_service_is_running", return_value=True),
            patch("builtins.open") as open_mock,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            rc = reset_demo.main(["--yes"])

        assert rc == 2
        open_mock.assert_not_called()
        message = stdout.getvalue()
        assert "[ABORT]" in message
        # The 3-step remediation recipe must be visible so an operator
        # who hits this at demo time knows how to unstick themselves.
        assert "systemctl stop" in message
        assert "systemctl start" in message

    def test_force_service_active_bypasses_guard(self) -> None:
        """The escape hatch must actually let the reset proceed. We stop
        just before the file writes by patching the target loop."""
        with (
            patch.object(reset_demo, "_service_is_running", return_value=True),
            patch("builtins.open") as open_mock,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            # `--yes` skips the interactive prompt; the loop over
            # targets will try to write JSON, so we let it run against
            # the patched open. We only care that abort does not fire.
            reset_demo.main(["--yes", "--force-service-active"])

        assert "[ABORT]" not in stdout.getvalue()
        # Some open() calls will have happened for the fake JSON writes;
        # the point is the guard did not preempt them.
        assert open_mock.called
