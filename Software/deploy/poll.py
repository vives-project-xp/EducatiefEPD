#!/usr/bin/env python3
"""Pull a tested GHCR main release; activate locally with a pull.enabled file."""
import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from deploy import Deployer, DeploymentError, save_json, validate_release


@dataclass(frozen=True)
class Release:
    image: str
    commit: str
    number: int


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def validate_repository(repository):
    if not re.fullmatch(r"ghcr\.io/[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)+", repository):
        raise DeploymentError("Expected a lowercase ghcr.io/owner/image repository without a tag")


def docker(*args):
    # Capture output: never dump Docker config, image env or registry credentials.
    return subprocess.run(["docker", *args], check=True, capture_output=True,
                          text=True, timeout=900).stdout


def resolve_channel(repository, run=docker):
    """Read the digest from THIS pull, so a moving :main tag cannot change the release."""
    validate_repository(repository)
    output = run("image", "pull", repository + ":main")
    digests = set(re.findall(r"^Digest: (sha256:[0-9a-f]{64})\s*$", output, re.MULTILINE))
    if len(digests) != 1:
        raise DeploymentError("Docker pull did not return one unambiguous manifest digest")
    image = repository + "@" + digests.pop()
    # Inspect the immutable reference rather than the mutable channel name.
    info = json.loads(run("image", "inspect", image))[0]
    return release_from_image(repository, image, info)


def release_from_image(repository, image, info):
    labels = info["Config"].get("Labels") or {}
    if info.get("Os") != "linux" or info.get("Architecture") != "amd64":
        raise DeploymentError("Release must be the tested Linux/amd64 image")
    source = "https://github.com/" + repository.removeprefix("ghcr.io/")
    if labels.get("org.opencontainers.image.source", "").lower() != source:
        raise DeploymentError("Image source does not match the configured repository")
    if labels.get("io.educatiefepd.ref") != "refs/heads/main":
        raise DeploymentError("Image is not marked as a main release")
    number = labels.get("io.educatiefepd.run-number", "")
    if not re.fullmatch(r"[1-9][0-9]{0,19}", number):
        raise DeploymentError("Image lacks a valid workflow run number")
    commit = labels.get("org.opencontainers.image.revision", "")
    # Reuse the deployer's immutable-image and commit validation.
    validate_release({"image_repository": repository, "project": "validation",
                      "media_dir": str(Path.cwd().resolve()), "health_url": "http://localhost/health/"},
                     image, commit, int(number), {})
    return Release(image, commit, int(number))


def decision(config, release, state, previous_poll, retry=False):
    highwater = max((state, previous_poll), key=lambda item: item.get("number", 0))
    if release.number < highwater.get("number", 0):
        return "older"
    validate_release(config, release.image, release.commit, release.number, highwater)
    candidate = asdict(release)
    same = lambda record: all(record.get(key) == value for key, value in candidate.items())
    if same(state) and state.get("status") == "healthy":
        return "current"
    if same(previous_poll) and not retry:
        return "needs_retry"
    # Also protect a previously interrupted/manual deployment that bypassed this poller.
    if same(state) and state.get("status") != "healthy" and not retry:
        return "needs_retry"
    return "deploy"


def poll_once(root, *, check=False, retry=False, resolve=resolve_channel, deployer=Deployer):
    if not check and not (root / "pull.enabled").is_file():
        print("Automatic deployment paused: pull.enabled is absent", flush=True)
        return "paused"
    config = read_json(root / "deploy.json")
    release = resolve(config["image_repository"])
    state = read_json(root / "state.json")
    poll_path = root / "pull-state.json"
    action = decision(config, release, state, read_json(poll_path), retry)
    print(f"Main release {release.number}, {release.commit}: {action}", flush=True)
    if check:
        print("Check only: no containers, migrations or deployment state changed", flush=True)
        return action
    if action == "needs_retry":
        raise DeploymentError("Release was already attempted. Inspect logs/state; use --retry only after diagnosis")
    if action != "deploy":
        return action
    attempt = {**asdict(release), "status": "deploying"}
    # Persist before deployment: a crash or disconnect must not trigger a migration loop.
    save_json(poll_path, attempt)
    try:
        deployer(root, config, release.image, release.commit, release.number).deploy()
    except BaseException:
        save_json(poll_path, {**attempt, "status": "failed"})
        raise
    save_json(poll_path, {**attempt, "status": "healthy"})
    return "healthy"


def main():
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="pull and validate only; never deploy")
    mode.add_argument("--retry", action="store_true", help="explicitly retry the previously failed release")
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(__file__).resolve().parent
    with (root / ".deploy.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another deployment/check holds the VM lock; skipping", flush=True)
            return
        poll_once(root, check=args.check, retry=args.retry)


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        sys.exit("Docker registry/deploy command failed. Check GHCR login, package access, connectivity and deployment logs.")
    except (DeploymentError, OSError, ValueError, KeyError) as error:
        sys.exit(str(error))
