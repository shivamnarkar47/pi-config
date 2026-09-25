# pi-config

My personal [pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent) configuration: the agent-directory files, my own extension, the plugin/package list, and a one-command installer.

Windows-first, PowerShell-first. No secrets — the API key in `models.json` is a `$COMMANDCODE_API_KEY` placeholder.

## Install

Any Python 3.9+ works:

```sh
git clone https://github.com/shivamnarkar47/pi-config.git
cd pi-config
python install.py
```

No system Python? [`uv`](https://docs.astral.sh/uv/) works too: `uv run install.py`.

```
python install.py                       # install into ~/.pi/agent
python install.py --agent-dir /tmp/pi   # install somewhere else (handy for testing)
python install.py --dry-run             # show what would change, write nothing
python install.py --list                # list what this config ships
python install.py --force               # overwrite without keeping a backup
python install.py --apply-patches       # also re-apply the npm package patches (needs node)
```

Then start pi, or run `/reload` in a session that is already open. Existing files are backed up as `<name>.bak-<timestamp>` unless you pass `--force`.

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

## PowerShell is the default shell

`settings.json` sets `defaultTools: ["read", "powershell", "edit", "write"]`, which is what pi's own [Windows guide](https://www.npmjs.com/package/@earendil-works/pi-coding-agent) recommends. The `bash` tool is deliberately **not** enabled: on Windows without Git for Windows, pi resolves it to the WSL stub `C:\Windows\System32\bash.exe`, so commands end up running in WSL instead of PowerShell.

Two things to know:

- `defaultTools` is a *startup* set. `pi -t read,grep,find,ls --print "…"` overrides it for one run, and an extension can call `setActiveTools()` at runtime.
- On Linux/macOS, swap `powershell` for `bash` in `defaultTools` (the `powershell` tool only exists on Windows) and re-run the installer.

`install.py` prints the resolved shell tool after installing, so you always see which one you ended up with.

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
