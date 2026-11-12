"""Resolve Compose using ONLY dummy configuration; no daemon or real .env needed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    compose = Path(__file__).resolve().parents[1] / "compose.yaml"
    with tempfile.TemporaryDirectory() as temporary:
        app_env = Path(temporary) / "app.env"
        values = {
            "MYSQL_DATABASE": "epd_ci", "MYSQL_USER": "epd_ci", "MYSQL_PASSWORD": "dummy",
            "MYSQL_ROOT_PASSWORD": "dummy_root", "SECRET_KEY": "dummy_secret",
            "ALLOWED_HOSTS": "epd.example", "EPD_IMAGE": "ghcr.io/example/epd@sha256:" + "a" * 64,
            "WEB_BIND": "127.0.0.1", "MEDIA_HOST_DIR": str(Path(temporary).resolve()),
            "MYSQL_VOLUME_NAME": "existing_mysql", "DEPLOY_HEALTH_HOST": "epd.example",
        }
        app_env.write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")
        result = subprocess.run(["docker", "compose", "--project-name", "epd-validation",
                                 "--env-file", str(app_env), "-f", str(compose), "config", "--format", "json"],
                                env={**os.environ, **values}, capture_output=True, text=True, check=True)
        config = json.loads(result.stdout)
        web = config["services"]["web"]
        assert "build" not in web
        assert web["image"] == values["EPD_IMAGE"]
        assert web["environment"]["RUN_MIGRATIONS"] == "0"
        assert web["environment"]["SEED_DEMO"] == "0"
        assert "MYSQL_ROOT_PASSWORD" not in web["environment"]
        assert web["volumes"][0]["target"] == "/app/uploads"
        assert not web["volumes"][0].get("bind", {}).get("create_host_path", False)
        assert config["volumes"]["mysql_data"]["external"] is True
        assert config["volumes"]["mysql_data"]["name"] == "existing_mysql"
        assert web["healthcheck"]["test"] == ["CMD", "python", "/app/healthcheck.py"]
        print("Production Compose validated with dummy values; existing storage and no startup migration.")


if __name__ == "__main__":
    main()
