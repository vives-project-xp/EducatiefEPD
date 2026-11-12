#!/usr/bin/env python3
"""Linux VM release: python3 deploy.py IMAGE@sha256:DIGEST COMMIT RUN_NUMBER.

Configuration and credentials stay in this directory on the VM. No git checkout,
database replacement, automatic schema rollback or Authentik changes occur here.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone


class DeploymentError(RuntimeError):
    pass


def validate_release(config, image, commit, number, state):
    expected = re.escape(config["image_repository"])
    if not re.fullmatch(expected + r"@sha256:[0-9a-f]{64}", image):
        raise DeploymentError("Expected configured GHCR repository and sha256 digest")
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or number < 1:
        raise DeploymentError("Invalid commit or workflow run number")
    if number < state.get("number", 0):
        raise DeploymentError("Older release refused; use a new main commit to repair")
    if number == state.get("number") and (commit != state["commit"] or image != state["image"]):
        raise DeploymentError("Same run number cannot deploy different contents")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", config["project"]):
        raise DeploymentError("Invalid Compose project name")
    if not Path(config["media_dir"]).is_absolute():
        raise DeploymentError("media_dir must be absolute")
    if not config["health_url"].startswith(("https://", "http://")):
        raise DeploymentError("health_url must be an HTTP(S) /health/ URL")


def verify_mount(container, target, kind, source):
    matches = [mount for mount in container["Mounts"] if mount["Destination"] == target]
    if len(matches) != 1:
        raise DeploymentError(f"Missing or ambiguous existing mount: {target}")
    mount = matches[0]
    actual = mount.get("Name") if kind == "volume" else mount["Source"]
    if mount["Type"] != kind or actual != source:
        raise DeploymentError(f"Existing {target} differs from deploy.json; refusing storage switch")


def save_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class Deployer:
    def __init__(self, root, config, image, commit, number):
        self.root, self.config = root, config
        self.image, self.commit, self.number = image, commit, number
        self.env = dict(os.environ, EPD_IMAGE=image, COMPOSE_PROJECT_NAME=config["project"],
                        MYSQL_VOLUME_NAME=config["mysql_volume"], MEDIA_HOST_DIR=config["media_dir"],
                        WEB_BIND=config["web_bind"], DEPLOY_HEALTH_HOST=config["health_host"])
        self.compose = ["docker", "compose", "--project-name", config["project"],
                        "--env-file", str(root / "app.env"), "-f", str(root / "compose.yaml")]

    def run(self, args, *, capture=False, output=None):
        # Never print resolved Compose config or Docker inspect (they include secrets).
        result = subprocess.run(args, cwd=self.root, env=self.env, check=True,
                                stdout=subprocess.PIPE if capture else output,
                                text=capture)
        return result.stdout.strip() if capture else None

    def cm(self, *args, **kwargs):
        return self.run(self.compose + list(args), **kwargs)

    def inspect(self, identifier):
        return json.loads(self.run(["docker", "inspect", identifier], capture=True))[0]

    def container(self, service, required=True):
        ids = self.cm("ps", "--all", "--quiet", service, capture=True).split()
        containers = [self.inspect(identifier) for identifier in ids]
        containers = [c for c in containers
                      if c["Config"]["Labels"].get("com.docker.compose.oneoff", "False").lower() != "true"]
        if len(containers) > 1 or (required and not containers):
            raise DeploymentError(f"Expected exactly one existing {service} container")
        return containers[0] if containers else None

    def external_health(self):
        # Follow no redirects: a login page or TLS redirect must not pass as health.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect())
        for attempt in range(12):
            try:
                with opener.open(self.config["health_url"], timeout=10) as response:
                    if response.status == 200 and json.load(response) == {"status": "ok"}:
                        return
            except (OSError, ValueError):
                pass
            if attempt < 11:
                time.sleep(5)
        raise DeploymentError("Public /health/ did not return HTTP 200 with status ok")

    def deploy(self):
        state_path = self.root / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        validate_release(self.config, self.image, self.commit, self.number, state)
        media = Path(self.config["media_dir"])
        if not media.is_dir() or str(media.resolve()) != str(media):
            raise DeploymentError("media_dir must be an existing canonical directory, not a symlink")
        self.cm("config", "--quiet")
        db = self.container("db")
        verify_mount(db, "/var/lib/mysql", "volume", self.config["mysql_volume"])
        if not db["State"]["Running"]:
            raise DeploymentError("Database must already be running; deployment never starts it")
        resolved = json.loads(self.cm("config", "--format", "json", capture=True))
        db_environment = dict(value.split("=", 1) for value in db["Config"]["Env"])
        if resolved["services"]["web"]["environment"]["MYSQL_DATABASE"] != db_environment["MYSQL_DATABASE"]:
            raise DeploymentError("Configured database differs from the database selected for backup")
        old = self.container("web", required=False)
        if old:
            verify_mount(old, "/app/uploads", "bind", str(media))

        print("Pulling and checking candidate image", flush=True)
        self.cm("pull", "web")
        labels = self.inspect(self.image)["Config"].get("Labels") or {}
        if labels.get("org.opencontainers.image.revision") != self.commit:
            raise DeploymentError("Image revision does not match tested commit")
        self.cm("run", "--rm", "--no-deps", "--entrypoint", "sh", "web", "-ec",
                "python manage.py check && python manage.py check_database && "
                "python manage.py collectstatic --noinput && "
                "test -w /app/uploads")

        backup = self.root / "backups" / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + self.commit[:12])
        backup.mkdir(parents=True, mode=0o700)
        migration_started = state.get("schema_may_have_changed", False) or state.get("status") in {
            "migrating", "starting", "failed_after_migration"}
        release = {"number": self.number, "commit": self.commit, "image": self.image,
                   "previous_image_id": old["Image"] if old else None,
                   "previous_release": state.get("successful_release"), "backup": str(backup),
                   "successful_release": state.get("successful_release"), "status": "backing_up",
                   "schema_may_have_changed": migration_started}
        save_json(state_path, release)
        save_json(backup / "release.json", release)
        shutil.copyfile(self.root / "app.env", backup / "app.env")
        shutil.copyfile(self.root / "deploy.json", backup / "deploy.json")
        was_running = bool(old and old["State"]["Running"])
        try:
            print("Stopping web for a consistent database + uploads backup", flush=True)
            if old:
                self.cm("stop", "web")
            with (backup / "mysql.sql").open("wb") as stream:
                self.cm("exec", "-T", "db", "sh", "-ec",
                        'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction '
                        '--routines --triggers --no-tablespaces --set-gtid-purged=OFF '
                        '--default-character-set=utf8mb4 "$MYSQL_DATABASE"', output=stream)
            with (backup / "uploads.tar.gz").open("wb") as stream:
                self.run(["docker", "run", "--rm", "--network", "none", "--user", "0",
                          "--mount", f"type=bind,src={media},dst=/backup-source,readonly",
                          "--entrypoint", "tar", self.image, "-C", "/backup-source", "-czf", "-", "."],
                         output=stream)
            if (backup / "mysql.sql").stat().st_size == 0:
                raise DeploymentError("Empty database backup")
            (backup / "BACKUP_COMPLETE").touch()

            # Past this point the old code may no longer be compatible with the schema.
            migration_started = True
            release["status"] = "migrating"
            release["schema_may_have_changed"] = True
            save_json(state_path, release)
            print("Applying migrations once", flush=True)
            self.cm("run", "--rm", "--no-deps", "--entrypoint", "python", "web",
                    "manage.py", "migrate", "--noinput")
            release["status"] = "starting"
            save_json(state_path, release)
            self.cm("up", "-d", "--no-deps", "--no-build", "--wait", "--wait-timeout", "180", "web")
            self.external_health()
            release["status"] = "healthy"
            release["schema_may_have_changed"] = False
            release["successful_release"] = {"image": self.image, "commit": self.commit,
                                             "number": self.number}
            save_json(state_path, release)
            save_json(backup / "release.json", release)
            print(f"Deployment healthy: {self.commit}", flush=True)
        except BaseException:
            release["status"] = "failed_after_migration" if migration_started else "failed_before_migration"
            save_json(state_path, release)
            if was_running and not migration_started:
                # start never recreates the old container with the candidate image.
                self.cm("start", "web")
            print(f"Deployment failed. Backup/state: {backup}. "
                  "No automatic database restore or schema rollback.", file=sys.stderr)
            raise


def main():
    import fcntl  # Linux VM only; helpers/tests can be imported on Windows.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("commit")
    parser.add_argument("number", type=int)
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(__file__).resolve().parent
    with (root / ".deploy.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        config = json.loads((root / "deploy.json").read_text(encoding="utf-8"))
        Deployer(root, config, args.image, args.commit, args.number).deploy()


if __name__ == "__main__":
    try:
        main()
    except (DeploymentError, subprocess.CalledProcessError, OSError, ValueError, KeyError) as error:
        # Command arguments can contain secrets; report only the failure type for subprocess errors.
        message = "Docker command failed; see preceding output" if isinstance(error, subprocess.CalledProcessError) else str(error)
        sys.exit(message)
