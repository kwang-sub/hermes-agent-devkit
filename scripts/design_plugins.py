#!/usr/bin/env python3
"""Initial design-plugin setup. Reuses Hermes CLI; never publishes or wakes agents."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "shared/design-plugins/hermes-pack.yaml"
SAMPLE = ROOT / "shared/design-plugins/sample-decisions.json"
IDENTITIES = {
    "https://github.com/dyiapanis/tabella": "tabella",
    "https://github.com/apelabs-dev/hermes-mock-review": "mock-review",
    "https://github.com/nosliwhtes/hardlight-ui": "hardlight-ui",
}


class SetupError(RuntimeError):
    """An explicit, non-destructive setup failure."""


def mapping(value, label: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SetupError(f"{label} must be a mapping")
    return value


def load_yaml(path: Path) -> dict:
    try:
        return mapping(yaml.safe_load(path.read_text(encoding="utf-8")), path.name)
    except (OSError, yaml.YAMLError) as exc:
        raise SetupError(f"Cannot read {path.name}: {type(exc).__name__}") from exc


def load_pack(path: Path = PACK) -> dict:
    pack = load_yaml(path)
    rows = pack.get("plugins")
    if not isinstance(rows, list) or len(rows) != len(IDENTITIES):
        raise SetupError("Expected exactly the three approved initial plugins")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"repo", "ref"}:
            raise SetupError("Plugin entries must contain only repo and ref")
        if row["repo"] not in IDENTITIES or row["repo"] in seen:
            raise SetupError("Unknown or duplicate plugin source")
        if not re.fullmatch(r"[0-9a-f]{40}", str(row["ref"])):
            raise SetupError("Plugin refs must be exact 40-character commit SHAs")
        seen.add(row["repo"])
    config = mapping(pack.get("config"), "Pack config")
    if set(config) != {"mock-review"}:
        raise SetupError("Only mock-review config seeds are allowed")
    safe = mapping(config["mock-review"], "Mock Review defaults")
    required = {
        "autostart": False, "wake_required": False, "wake_toolsets": [],
        "default_host": "local", "host": "0.0.0.0", "port": 8790,
        "local_base": "http://127.0.0.1:8790", "lan_address": "127.0.0.1",
        "footer_button": "send", "offer_live_demo": False,
        "auto_close_idle_days": 0, "keep_closed_days": 0,
    }
    for key, value in required.items():
        if key not in safe or type(safe[key]) is not type(value) or safe[key] != value:
            raise SetupError(f"Unsafe pack default: {key}")
    if any(re.search(r"secret|token|password|api_key|allow_", k) for k in safe):
        raise SetupError("Secrets and capability grants are not pack defaults")
    return pack


def run(argv: list[str], *, capture: bool = False, timeout: int = 600) -> str:
    """Bound each finite command and clean up its process group on timeout."""
    kwargs = {"text": True, "start_new_session": os.name == "posix"}
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc = subprocess.Popen(argv, **kwargs)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            proc.communicate()
        raise SetupError("Command interrupted or timed out; inspect partial installation") from None
    if proc.returncode:
        # Do not echo captured diagnostics: third-party commands can contain secrets.
        raise SetupError(f"Command failed (exit {proc.returncode}): {Path(argv[0]).name}")
    return out or ""


def config_at(home: Path) -> dict:
    return load_yaml(home / "config.yaml")


def check_config(home: Path, pack: dict, *, complete: bool = False) -> list[str]:
    config = config_at(home)
    plugins = mapping(config.get("plugins"), "plugins")
    entries = mapping(plugins.get("entries"), "plugins.entries")
    current = mapping(entries.get("mock-review"), "mock-review config")
    missing = []
    for key, expected in pack["config"]["mock-review"].items():
        if key not in current:
            missing.append(key)
        elif type(current[key]) is not type(expected) or current[key] != expected:
            raise SetupError(f"Existing mock-review.{key} conflicts; not overwritten")
        env_name = "MOCKREVIEW_" + key.upper()
        if env_name in os.environ:
            raw = os.environ[env_name]
            try:
                actual = yaml.safe_load(raw)
            except yaml.YAMLError:
                actual = raw
            if type(actual) is not type(expected) or actual != expected:
                raise SetupError(f"Environment override conflicts: {env_name}")
    # An alternate store could expose unrelated reviews or lose persistence.
    for key, env_name in (("data_dir", "MOCKREVIEW_HOME"), ("public_base", "MOCKREVIEW_PUBLIC_BASE")):
        if current.get(key) or os.environ.get(env_name):
            raise SetupError(f"Existing mock-review.{key} override needs separate review")
    if current.get("owner", "auto") != "auto" or os.environ.get("MOCKREVIEW_OWNER", "auto") != "auto":
        raise SetupError("Initial setup requires Mock Review's checked service ownership")
    if complete and missing:
        raise SetupError("Missing local-only settings; run install first")
    return missing


def installed_dir(home: Path, plugin_id: str) -> Path | None:
    root = home / "plugins"
    if not root.exists():
        return None
    found = []
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        for filename in ("plugin.yaml", "plugin.json"):
            manifest = directory / filename
            if manifest.is_file():
                if load_yaml(manifest).get("name") == plugin_id:
                    if directory.is_symlink() or not directory.resolve().is_relative_to(root.resolve()):
                        raise SetupError(f"Refusing linked plugin directory: {plugin_id}")
                    found.append(directory)
                break
    if len(found) > 1:
        raise SetupError(f"Ambiguous installed plugin: {plugin_id}")
    return found[0] if found else None


def plugin_keys(home: Path, plugin_id: str, directory: Path | None = None) -> set[str]:
    """Hermes can persist the directory key rather than a manifest display name."""
    keys = {plugin_id}
    keys.update(repo.rsplit("/", 1)[-1] for repo, name in IDENTITIES.items() if name == plugin_id)
    if directory is not None:
        try:
            keys.add(directory.relative_to(home / "plugins").as_posix())
        except ValueError as exc:
            raise SetupError("Plugin registration is outside the active plugin store") from exc
    return keys


def plugin_enabled(home: Path, plugin_id: str, directory: Path | None) -> bool:
    plugins = mapping(config_at(home).get("plugins"), "plugins")
    enabled, disabled = plugins.get("enabled", []), plugins.get("disabled", [])
    if not isinstance(enabled, list) or not isinstance(disabled, list):
        raise SetupError("plugins.enabled and plugins.disabled must be lists")
    keys = plugin_keys(home, plugin_id, directory)
    return bool(keys.intersection(enabled)) and not keys.intersection(disabled)


def verify_pin(directory: Path, row: dict) -> None:
    head = run(["git", "-C", str(directory), "rev-parse", "HEAD"], capture=True, timeout=30).strip()
    origin = run(["git", "-C", str(directory), "remote", "get-url", "origin"], capture=True, timeout=30).strip()
    dirty = run(["git", "-C", str(directory), "status", "--porcelain", "--untracked-files=normal"], capture=True, timeout=30)
    # The installer may add its own untracked catalog receipt; nothing else is ignored.
    changed = [line for line in dirty.splitlines() if line != "?? .hermes-catalog.json"]
    if head != row["ref"] or origin.removesuffix(".git").rstrip("/") != row["repo"] or changed:
        raise SetupError(f"Installed source/revision/worktree differs: {IDENTITIES[row['repo']]}; not overwritten")


def backup_config(home: Path) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = home / "devkit-state/design-plugins" / f"{stamp}-{uuid.uuid4().hex[:8]}"
    folder.mkdir(parents=True, mode=0o700)
    os.chmod(folder, 0o700)
    target = folder / "config.yaml"
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write((home / "config.yaml").read_bytes())
    return target


def install(home: Path, pack: dict, native: list[str]) -> None:
    check_config(home, pack)
    plugins = mapping(config_at(home).get("plugins"), "plugins")
    disabled = plugins.get("disabled", [])
    if not isinstance(disabled, list):
        raise SetupError("plugins.disabled must be a list")
    if any(plugin_keys(home, name).intersection(disabled) for name in IDENTITIES.values()):
        raise SetupError("An initial plugin is explicitly disabled; existing choice preserved")
    installed = {}
    for row in pack["plugins"]:
        name = IDENTITIES[row["repo"]]
        directory = installed_dir(home, name)
        if directory:
            if plugin_keys(home, name, directory).intersection(disabled):
                raise SetupError("An installed plugin is explicitly disabled; existing choice preserved")
            verify_pin(directory, row)
        installed[name] = directory
    backup_config(home)
    # Never use --force, remove, automatic updates, or hand-written plugin files.
    for row in pack["plugins"]:
        name = IDENTITIES[row["repo"]]
        if installed[name] is None:
            print(f"[DESIGN] Installing pinned plugin: {name}", flush=True)
            run(native + ["plugins", "install", row["repo"], "--ref", row["ref"], "--no-enable"])
        directory = installed_dir(home, name)
        if directory is None:
            raise SetupError(f"Native installer did not register {name}")
        verify_pin(directory, row)
        run(native + ["plugins", "validate", str(directory)])
    # Native config writes merge individual keys. Read afresh to avoid replacing edits.
    for key, expected in pack["config"]["mock-review"].items():
        if key in check_config(home, pack):
            run(native + ["config", "set", f"plugins.entries.mock-review.{key}", expected if isinstance(expected, str) else json.dumps(expected)])
    check_config(home, pack, complete=True)
    for name in IDENTITIES.values():
        run(native + ["plugins", "enable", name])
        if not plugin_enabled(home, name, installed_dir(home, name)):
            raise SetupError(f"Native enable did not confirm activation for {name}; inspect native output")
    print("[DESIGN] Installation completed. Existing sessions may require supported reload/restart.")
    print("[DESIGN] Document generation, browser reachability and feedback round-trip remain runtime checks.")


def review_command(mode: str, *, review_id: str | None = None, decisions: Path | None = None) -> list[str]:
    if mode == "serve":
        return ["mockreview", "serve", "--host", "0.0.0.0", "--port", "8790", "--no-worker"]
    if mode == "feedback":
        if not review_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", review_id):
            raise SetupError("A valid review ID is required")
        return ["mockreview", "feedback", review_id, "--json"]
    if mode in ("sample", "create"):
        path = SAMPLE if mode == "sample" else decisions
        if path is None or not path.is_file() or path.stat().st_size >= 3_000_000:
            raise SetupError("An existing decisions JSON smaller than 3 MB is required")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SetupError("Cannot read decisions JSON") from exc
        if not isinstance(data, dict) or not isinstance(data.get("blocks"), list) or not 1 <= len(data["blocks"]) <= 60:
            raise SetupError("Decisions JSON requires 1 to 60 blocks")
        cmd = ["mockreview", "create", "--title", "DevKit local design review",
                "--platform", "cli", "--chat-id", "devkit-local", "--mode", "local",
                "--no-wake", "--no-allow-live-demo", "--footer-button", "send", "--decisions", str(path.resolve())]
        if mode == "sample":
            cmd.append("--no-design")
        return cmd
    raise SetupError(f"Unsupported review action: {mode}")


def status(home: Path, pack: dict, native: list[str]) -> bool:
    rows = []
    check_config(home, pack, complete=True)
    for row in pack["plugins"]:
        name = IDENTITIES[row["repo"]]
        directory = installed_dir(home, name)
        if directory:
            verify_pin(directory, row)
        rows.append({"id": name, "pin_verified": directory is not None,
                     "enabled_in_config": plugin_enabled(home, name, directory)})
    ready = all(row["pin_verified"] and row["enabled_in_config"] for row in rows)
    if ready:
        run(native + ["mockreview", "--help"], capture=True, timeout=60)
    print(json.dumps({"plugins": rows, "static_installation_ready": ready,
        "runtime_tool_calls": "NOT_CHECKED", "document_rendering": "NOT_CHECKED",
        "feedback_round_trip": "NOT_CHECKED", "windows_browser": "NOT_CHECKED",
        "available_commands": {name: bool(shutil.which(name)) for name in
            ("libreoffice", "soffice", "pandoc", "pdftoppm", "fc-match")}}, indent=2))
    return ready


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "install", "status", "serve", "sample", "create", "feedback"))
    parser.add_argument("--hermes", default=os.environ.get("HERMES_BIN", "/opt/hermes/.venv/bin/hermes"))
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--review-id")
    args = parser.parse_args(argv)
    try:
        pack = load_pack()
        if args.mode == "plan":
            print(json.dumps({"plugins": pack["plugins"], "config": pack["config"],
                              "publishing": False, "automatic_wake": False}, indent=2))
            return 0
        home_value = os.environ.get("HERMES_HOME")
        if not home_value:
            raise SetupError("HERMES_HOME is not set; use the initialized DevKit default environment")
        home = Path(home_value).resolve()
        if not home.is_relative_to(Path("/opt/data")):
            raise SetupError("HERMES_HOME is outside the persistent /opt/data mount; refused")
        if not Path(args.hermes).is_file():
            raise SetupError("Hermes CLI is missing; no automatic Hermes update is performed")
        if os.geteuid() == 0:
            raise SetupError("Run as the hermes user, not root")
        native = [args.hermes, "-p", "default"]
        if args.mode == "install":
            version = run(native + ["--version"], capture=True, timeout=30)
            match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", version)
            if not match or tuple(map(int, match.groups())) < (0, 22, 0):
                raise SetupError("Hermes >=0.22.0 is required; verify the installed version")
            install(home, pack, native)
            return 0
        if args.mode == "status":
            return 0 if status(home, pack, native) else 1
        check_config(home, pack, complete=True)
        row = next(row for row in pack["plugins"] if IDENTITIES[row["repo"]] == "mock-review")
        directory = installed_dir(home, "mock-review")
        if directory is None:
            raise SetupError("mock-review is not installed")
        verify_pin(directory, row)
        cmd = native + review_command(args.mode, review_id=args.review_id, decisions=args.decisions)
        if args.mode == "serve":
            # A user-owned foreground server: no daemon, service or wake worker.
            os.execv(cmd[0], cmd)
        run(cmd, timeout=120)
        return 0
    except (SetupError, OSError) as exc:
        print(f"[DESIGN] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
