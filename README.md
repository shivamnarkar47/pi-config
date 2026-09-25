# pi-config

My personal [pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent) configuration: the agent-directory files, my own extension, the plugin/package list, and a one-command installer.

Windows-first, PowerShell-first. No secrets — the API key in `models.json` is a `$COMMANDCODE_API_KEY` placeholder.

## Install

Any Python 3.9+ works, on Windows, macOS and Linux:

```sh
git clone https://github.com/shivamnarkar47/pi-config.git
cd pi-config
python3 install.py        # or: python install.py on Windows, ./install.py
```

No system Python? [`uv`](https://docs.astral.sh/uv/) works too: `uv run install.py`.

```
python3 install.py                    # install into the agent dir
python3 install.py --agent-dir /tmp/pi # install somewhere else (handy for testing)
python3 install.py --dry-run          # show what would change, write nothing
python3 install.py --list             # list what this config ships
python3 install.py --force            # overwrite without keeping a backup
python3 install.py --shell bash       # force the shell tool instead of auto-detecting
python3 install.py --apply-patches    # also re-apply the npm package patches (needs node)
```

The target directory defaults to `$PI_CODING_AGENT_DIR` when that is set, otherwise `~/.pi/agent` — the same resolution pi itself uses. Then start pi, or run `/reload` in a session that is already open. Existing files are backed up as `<name>.bak-<timestamp>` unless you pass `--force`.

## What gets installed

Copied into `~/.pi/agent/`:

| File | Purpose |
| --- | --- |
| `settings.json` | Theme, **package/plugin list**, and the enabled tool set |
| `models.json` | Custom providers: `explabs`, `commandcode` (local server on `127.0.0.1:18731`), `llama-cpp` |
| `AGENTS.md` | Standing user instructions (the "end the turn, never sleep on a backgrounded command" rule) |
| `extensions/background-shell.ts` | Ctrl+B backgrounds a running shell command; `/background` lists and kills jobs — see [pi-background-shell](https://github.com/shivamnarkar47/pi-background-shell) |
| `patches/pi-turn-stats-units.mjs` | Re-applies k/M/B token formatting to `@marshal/pi-turn-stats` after a package update (`--apply-patches`, or run it directly) |

## Plugins / packages

From `settings.json` → `packages`; pi installs and updates these itself on the next start:

| Package | Source | What it adds |
| --- | --- | --- |
| `pi-herdsman` | npm | herdr integration for pi (writes `extensions/herdr-agent-state.ts`, "managed by herdr") |
| `@marshal/pi-turn-stats` | npm | Per-turn stats card and status bar (duration, tokens, cost) |
| `@xynogen/pix-optimizer` | npm | Image optimization (nothing lands in the agent dir) |
| `DietrichGebert/ponytail` | git | The ponytail subagent, installed from `github.com/DietrichGebert/ponytail` |

`background-shell.ts` (above) is not a package — it is a local extension shipped in this repo.

## Shell tool: PowerShell on Windows, bash elsewhere

The repo's `settings.json` ships the Windows set `defaultTools: ["read", "powershell", "edit", "write"]`, which is what pi's own Windows guide recommends. The installer rewrites that one entry for the machine it runs on — `bash` in place of `powershell` on macOS/Linux, because pi's `powershell` tool only exists on Windows and would fail on every call. It says so when it does:

```
~ adapting settings.json defaultTools: powershell -> bash
Shell tool: bash
  resolved by pi: /bin/bash, else bash on PATH
```

Override with `--shell powershell` or `--shell bash`, or pass `--shell keep` to install `settings.json` byte-for-byte.

Two more things worth knowing:

- On Windows the `bash` tool is deliberately *not* enabled: without Git for Windows, pi resolves it to the WSL stub `C:\Windows\System32\bash.exe`, so commands would run in WSL instead of PowerShell.
- `defaultTools` is a *startup* set. `pi -t read,grep,find,ls --print "…"` overrides it for one run, and an extension can call `setActiveTools()` at runtime.

`install.py` prints the resolved shell tool after installing, so you always see which one you ended up with.

## Linux and macOS notes

- The installer is stdlib-only Python 3.9+ and has no Windows-specific code: paths are handled with `pathlib`, and output always uses `/` separators.
- The `bash` tool is what `background-shell.ts` attaches to on these platforms, so Ctrl+B and `/background` work there too.
- `--apply-patches` needs `node` on `PATH` (pi itself is an npm package, so you will have it). It patches `<agent-dir>/npm/node_modules/@marshal/pi-turn-stats/extensions/turn-stats.ts` — the file only exists after pi has installed its packages, so run it once more after the first start if it reports "not present yet".
- `models.json` providers are plain HTTP endpoints (`127.0.0.1:18731` for command-code, `localhost:8080` for llama.cpp); the local ones need those servers running on the same host.

## Not installed (and why)

| Left out | Reason |
| --- | --- |
| `auth.json` | Credentials. Never share it; `install.py` will not create, copy or overwrite it. |
| `models.json` API keys | Replaced with `$COMMANDCODE_API_KEY` / `$EXPLABS_API_KEY` placeholders — set the env vars, or put the key in `auth.json`. |
| `models-store.json`, `trust.json` | Machine-local state (cached model metadata, project trust decisions) |
| `sessions/`, `npm/`, `git/`, `bin/` | Session history and pi-managed installs; pi recreates the latter three |
| `extensions/herdr-agent-state.ts` | Generated and overwritten by `pi-herdsman` |
| `skills/*` | On this machine they are junctions into `~/.agents/skills`, i.e. content owned elsewhere |
| the `orca-*` extensions | Removed from this config on purpose |

## Customising

Edit the files under `agent/` in this repo, then re-run `python install.py` — it diffs by content, so unchanged files are skipped and changed ones are backed up.
