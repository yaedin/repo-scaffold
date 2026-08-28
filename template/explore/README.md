# explore/

This is the fast, disposable side of the repository. Use it to inspect examples,
try small canaries, and decide what deserves a proper experiment. Notebook files,
scratch data, and raw exploration output are gitignored; `FINDINGS.md` is
committed so useful observations survive.

## The boundary

**Nothing under `explore/` may be cited by `CLAIMS.md`.** `just check` enforces
the boundary. Promote anything you want to defend into a committed experiment:

```text
notebook  ->  FINDINGS.md  ->  experiments/eNN_slug/  ->  CLAIMS.md
(noticed)     (worth a look)   (run.py + analyze.py)     (defended)
```

This is a lifecycle boundary, not a claim that every notebook must be messy or
that every exploration needs a model-specific experimental protocol.

## Install and start

From the repository root:

```bash
uv sync --group explore --locked
uv run just explore
```

Open <http://127.0.0.1:8888/lab>. Keep the process running while you work. The
recipe deliberately binds Jupyter to loopback and disables authentication for
local agent access. Do not change the IP to `0.0.0.0` or expose port 8888 on a
network without restoring authentication.

The project-local `.codex/config.toml` points Codex at the Jupyter MCP endpoint.
After opening this repository as the Codex project, restart or reopen the project
once so that configuration is loaded. Jupyter is still a separate process: MCP
lets the agent work with a running server and kernel; it does not start or host
either one.

With that connection, an agent can create and edit notebooks, run cells, inspect
their outputs, and help iterate on live kernel state. It can also work from plain
Python scripts when that is the clearer artifact.

## Shut down cleanly

In the terminal running Jupyter, press Ctrl-C once. Jupyter then asks:

```text
Shut down this Jupyter server (y/[n])?
```

Type `y` and press Enter. Ctrl-C alone does not answer that prompt, which can
make the server appear stuck. The shutdown log should say that its extensions
and kernels were stopped.

From another terminal, the deterministic alternative is:

```bash
uv run jupyter server stop 8888
```

Use `uv run jupyter server list` to see whether a registered server remains. A
browser connection error usually means the server process ended; it does not by
itself imply that a notebook file is damaged. Restarting the server creates new
kernels, so in-memory variables are not preserved. When reusing port 8888 for a
different repository, close or reload old Jupyter tabs so they do not reconnect
and request notebook IDs that do not exist in the new project.

## Choose the arrangement that fits the work

### Local notebook, remote jobs

Keep Jupyter on your machine and let notebook cells launch or inspect serverless
jobs such as Modal functions. This fits short or batched inference where model
weights can be cached and the accelerator should scale down while you think. Put
the provider client in the project and write durable job results to files that
the notebook can reload.

### Remote kernel beside the accelerator

Run Jupyter on the GPU machine when exploration repeatedly needs a live model,
activations, hooks, or other in-memory state. Keep it bound to `127.0.0.1` there
and forward the port, for example:

```bash
ssh -L 8888:127.0.0.1:8888 your-gpu-host
```

A persistent GPU kernel improves iteration speed but bills while it waits. Save
expensive intermediate artifacts to durable storage; a container or kernel can
still disappear.

## When the exploration stops being disposable

Once a run is costly, long-running, or intended to support a claim, move it to a
restartable script and the repository's normal experiment workflow. The durable
provenance, checkpointing, output, and review rules are already documented in
`AGENTS.md`; they are not repeated here. Keep the notebook as the interface for
inspection if that remains useful.
