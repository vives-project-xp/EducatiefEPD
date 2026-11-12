#!/usr/bin/env python3
"""CI only: promote an already tested digest; caller must serialize main promotions."""
import argparse
import json
import os
import subprocess
import sys

from deploy import DeploymentError
from poll import docker, release_from_image, resolve_channel, validate_repository


def promote(image, commit, number, *, run=docker):
    repository = image.split("@", 1)[0]
    validate_repository(repository)
    run("image", "pull", image)
    candidate = release_from_image(repository, image, json.loads(run("image", "inspect", image))[0])
    if candidate.commit != commit or candidate.number != number:
        raise DeploymentError("Image metadata does not match this tested workflow run")
    try:
        current = resolve_channel(repository, run)
    except subprocess.CalledProcessError as error:
        # A missing channel is expected on FIRST publication. Auth/network failures are not.
        detail = (error.stderr or "").lower()
        missing = "manifest unknown" in detail or repository + ":main: not found" in detail
        if not missing:
            raise
        current = None
    if current:
        if current.number > number:
            return "Skipped: a newer main release is already published"
        if current.number == number:
            if current != candidate:
                raise DeploymentError("This run number already published different contents; start a new run")
            return "Main channel already points to this tested release"
    run("image", "tag", image, repository + ":main")
    run("image", "push", repository + ":main")
    return f"Main release published: {candidate.image} (run {number})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("commit")
    parser.add_argument("number", type=int)
    args = parser.parse_args()
    message = promote(args.image, args.commit, args.number)
    print(message)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(message + "\n")


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        sys.exit("Release promotion failed: check GHCR permissions/connectivity. Channel was not intentionally downgraded.")
    except (DeploymentError, OSError, ValueError, KeyError) as error:
        sys.exit(str(error))
