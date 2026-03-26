#!/usr/bin/env python3
"""
Download and install Sandstorm mods listed in a Mods.txt file via mod.io.

This script:
  - reads mod IDs from Mods.txt
  - queries mod.io for the live Linux Server modfile
  - downloads the mod archive
  - extracts it into the target workshop directory

Usage example:
  python3 scripts/modio_download_mods.py \
    --mods-file /AMP/insurgencysandstorm/581330/Insurgency/Config/Server/Mods.txt \
    --content-dir /AMP/insurgencysandstorm/581330/Steam/steamapps/workshop/content/581330 \
    --token "$MODIO_TOKEN"
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional


DEFAULT_GAME_ID = 254
DEFAULT_PLATFORM = "linuxserver"
DEFAULT_API_BASE = "https://g-254.modapi.io/v1"


@dataclasses.dataclass
class ModFile:
    mod_id: str
    file_id: int
    filename: str
    download_url: str
    date_expires: Optional[int] = None
    md5: Optional[str] = None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mods-file", type=Path, help="Path to Mods.txt")
    p.add_argument(
        "--content-dir",
        required=True,
        type=Path,
        help="Target mod content directory (one subdir per mod id)",
    )
    p.add_argument("--token", required=True, help="mod.io access token or API key")
    p.add_argument(
        "--token-mode",
        choices=("bearer", "api-key"),
        default="bearer",
        help="How to send --token to mod.io. Default: bearer",
    )
    p.add_argument("--game-id", type=int, default=DEFAULT_GAME_ID, help="mod.io game id")
    p.add_argument(
        "--platform",
        default=DEFAULT_PLATFORM,
        help="mod.io X-Modio-Platform header (default: linuxserver)",
    )
    p.add_argument(
        "--api-base",
        default=None,
        help=f"Override API base URL (default: {DEFAULT_API_BASE})",
    )
    p.add_argument(
        "--keep-archives",
        action="store_true",
        help="Keep downloaded archive files next to the extracted content",
    )
    p.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove the target mod directory before extracting",
    )
    p.add_argument(
        "--amp-root",
        type=Path,
        help="AMP instance root (contains GenericModule.kvp). Used when Mods.txt is missing.",
    )
    return p.parse_args()


def read_mod_ids(mods_file: Path) -> list[str]:
    mods: list[str] = []
    for raw in mods_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        mods.append(line)
    return mods


def read_mod_ids_from_amp(instance_root: Path) -> list[str]:
    kvp = instance_root / "GenericModule.kvp"
    if not kvp.exists():
        raise FileNotFoundError(f"GenericModule.kvp not found at {kvp}")

    app_settings_json = None
    for raw in kvp.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("App.AppSettings="):
            app_settings_json = raw.split("=", 1)[1].strip()
            break

    if not app_settings_json:
        raise RuntimeError(f"No App.AppSettings line found in {kvp}")

    settings = json.loads(app_settings_json)
    mods = settings.get("Mods")
    if isinstance(mods, str):
        try:
            mods = json.loads(mods)
        except json.JSONDecodeError:
            mods = [m.strip() for m in re.split(r"[,\s]+", mods) if m.strip()]

    if not isinstance(mods, list):
        raise RuntimeError(f"App.AppSettings Mods field is not a list in {kvp}")

    return [str(m).strip() for m in mods if str(m).strip()]


def find_amp_root(start: Path) -> Optional[Path]:
    candidates = [start, *start.parents]
    for base in candidates:
        direct = base / "GenericModule.kvp"
        if direct.exists():
            return base
        nested = base / "AMP" / "GenericModule.kvp"
        if nested.exists():
            return base / "AMP"
    return None


def build_headers(token: str, token_mode: str, platform: str) -> dict[str, str]:
    headers = {
        "User-Agent": "sandstorm-mod-downloader/1.0",
        "Accept": "application/json",
        "X-Modio-Platform": platform,
    }
    if token_mode == "bearer":
        headers["Authorization"] = f"Bearer {token}"
    else:
        headers["Authorization"] = token
    return headers


def api_get_json(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def api_get_binary(url: str, headers: dict[str, str], dst: Path) -> None:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=120) as resp, dst.open("wb") as out:
        shutil.copyfileobj(resp, out)


def pick_modfile(mod_json: dict, mod_id: str) -> ModFile:
    modfile = mod_json.get("modfile") or {}
    download = modfile.get("download") or {}
    filename = modfile.get("filename") or f"{mod_id}.zip"
    url = download.get("binary_url")
    if not url:
        raise RuntimeError(f"mod {mod_id}: no download URL returned by mod.io")
    return ModFile(
        mod_id=str(mod_id),
        file_id=int(modfile.get("id") or 0),
        filename=filename,
        download_url=url,
        date_expires=download.get("date_expires"),
        md5=(modfile.get("filehash") or {}).get("md5"),
    )


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def extract_archive(archive: Path, dest_dir: Path) -> None:
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest_dir)
        return
    raise RuntimeError(f"Unsupported archive format: {archive.name}")


def verify_md5(path: Path, expected: Optional[str]) -> None:
    if not expected:
        return
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual.lower() != expected.lower():
        raise RuntimeError(f"MD5 mismatch for {path.name}: expected {expected}, got {actual}")


def download_mod(mod_id: str, api_base: str, headers: dict[str, str], target_root: Path, keep_archives: bool, no_clean: bool) -> None:
    mod_url = f"{api_base}/games/{DEFAULT_GAME_ID}/mods/{mod_id}"
    mod_json = api_get_json(mod_url, headers)
    modfile = pick_modfile(mod_json, mod_id)

    mod_dir = target_root / str(mod_id)
    ensure_dir(target_root)
    if not no_clean:
        clean_dir(mod_dir)
    else:
        ensure_dir(mod_dir)

    archive_path = mod_dir / modfile.filename
    print(f"[{mod_id}] downloading {modfile.filename}")
    api_get_binary(modfile.download_url, headers, archive_path)
    verify_md5(archive_path, modfile.md5)
    print(f"[{mod_id}] extracted from {archive_path.name}")
    extract_archive(archive_path, mod_dir)

    if not keep_archives:
        archive_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    api_base = args.api_base or DEFAULT_API_BASE

    mod_ids: list[str] = []
    if args.mods_file and args.mods_file.exists():
        mod_ids = read_mod_ids(args.mods_file)
    else:
        amp_root = args.amp_root or find_amp_root(args.content_dir) or find_amp_root(Path.cwd())
        if amp_root is None:
            print("Mods.txt not found and AMP root could not be discovered.", file=sys.stderr)
            return 2
        mod_ids = read_mod_ids_from_amp(amp_root)
        print(f"Loaded {len(mod_ids)} mod IDs from {amp_root / 'GenericModule.kvp'}")

    if not mod_ids:
        print("No mod IDs found in Mods.txt", file=sys.stderr)
        return 1

    headers = build_headers(args.token, args.token_mode, args.platform)
    args.content_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for mod_id in mod_ids:
        try:
            download_mod(mod_id, api_base, headers, args.content_dir, args.keep_archives, args.no_clean)
        except Exception as e:
            failures += 1
            print(f"[{mod_id}] ERROR: {e}", file=sys.stderr)

    if failures:
        print(f"Completed with {failures} failure(s).", file=sys.stderr)
        return 1

    print(f"Downloaded {len(mod_ids)} mod(s) to {args.content_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
