#!/usr/bin/env python3
"""Install this pi config into a pi agent directory (Windows, macOS, Linux).

    python3 install.py                      # install into the agent dir
    python3 install.py --agent-dir /tmp/pi  # install somewhere else (testing)
    python3 install.py --dry-run            # show what would change, touch nothing
    python3 install.py --list               # list what this config ships
    python3 install.py --force              # overwrite without keeping a backup
    python3 install.py --shell bash         # force the shell tool instead of auto-detect
    python3 install.py --apply-patches      # also patch installed npm packages (needs node)

The agent directory defaults to $PI_CODING_AGENT_DIR, else ~/.pi/agent - the same
resolution pi itself uses (a leading ~ is expanded).

Existing files are backed up as <name>.bak-<timestamp> unless --force is given.
Credentials and machine state are never copied or touched: auth.json,
models-store.json, trust.json, sessions/, npm/, git/, bin/ and skills/.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
SOURCE = REPO / "agent"
SETTINGS = Path("settings.json")
SHELL_TOOLS = ("bash", "powershell")
SHELL_CHOICES = ("auto", *SHELL_TOOLS, "keep")

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
    """Same resolution pi uses: $PI_CODING_AGENT_DIR, else ~/.pi/agent."""
    override = os.environ.get("PI_CODING_AGENT_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".pi" / "agent"


def target_shell(choice: str) -> str | None:
    """The shell tool that works on this machine, or None to leave the file as-is."""
    if choice == "keep":
        return None
    if choice in SHELL_TOOLS:
        return choice
    return "powershell" if sys.platform == "win32" else "bash"


def adapt_settings(data: bytes, want: str) -> tuple[bytes, str | None]:
    """Point defaultTools at a shell tool this platform has.

    pi's powershell tool only exists on Windows, so shipping the Windows set
    verbatim to Linux gives the model a tool that always errors. Rewrites the
    list in place (preserving order) and only when the swap is unambiguous.
    """
    try:
        settings = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return data, None
    tools = settings.get("defaultTools")
    if not isinstance(tools, list):
        return data, None
    present = [tool for tool in tools if tool in SHELL_TOOLS]
    if not present or len(present) > 1 or present[0] == want:
        return data, None  # no shell tool, both requested, or already correct
    settings["defaultTools"] = [want if tool in SHELL_TOOLS else tool for tool in tools]
    note = f"defaultTools: {present[0]} -> {want}"
    return (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), note


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


def build_payload(files: list[Path], shell: str | None) -> tuple[dict[Path, bytes], list[str]]:
    """Bytes to install for each file, plus any adaptation notes."""
    payload: dict[Path, bytes] = {}
    notes: list[str] = []
    for rel in files:
        data = (SOURCE / rel).read_bytes()
        if rel == SETTINGS and shell:
            data, note = adapt_settings(data, shell)
            if note:
                notes.append(f"{rel.as_posix()}: {note}")
        payload[rel] = data
    return payload, notes


def plan(payload: dict[Path, bytes], agent_dir: Path) -> list[tuple[Path, str]]:
    actions: list[tuple[Path, str]] = []
    for rel in payload:
        dst = agent_dir / rel
        if not dst.exists():
            actions.append((rel, "create"))
        elif dst.read_bytes() == payload[rel]:
            actions.append((rel, "unchanged"))
        else:
            actions.append((rel, "update"))
    return actions


def apply(
    actions: list[tuple[Path, str]],
    payload: dict[Path, bytes],
    agent_dir: Path,
    force: bool,
) -> None:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for rel, action in actions:
        if action == "unchanged":
            print(f"  = {rel.as_posix()}")
            continue
        dst = agent_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and not force:
            backup = dst.with_name(f"{dst.name}.bak-{stamp}")
            shutil.copy2(dst, backup)
            print(f"  ~ {rel.as_posix()}  (backup: {backup.name})")
        dst.write_bytes(payload[rel])
        print(f"  + {rel.as_posix()}")


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
    shells = [tool for tool in tools if tool in SHELL_TOOLS]
    if shells:
        print(f"\nShell tool: {', '.join(shells)}")
        if "bash" in shells and "powershell" not in shells and sys.platform != "win32":
            print("  resolved by pi: /bin/bash, else bash on PATH")
        if "bash" in shells and sys.platform == "win32":
            print("  note: without Git for Windows, the bash tool resolves to the WSL bash stub")
        if "powershell" in shells and sys.platform != "win32":
            print("  WARNING: the powershell tool does not exist here - re-run with --shell bash")
    elif tools:
        print("\nShell tool: (none enabled - the model cannot run shell commands)")

    packages = data.get("packages") or []
    if packages:
        print("\nPlugins / packages (pi installs these on next start):")
        for package in packages:
            print(f"  - {package}")


def apply_patches(agent_dir: Path, dry_run: bool) -> None:
    """Re-apply local patches to an installed npm package (turn-stats token units).

    The target is resolved inside *this* agent dir, never the default one, so
    installing to a scratch directory cannot touch a real pi install.
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
        print(
            f"\npatches: {target} not present yet - start pi so it installs its "
            "packages, then re-run with --apply-patches"
        )
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
        help="target agent directory (default: $PI_CODING_AGENT_DIR or %(default)s)",
    )
    parser.add_argument("--dry-run", action="store_true", help="show actions, change nothing")
    parser.add_argument("--force", action="store_true", help="overwrite without backups")
    parser.add_argument("--list", action="store_true", help="list the files and exit")
    parser.add_argument(
        "--shell",
        choices=SHELL_CHOICES,
        default="auto",
        help="shell tool for defaultTools: auto (powershell on Windows, bash elsewhere), "
        "or an explicit choice, or keep to install settings.json verbatim",
    )
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
            print(f"  agent/{rel.as_posix()}")
        return 0

    agent_dir = args.agent_dir.expanduser()
    payload, notes = build_payload(files, target_shell(args.shell))
    actions = plan(payload, agent_dir)

    if args.dry_run:
        print(f"Dry run - target: {agent_dir}")
        for note in notes:
            print(f"  ~ would adapt {note}")
        for rel, action in actions:
            print(f"  {'=' if action == 'unchanged' else '+'} agent/{rel.as_posix()}  ({action})")
        if args.apply_patches:
            apply_patches(agent_dir, dry_run=True)
        print("\nNothing was written.")
        return 0

    print(f"Installing into {agent_dir}")
    for note in notes:
        print(f"  ~ adapting settings.json {note}")
    apply(actions, payload, agent_dir, args.force)
    counts = {kind: sum(1 for _, act in actions if act == kind) for kind in ("create", "update", "unchanged")}
    print(
        f"\nDone: {counts['create']} created, {counts['update']} updated, "
        f"{counts['unchanged']} unchanged."
    )
    report_settings(agent_dir)
    if args.apply_patches:
        apply_patches(agent_dir, dry_run=False)
    print("\nNext: start pi, or run /reload in a running session.")
    print("Keys: set COMMANDCODE_API_KEY / EXPLABL_API_KEY, or edit auth.json (not shipped).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
