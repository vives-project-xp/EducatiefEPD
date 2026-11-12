"""Release-channel ordering and automatic-deployment failure paths, without Docker."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import poll
import promote

REPO = "ghcr.io/example/epd"
IMAGE = REPO + "@sha256:" + "a" * 64
COMMIT = "b" * 40
RELEASE = poll.Release(IMAGE, COMMIT, 10)


def metadata(release=RELEASE):
    return {"Os": "linux", "Architecture": "amd64", "Config": {"Labels": {
        "org.opencontainers.image.source": "https://github.com/example/EPD",
        "org.opencontainers.image.revision": release.commit,
        "io.educatiefepd.ref": "refs/heads/main",
        "io.educatiefepd.run-number": str(release.number),
    }}}


class PullTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {"project": "software", "media_dir": str(self.root),
                       "health_url": "http://localhost/health/", "image_repository": REPO}
        poll.save_json(self.root / "deploy.json", self.config)
        (self.root / "pull.enabled").touch()
        self.resolve = Mock(return_value=RELEASE)
        self.deployer = Mock()

    def call(self, **kwargs):
        return poll.poll_once(self.root, resolve=self.resolve, deployer=self.deployer, **kwargs)

    def save_state(self, **kwargs):
        poll.save_json(self.root / "state.json", {**asdict(RELEASE), **kwargs})

    def test_pull_resolves_digest_before_inspecting_a_moving_tag(self):
        run = Mock(side_effect=["Downloaded\nDigest: sha256:" + "a" * 64 + "\n",
                                json.dumps([metadata()])])
        self.assertEqual(poll.resolve_channel(REPO, run), RELEASE)
        self.assertEqual(run.call_args_list[1].args, ("image", "inspect", IMAGE))

    def test_missing_or_ambiguous_digest_fails_closed(self):
        for output in ["Downloaded", "Digest: sha256:" + "a" * 64 + "\nDigest: sha256:" + "c" * 64]:
            with self.subTest(output=output), self.assertRaises(poll.DeploymentError):
                poll.resolve_channel(REPO, Mock(return_value=output))

    def test_untrusted_metadata_is_rejected(self):
        for key, value in [("io.educatiefepd.ref", "refs/pull/1/merge"),
                           ("io.educatiefepd.run-number", ""),
                           ("io.educatiefepd.run-number", "0"),
                           ("org.opencontainers.image.revision", "not-a-commit"),
                           ("org.opencontainers.image.source", "https://github.com/other/project")]:
            info = metadata()
            info["Config"]["Labels"][key] = value
            with self.subTest(key=key), self.assertRaises(poll.DeploymentError):
                poll.release_from_image(REPO, IMAGE, info)
        info = metadata()
        info["Architecture"] = "arm64"
        with self.assertRaises(poll.DeploymentError):
            poll.release_from_image(REPO, IMAGE, info)

    def test_pause_does_not_contact_registry(self):
        (self.root / "pull.enabled").unlink()
        self.assertEqual(self.call(), "paused")
        self.resolve.assert_not_called()

    def test_check_pulls_but_never_deploys_or_writes_state(self):
        (self.root / "pull.enabled").unlink()
        self.assertEqual(self.call(check=True), "deploy")
        self.deployer.assert_not_called()
        self.assertFalse((self.root / "state.json").exists())
        self.assertFalse((self.root / "pull-state.json").exists())

    def test_healthy_current_release_never_redeploys(self):
        self.save_state(status="healthy")
        self.assertEqual(self.call(), "current")
        self.deployer.assert_not_called()

    def test_successful_new_release_uses_immutable_reference(self):
        self.assertEqual(self.call(), "healthy")
        self.deployer.assert_called_once_with(self.root, self.config, IMAGE, COMMIT, 10)
        self.deployer.return_value.deploy.assert_called_once()
        self.assertEqual(poll.read_json(self.root / "pull-state.json")["status"], "healthy")

    def test_failure_is_recorded_and_not_retried_each_minute(self):
        self.deployer.return_value.deploy.side_effect = poll.DeploymentError("migration failed")
        with self.assertRaises(poll.DeploymentError):
            self.call()
        self.assertEqual(poll.read_json(self.root / "pull-state.json")["status"], "failed")
        self.deployer.reset_mock()
        with self.assertRaises(poll.DeploymentError):
            self.call()
        self.deployer.assert_not_called()

    def test_explicit_retry_and_newer_release_are_allowed_after_failure(self):
        failed = {**asdict(RELEASE), "status": "failed"}
        self.assertEqual(poll.decision(self.config, RELEASE, {}, failed, retry=True), "deploy")
        newer = poll.Release(REPO + "@sha256:" + "c" * 64, "d" * 40, 11)
        self.assertEqual(poll.decision(self.config, newer, {}, failed), "deploy")

    def test_interrupted_or_manual_failed_release_requires_diagnosis(self):
        for status in ["deploying", "failed", "migrating", "backing_up"]:
            record = {**asdict(RELEASE), "status": status}
            with self.subTest(status=status):
                self.assertEqual(poll.decision(self.config, RELEASE, {}, record), "needs_retry")
                self.assertEqual(poll.decision(self.config, RELEASE, record, {}), "needs_retry")

    def test_success_recorded_before_poller_crash_is_not_redeployed(self):
        self.assertEqual(poll.decision(self.config, RELEASE, {**asdict(RELEASE), "status": "healthy"},
                                       {**asdict(RELEASE), "status": "deploying"}), "current")

    def test_older_channel_is_ignored_even_if_latest_attempt_failed_preflight(self):
        older = poll.Release(REPO + "@sha256:" + "c" * 64, "d" * 40, 9)
        self.assertEqual(poll.decision(self.config, older, {}, {**asdict(RELEASE), "status": "failed"}), "older")

    def test_same_run_cannot_change_contents_even_after_failed_preflight(self):
        changed = poll.Release(REPO + "@sha256:" + "c" * 64, COMMIT, 10)
        with self.assertRaises(poll.DeploymentError):
            poll.decision(self.config, changed, {}, {**asdict(RELEASE), "status": "failed"})

    def test_registry_failure_leaves_app_and_attempt_state_untouched(self):
        self.resolve.side_effect = subprocess.CalledProcessError(1, ["docker", "pull"])
        with self.assertRaises(subprocess.CalledProcessError):
            self.call()
        self.deployer.assert_not_called()
        self.assertFalse((self.root / "pull-state.json").exists())


class PromotionTests(unittest.TestCase):
    def runner(self, current=None, error=None):
        def execute(*args):
            if args == ("image", "inspect", IMAGE):
                return json.dumps([metadata()])
            if args == ("image", "pull", REPO + ":main"):
                if error:
                    raise error
                if current is None:
                    raise subprocess.CalledProcessError(1, ["docker", "pull"], stderr="manifest unknown")
                return "Digest: " + current.image.split("@", 1)[1] + "\n"
            if current and args == ("image", "inspect", current.image):
                return json.dumps([metadata(current)])
            return ""
        return Mock(side_effect=execute)

    def test_first_publication_promotes_exact_tested_digest(self):
        run = self.runner()
        promote.promote(IMAGE, COMMIT, 10, run=run)
        self.assertIn(unittest.mock.call("image", "tag", IMAGE, REPO + ":main"), run.call_args_list)
        self.assertEqual(run.call_args_list[-1].args, ("image", "push", REPO + ":main"))

    def test_first_publication_handles_containerd_missing_tag_message(self):
        run = self.runner(error=subprocess.CalledProcessError(1, ["docker"],
                          stderr=f'failed to resolve reference "{REPO}:main": {REPO}:main: not found'))
        promote.promote(IMAGE, COMMIT, 10, run=run)
        self.assertEqual(run.call_args_list[-1].args, ("image", "push", REPO + ":main"))

    def test_out_of_order_older_run_does_not_overwrite_newer_channel(self):
        run = self.runner(poll.Release(REPO + "@sha256:" + "c" * 64, "d" * 40, 11))
        self.assertIn("newer", promote.promote(IMAGE, COMMIT, 10, run=run))
        self.assertFalse(any("push" in call.args or "tag" in call.args for call in run.call_args_list))

    def test_identical_retry_is_idempotent(self):
        run = self.runner(RELEASE)
        self.assertIn("already", promote.promote(IMAGE, COMMIT, 10, run=run))
        self.assertFalse(any("push" in call.args for call in run.call_args_list))

    def test_same_run_with_different_digest_is_refused(self):
        run = self.runner(poll.Release(REPO + "@sha256:" + "c" * 64, COMMIT, 10))
        with self.assertRaises(poll.DeploymentError):
            promote.promote(IMAGE, COMMIT, 10, run=run)

    def test_auth_and_network_errors_are_not_treated_as_absent_channel(self):
        for message in ["unauthorized", "connection timed out", "name unknown"]:
            run = self.runner(error=subprocess.CalledProcessError(1, ["docker"], stderr=message))
            with self.subTest(message=message), self.assertRaises(subprocess.CalledProcessError):
                promote.promote(IMAGE, COMMIT, 10, run=run)
            self.assertFalse(any("push" in call.args for call in run.call_args_list))

    def test_wrong_commit_or_run_fails_before_channel_update(self):
        for commit, number in [("d" * 40, 10), (COMMIT, 11)]:
            with self.subTest(commit=commit, number=number), self.assertRaises(poll.DeploymentError):
                promote.promote(IMAGE, commit, number, run=self.runner())


@unittest.skipUnless(sys.platform.startswith("linux"), "Real flock/CLI integration requires Linux")
class LinuxPollCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = Path(__file__).resolve().parents[1]
        for filename in ("poll.py", "deploy.py"):
            shutil.copyfile(source / filename, self.root / filename)
        poll.save_json(self.root / "deploy.json", {
            "project": "software", "media_dir": str(self.root), "health_url": "http://localhost/health/",
            "image_repository": REPO})
        binary = self.root / "bin"
        binary.mkdir()
        stub = binary / "docker"
        stub.write_text("#!/usr/bin/env python3\nimport sys\n"
                        "args = sys.argv[1:]\n"
                        f"open({str(self.root / 'docker-calls')!r}, 'a').write(repr(args) + '\\n')\n"
                        "if args[:2] == ['image', 'pull']:\n"
                        f"    print('Digest: sha256:{'a' * 64}')\n"
                        "elif args[:2] == ['image', 'inspect']:\n"
                        f"    print({json.dumps([metadata()])!r})\n"
                        "else:\n    sys.exit(99)\n", encoding="utf-8")
        stub.chmod(0o700)
        self.env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}

    def command(self, *args):
        return subprocess.run([sys.executable, str(self.root / "poll.py"), *args],
                              env=self.env, capture_output=True, text=True, check=True, timeout=10).stdout

    def test_real_cli_check_resolves_release_without_deployment(self):
        self.assertIn("Check only", self.command("--check"))
        self.assertFalse((self.root / "state.json").exists())
        self.assertFalse((self.root / "pull-state.json").exists())

    def test_real_cli_is_paused_without_local_enable_file(self):
        self.assertIn("paused", self.command())
        self.assertFalse((self.root / "docker-calls").exists())

    def test_real_vm_lock_prevents_second_process_from_contacting_registry(self):
        import fcntl
        with (self.root / ".deploy.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertIn("holds the VM lock", self.command("--check"))
        self.assertFalse((self.root / "docker-calls").exists())


if __name__ == "__main__":
    unittest.main()
