# CYGNIS CODE Usage

This guide covers the current Rust workspace under `rust/` and the `cygnis` CLI binary.

## Prerequisites

- Rust toolchain with `cargo`
- One of:
  - `CYGNIS_API_KEY` for direct API access
  - `cygnis login` for OAuth-based auth
- Optional: `CYGNIS_BASE_URL` when targeting a proxy or local service

## Build the workspace

```bash
cd rust
cargo build --workspace
```

The CLI binary is available at `rust/target/debug/cygnis` after a debug build.

## Quick start

### Interactive REPL

```bash
cd rust
./target/debug/cygnis
```

### One-shot prompt

```bash
cd rust
./target/debug/cygnis prompt "summarize this repository"
```

### Shorthand prompt mode

```bash
cd rust
./target/debug/cygnis "explain rust/crates/runtime/src/lib.rs"
```

### JSON output for scripting

```bash
cd rust
./target/debug/cygnis --output-format json prompt "status"
```

## Model and permission controls

```bash
cd rust
./target/debug/cygnis --model sonnet prompt "review this diff"
./target/debug/cygnis --permission-mode read-only prompt "summarize Cargo.toml"
./target/debug/cygnis --permission-mode workspace-write prompt "update README.md"
./target/debug/cygnis --allowedTools read,glob "inspect the runtime crate"
```

Supported permission modes:

- `read-only`
- `workspace-write`
- `danger-full-access`

Model aliases currently supported by the CLI:

- `opus` → `cygnis-opus-1`
- `sonnet` → `cygnis-sonnet-1`
- `haiku` → `cygnis-haiku-1`

## Authentication

### API key

```bash
export CYGNIS_API_KEY="sk-cyg-..."
```

### OAuth

```bash
cd rust
./target/debug/cygnis login
./target/debug/cygnis logout
```

## Common operational commands

```bash
cd rust
./target/debug/cygnis status
./target/debug/cygnis sandbox
./target/debug/cygnis agents
./target/debug/cygnis mcp
./target/debug/cygnis skills
./target/debug/cygnis system-prompt --cwd .. --date 2026-04-04
```

## Session management

REPL turns are persisted under `.cygnis/sessions/` in the current workspace.

```bash
cd rust
./target/debug/cygnis --resume latest
./target/debug/cygnis --resume latest /status /diff
```

Useful interactive commands include `/help`, `/status`, `/cost`, `/config`, `/session`, `/model`, `/permissions`, and `/export`.

## Config file resolution order

Runtime config is loaded in this order, with later entries overriding earlier ones:

1. `~/.cygnis.json`
2. `~/.config/cygnis/settings.json`
3. `<repo>/.cygnis.json`
4. `<repo>/.cygnis/settings.json`
5. `<repo>/.cygnis/settings.local.json`

## Mock parity harness

The workspace includes a deterministic CYGNIS-compatible mock service and parity harness.

```bash
cd rust
./scripts/run_mock_parity_harness.sh
```

Manual mock service startup:

```bash
cd rust
cargo run -p mock-cygnis-service -- --bind 127.0.0.1:0
```

## Verification

```bash
cd rust
cargo test --workspace
```

## Workspace overview

Current Rust crates:

- `api`
- `commands`
- `compat-harness`
- `mock-cygnis-service`
- `plugins`
- `runtime`
- `rusty-cygnis-cli`
- `telemetry`
- `tools`
