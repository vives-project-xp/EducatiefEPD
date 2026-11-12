"""Failure-path tests; never access Docker, SSH or real application data."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("epd_deploy", Path(__file__).parents[1] / "deploy.py")
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)
IMAGE = "ghcr.io/example/epd@sha256:" + "a" * 64
COMMIT = "b" * 40


class FakeDeployer(deploy.Deployer):
    def __init__(self, root, fault=None):
        (root / "uploads").mkdir()
        config = {"project": "software", "mysql_volume": "existing_mysql",
                  "media_dir": str((root / "uploads").resolve()), "web_bind": "127.0.0.1",
                  "health_host": "epd.example", "health_url": "https://epd.example/health/",
                  "image_repository": "ghcr.io/example/epd"}
        (root / "app.env").write_text("SECRET_KEY=dummy-for-test\n")
        (root / "deploy.json").write_text(json.dumps(config))
        super().__init__(root, config, IMAGE, COMMIT, 10)
        self.calls, self.fault = [], fault

    def container(self, service, required=True):
        mount = {"Destination": "/var/lib/mysql", "Type": "volume", "Name": "existing_mysql"}
        if service == "web":
            mount = {"Destination": "/app/uploads", "Type": "bind", "Source": self.config["media_dir"]}
        if self.fault == "mount":
            mount["Name"] = "other_database"
        return {"Image": "sha256:old-image", "State": {"Running": True}, "Mounts": [mount],
                "Config": {"Env": ["MYSQL_DATABASE=epd"]}}

    def inspect(self, identifier):
        return {"Config": {"Labels": {"org.opencontainers.image.revision":
                                       "wrong" if self.fault == "revision" else COMMIT}}}

    def run(self, args, *, capture=False, output=None):
        self.calls.append(args)
        if "--format" in args:
            database = "wrong" if self.fault == "database" else "epd"
            return json.dumps({"services": {"web": {"environment": {"MYSQL_DATABASE": database}}}})
        if (self.fault == "backup" and "mysqldump" in " ".join(args)) or (
                self.fault == "migration" and "migrate" in args) or (
                self.fault == "preflight" and "test -w /app/uploads" in " ".join(args)):
            raise subprocess.CalledProcessError(1, args)
        if output is not None:
            output.write(b"dummy backup contents")
        return "" if capture else None

    def external_health(self):
        self.calls.append(["external_health"])
        if self.fault == "health":
            raise deploy.DeploymentError("unhealthy")


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def commands(self, runner):
        return [args[len(runner.compose):] if args[:len(runner.compose)] == runner.compose else args
                for args in runner.calls]

    def test_success_backs_up_before_migration_and_only_replaces_web(self):
        runner = FakeDeployer(self.root)
        runner.deploy()
        commands = self.commands(runner)
        stop = commands.index(["stop", "web"])
        dump = next(i for i, cmd in enumerate(commands) if "mysqldump" in " ".join(cmd))
        migrate = next(i for i, cmd in enumerate(commands) if "migrate" in cmd)
        up = next(i for i, cmd in enumerate(commands) if cmd[0] == "up")
        self.assertLess(stop, dump)
        self.assertLess(dump, migrate)
        self.assertLess(migrate, up)
        self.assertIn("--no-deps", commands[up])
        self.assertIn("--no-build", commands[up])
        self.assertEqual(commands[up][-1], "web")
        self.assertEqual(sum("migrate" in cmd for cmd in commands), 1)
        self.assertFalse(any("down" in cmd for cmd in commands))
        state = json.loads((self.root / "state.json").read_text())
        self.assertEqual(state["status"], "healthy")
        self.assertEqual(state["successful_release"]["image"], IMAGE)
        self.assertTrue((Path(state["backup"]) / "BACKUP_COMPLETE").exists())

    def test_backup_failure_restarts_existing_container_without_migration(self):
        runner = FakeDeployer(self.root, "backup")
        with self.assertRaises(subprocess.CalledProcessError):
            runner.deploy()
        commands = self.commands(runner)
        self.assertIn(["start", "web"], commands)
        self.assertFalse(any("migrate" in cmd or cmd[0] == "up" for cmd in commands))
        self.assertFalse(list(self.root.glob("backups/*/BACKUP_COMPLETE")))

    def test_migration_failure_never_restarts_old_code_or_restores_database(self):
        runner = FakeDeployer(self.root, "migration")
        with self.assertRaises(subprocess.CalledProcessError):
            runner.deploy()
        self.assertNotIn(["start", "web"], self.commands(runner))
        self.assertFalse(any(cmd[0] == "up" for cmd in self.commands(runner)))
        self.assertEqual(json.loads((self.root / "state.json").read_text())["status"],
                         "failed_after_migration")

    def test_health_failure_does_not_report_success_or_rollback(self):
        runner = FakeDeployer(self.root, "health")
        with self.assertRaises(deploy.DeploymentError):
            runner.deploy()
        self.assertNotIn(["start", "web"], self.commands(runner))
        state = json.loads((self.root / "state.json").read_text())
        self.assertEqual(state["status"], "failed_after_migration")
        self.assertIsNone(state["successful_release"])

    def test_storage_mismatch_fails_before_pull_or_stop(self):
        runner = FakeDeployer(self.root, "mount")
        with self.assertRaises(deploy.DeploymentError):
            runner.deploy()
        self.assertEqual(self.commands(runner), [["config", "--quiet"]])

    def test_wrong_image_revision_fails_before_stop(self):
        runner = FakeDeployer(self.root, "revision")
        with self.assertRaises(deploy.DeploymentError):
            runner.deploy()
        self.assertNotIn(["stop", "web"], self.commands(runner))

    def test_database_selection_mismatch_fails_before_pull(self):
        runner = FakeDeployer(self.root, "database")
        with self.assertRaises(deploy.DeploymentError):
            runner.deploy()
        self.assertNotIn(["pull", "web"], self.commands(runner))

    def test_candidate_preflight_failure_leaves_existing_web_running(self):
        runner = FakeDeployer(self.root, "preflight")
        with self.assertRaises(subprocess.CalledProcessError):
            runner.deploy()
        self.assertNotIn(["stop", "web"], self.commands(runner))
        self.assertFalse((self.root / "state.json").exists())

    def test_older_run_is_rejected_before_docker(self):
        runner = FakeDeployer(self.root)
        deploy.save_json(self.root / "state.json", {"number": 11})
        with self.assertRaises(deploy.DeploymentError):
            runner.deploy()
        self.assertEqual(runner.calls, [])

    def test_mutable_tag_and_wrong_registry_are_rejected(self):
        runner = FakeDeployer(self.root)
        for image in ("ghcr.io/example/epd:latest", IMAGE.replace("example", "other")):
            with self.subTest(image=image), self.assertRaises(deploy.DeploymentError):
                deploy.validate_release(runner.config, image, COMMIT, 10, {})

    def test_same_run_cannot_change_image(self):
        runner = FakeDeployer(self.root)
        with self.assertRaises(deploy.DeploymentError):
            deploy.validate_release(runner.config, IMAGE, COMMIT, 10,
                                    {"number": 10, "commit": COMMIT, "image": IMAGE + "f"})

    def test_retry_after_migration_failure_does_not_restart_old_code_on_backup_failure(self):
        runner = FakeDeployer(self.root, "backup")
        deploy.save_json(self.root / "state.json", {"number": 9, "status": "failed_after_migration"})
        with self.assertRaises(subprocess.CalledProcessError):
            runner.deploy()
        self.assertNotIn(["start", "web"], self.commands(runner))


if __name__ == "__main__":
    unittest.main()
