import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
MIRROR_HOST = "ms-feed-25.pkgs.visualstudio.com"


def refresh(lockfile: Path) -> None:
    lock = json.loads(lockfile.read_text(encoding="utf-8"))
    cached: dict[tuple[str, str], dict[str, str]] = {}
    replacements: dict[str, dict[str, str]] = {}
    for name, entry in lock["packages"].items():
        if urlsplit(entry.get("resolved", "")).hostname != MIRROR_HOST:
            continue
        package = name.rsplit("node_modules/", 1)[1]
        version = entry["version"]
        key = (package, version)
        if key not in cached:
            spec = f"{package}@{version}"
            result = subprocess.run(
                [
                    shutil.which("npm") or "npm",
                    "view",
                    spec,
                    "dist",
                    "--json",
                    "--registry=https://registry.npmjs.org/",
                    "--prefer-online",
                    "--fetch-retries=1",
                    "--fetch-timeout=20000",
                ],
                capture_output=True,
                text=True,
                creationflags=CREATION_FLAGS,
            )
            if result.returncode != 0:
                raise RuntimeError(f"{spec}: {result.stderr.strip()}")
            dist = json.loads(result.stdout)
            tarball = dist["tarball"]
            url = urlsplit(tarball)
            if (
                url.scheme != "https"
                or url.hostname != "registry.npmjs.org"
                or url.username is not None
                or url.password is not None
            ):
                raise ValueError(f"{spec}: non-public tarball URL")
            integrity = dist["integrity"]
            if (
                not integrity.startswith("sha512-")
                or len(base64.b64decode(integrity[7:], validate=True)) != 64
            ):
                raise ValueError(f"{spec}: invalid SHA-512 integrity")
            cached[key] = {"resolved": tarball, "integrity": integrity}
            print(f"verified public metadata for {spec}", flush=True)
        replacements[name] = cached[key]

    for name, metadata in replacements.items():
        lock["packages"][name].update(metadata)
    if replacements:
        lockfile.write_text(
            json.dumps(lock, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(
        f"refreshed {len(replacements)} mirror entries from "
        f"{len(cached)} public npm lookups",
        flush=True,
    )


if __name__ == "__main__":
    refresh(Path("scenarios/http/js/package-lock.json"))
