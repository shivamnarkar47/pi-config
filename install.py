#!/usr/bin/env python3
"""Install this pi config into a pi agent directory.

    python install.py                       # install into ~/.pi/agent
    python install.py --agent-dir /tmp/pi   # install somewhere else (testing)
    python install.py --dry-run             # show what would change, touch nothing
    python install.py --list                # list what this config ships
    python install.py --force               # overwrite without keeping a backup
    python install.py --apply-patches       # also patch installed npm packages (needs node)

Existing files are backed up as <name>.bak-<timestamp> unless --force is given.
Credentials and machine state are never copied or touched: auth.json,
models-store.json, trust.json, sessions/, npm/, git/, bin/ and skills/.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
SOURCE = REPO / "agent"

# Never installed, never overwritten: credentials and per-machine state.
SKIP_TOP_LEVEL = {
    "auth.json",
    "models-store.json",
    "trust.json",
    "sessions",
    "npm",
    "git",
    "bin",
    "skills",
    "pi-herdsman",
}


def default_agent_dir() -> Path:
    return Path.home() / ".pi" / "agent"


def collect() -> list[Path]:
    """Files this config ships, relative to agent/."""
    if not SOURCE.is_dir():
        sys.exit(f"error: {SOURCE} not found - run this from the pi-config checkout")
    found = []
    for path in sorted(SOURCE.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(SOURCE)
        if rel.parts[0] in SKIP_TOP_LEVEL:
            continue
        found.append(rel)
    if not found:
        sys.exit(f"error: no files to install under {SOURCE}")
    return found


def same_bytes(a: Path, b: Path) -> bool:
    return a.read_bytes() == b.read_bytes()


def plan(files: list[Path], agent_dir: Path) -> list[tuple[Path, str]]:
    actions: list[tuple[Path, str]] = []
    for rel in files:
        src = SOURCE / rel
        dst = agent_dir / rel
        if not dst.exists():
            actions.append((rel, "create"))
        elif same_bytes(src, dst):
            actions.append((rel, "unchanged"))
        else:
            actions.append((rel, "update"))
    return actions


def apply(actions: list[tuple[Path, str]], agent_dir: Path, force: bool, dry_run: bool) -> int:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    changed = 0
    for rel, action in actions:
        src = SOURCE / rel
        dst = agent_dir / rel
        if action == "unchanged":
            print(f"  = {rel}")
            continue
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists() and not force:
                backup = dst.with_name(f"{dst.name}.bak-{stamp}")
                shutil.copy2(dst, backup)
                print(f"  ~ {rel}  (backup: {backup.name})")
            shutil.copy2(src, dst)
        print(f"  + {rel}")
        changed += 1
    return changed


def report_settings(agent_dir: Path) -> None:
    """Print the shell tool and plugin list pi will use after a restart."""
    settings = agent_dir / "settings.json"
    if not settings.is_file():
        return
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("\nsettings.json could not be parsed - check it by hand.")
        return

    tools = data.get("defaultTools") or []
    shells = [tool for tool in tools if tool in ("bash", "powershell")]
    if shells:
        print(f"\nShell tool: {', '.join(shells)}")
        if "bash" in shells:
            print("  note: without Git for Windows, the bash tool resolves to the WSL bash stub")
    elif tools:
        print("\nShell tool: (none enabled - the model cannot run shell commands)")

    packages = data.get("packages") or []
    if packages:
        print("\nPlugins / packages (pi installs these on next start):")
        for package in packages:
            print(f"  - {package}")


def apply_patches(agent_dir: Path, dry_run: bool) -> None:
    """Re-apply local patches to an installed npm package (turn-stats token units).

    The target is resolved inside *this* agent dir, never the default ~/.pi/agent,
    so installing to a scratch directory cannot touch a real pi install.
    """
    script = agent_dir / "patches" / "pi-turn-stats-units.mjs"
    if not script.is_file():
        return
    if shutil.which("node") is None:
        print("\npatches: node not found - skipped (run the patch script manually later)")
        return
    target = (
        agent_dir
        / "npm"
        / "node_modules"
        / "@marshal"
        / "pi-turn-stats"
        / "extensions"
        / "turn-stats.ts"
    )
    if not target.is_file():
        print(f"\npatches: {target} not present yet - start pi so it installs its packages, then re-run with --apply-patches")
        return
    if dry_run:
        print(f"\npatches: would run {script} {target}")
        return
    print(f"\npatches: {target}")
    result = subprocess.run(
        ["node", str(script), str(target)], capture_output=True, text=True, check=False
    )
    for line in (result.stdout + result.stderr).splitlines():
        print(f"  {line}")
    if result.returncode != 0:
        print("  patch script reported a problem - the config is installed, the patch was not")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install this pi config into a pi agent directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--agent-dir",
        type=Path,
        default=default_agent_dir(),
        help="target agent directory (default: %(default)s)",
    )
    parser.add_argument("--dry-run", action="store_true", help="show actions, change nothing")
    parser.add_argument("--force", action="store_true", help="overwrite without backups")
    parser.add_argument("--list", action="store_true", help="list the files and exit")
    parser.add_argument(
        "--apply-patches",
        action="store_true",
        help="also re-apply patches to installed npm packages (needs node)",
    )
    args = parser.parse_args()

    files = collect()

    if args.list:
        print(f"{REPO.name} ships {len(files)} file(s):")
        for rel in files:
            print(f"  agent/{rel}")
        return 0

    agent_dir = args.agent_dir.expanduser()
    actions = plan(files, agent_dir)

    if args.dry_run:
        print(f"Dry run - target: {agent_dir}")
        for rel, action in actions:
            print(f"  {'=' if action == 'unchanged' else '+'} agent/{rel}  ({action})")
        print("\nNothing was written.")
    else:
        print(f"Installing into {agent_dir}")
        changed = apply(actions, agent_dir, args.force, args.dry_run)
        counts = {a: sum(1 for _, act in actions if act == a) for a in ("create", "update", "unchanged")}
        print(
            f"\nDone: {counts['create']} created, {counts['update']} updated, "
            f"{counts['unchanged']} unchanged ({changed} written)."
        )
        report_settings(agent_dir)
        if args.apply_patches:
            apply_patches(agent_dir, args.dry_run)
        print("\nNext: start pi, or run /reload in a running session.")
        print("Keys: set COMMANDCODE_API_KEY / EXPLABS_API_KEY, or edit auth.json (not shipped).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
