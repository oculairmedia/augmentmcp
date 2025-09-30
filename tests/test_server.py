from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastmcp.exceptions import ToolError

from augment_mcp.auggie import run_auggie
from augment_mcp.server import (
    augment_configure,
    augment_custom_command,
    augment_list_commands,
    augment_review,
)


class AugmentServerTests(unittest.IsolatedAsyncioTestCase):
    """Integration tests against the fake Auggie CLI."""

    def setUp(self) -> None:
        self.fake_cli = Path(__file__).with_name("fake_auggie.py")
        current_mode = self.fake_cli.stat().st_mode
        if not current_mode & stat.S_IXUSR:
            self.fake_cli.chmod(current_mode | stat.S_IXUSR)
        self.addCleanup(lambda: self.fake_cli.chmod(current_mode))

        self._previous_path = os.environ.get("AUGGIE_PATH")
        os.environ["AUGGIE_PATH"] = str(self.fake_cli)
        self.addCleanup(self._restore_env)

    def _restore_env(self) -> None:
        if self._previous_path is None:
            os.environ.pop("AUGGIE_PATH", None)
        else:
            os.environ["AUGGIE_PATH"] = self._previous_path

    async def test_run_auggie_supports_workspace_and_model(self) -> None:
        result = await run_auggie(
            instruction="Check security",
            input_text="hello world",
            workspace_root="/tmp/workspace",
            model="claude-sonnet-4",
            compact=True,
            github_api_token="gh-token",
            extra_args=["--foo", "bar"],
        )

        stdout = result.stdout
        self.assertIn("--workspace-root /tmp/workspace", stdout)
        self.assertIn("--model claude-sonnet-4", stdout)
        self.assertIn("--foo bar", stdout)
        self.assertIn("Context:\nhello world", stdout)

    async def test_augment_review_includes_workspace_in_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ToolError) as ctx:
                await augment_review.fn(
                    instruction="fail",
                    workspace_root=tmp_dir,
                    extra_args=["--fail"],
                )

        self.assertIn("Workspace:", str(ctx.exception))
        self.assertIn(tmp_dir, str(ctx.exception))

    async def test_augment_custom_command_passes_workspace(self) -> None:
        output = await augment_custom_command.fn(
            command_name="security-review",
            arguments="src/api.py",
            workspace_root="/workspace/project",
        )

        self.assertIn("Executed command: security-review", output)
        self.assertIn("Arguments: src/api.py", output)
        self.assertIn("Workspace root: /workspace/project", output)

    async def test_augment_list_commands_returns_catalog(self) -> None:
        output = await augment_list_commands.fn(workspace_root="/workspace/project")
        self.assertIn("security-review", output)
        self.assertIn("performance-check", output)
        self.assertIn("Workspace root: /workspace/project", output)

    async def test_augment_configure_project_scope_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            permissions = [{"tool-name": "view", "permission": {"type": "allow"}}]
            message = await augment_configure.fn(
                workspace_root=tmp_dir,
                permissions=permissions,
                scope="project",
            )

            settings_path = Path(tmp_dir) / ".augment" / "settings.json"
            self.assertTrue(settings_path.is_file())
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(data["tool-permissions"], permissions)
            self.assertIn(str(settings_path), message)

    async def test_augment_configure_user_scope_uses_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_home = Path(tmp_dir) / "home"
            fake_home.mkdir()
            permissions = {"tool-name": "view", "permission": {"type": "allow"}}

            with mock.patch("augment_mcp.server.Path.home", return_value=fake_home):
                message = await augment_configure.fn(
                    workspace_root="/does/not/matter",
                    permissions=permissions,
                    scope="user",
                )

            settings_path = fake_home / ".augment" / "settings.json"
            self.assertTrue(settings_path.is_file())
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(data["tool-permissions"], permissions)
            self.assertIn(str(settings_path), message)


if __name__ == "__main__":
    unittest.main()
