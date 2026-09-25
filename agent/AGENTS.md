# Agent instructions

## Backgrounded shell commands

The `powershell` and `bash` tools can report `Command moved to background (job #N)`. The
process is still running, and pi delivers its exit code, duration and output as a message
when it exits. Pressing Ctrl+B is what triggers this.

- Never re-run a backgrounded command to check on it, and never wait for it: no `sleep`,
  `Start-Sleep`, `Wait-Sleep`, `timeout`, or any poll/re-check loop. Pi refuses such
  commands outright while a backgrounded command is still running.
- If you have other work, do it. If you have nothing else to do, end your turn immediately -
  the result arrives on its own and the next turn continues from there.
