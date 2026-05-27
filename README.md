# CYGNIS CODE: The Professional AI Coding Harness

<p align="center">
  <strong>⭐ Pioneering the next generation of autonomous development with CYGNIS CODE ⭐</strong>
</p>

<p align="center">
  <a href="https://star-history.com/#ultraworkers/cygnis-code&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ultraworkers/claw-code&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=ultraworkers/claw-code&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=ultraworkers/claw-code&type=Date" width="600" />
    </picture>
  </a>
</p>

<p align="center">
  <img src="assets/clawd-hero.jpeg" alt="Cygnis" width="300" />
</p>

<p align="center">
  <strong>Developed and maintained by the Cygnis Autonomous Collective</strong>
</p>

<p align="center">
  <a href="https://github.com/Yeachan-Heo/clawhip">clawhip</a> ·
  <a href="https://github.com/code-yeongyu/oh-my-openagent">oh-my-openagent</a> ·
  <a href="https://github.com/Yeachan-Heo/oh-my-claudecode">oh-my-claudecode</a> ·
  <a href="https://github.com/Yeachan-Heo/oh-my-codex">oh-my-codex</a> ·
  <a href="https://discord.gg/6ztZB9jvWq">UltraWorkers Discord</a>
</p>

> [!IMPORTANT]
> The active Rust workspace now lives in [`rust/`](./rust). Start with [`USAGE.md`](./USAGE.md) for build, auth, CLI, session, and parity-harness workflows, then use [`rust/README.md`](./rust/README.md) for crate-level details.

---

## Vision

CYGNIS CODE is a high-performance, autonomous coding harness designed for professional software engineering. Built on the principles of reliability, speed, and precision, CYGNIS CODE enables developers to leverage advanced AI capabilities within their existing workflows.

This repository exists to prove that an open coding harness can be built **autonomously, in public, and at high velocity** — with humans setting direction and autonomous agents executing the implementation.

## Porting Status

The main source tree is now Python-first.

- `src/` contains the active Python porting workspace
- `tests/` verifies the current Python workspace
- the exposed snapshot is no longer part of the tracked repository state

The current Python workspace is not yet a complete one-to-one replacement for the original system, but the primary implementation surface is now Python.

## Repository Layout

```text
.
├── src/                                # Python porting workspace
│   ├── __init__.py
│   ├── commands.py
│   ├── main.py
│   ├── models.py
│   ├── port_manifest.py
│   ├── query_engine.py
│   ├── task.py
│   └── tools.py
├── tests/                              # Python verification
├── assets/omx/                         # OmX workflow screenshots
├── 2026-03-09-is-legal-the-same-as-legitimate-ai-reimplementation-and-the-erosion-of-copyleft.md
└── README.md
```

## Quickstart

Render the CYGNIS CODE porting summary:

```bash
python3 -m src.main summary
```

Print the current workspace manifest:

```bash
python3 -m src.main manifest
```

Run verification:

```bash
python3 -m unittest discover -s tests -v
```

## Community

<p align="center">
  <a href="https://discord.gg/6ztZB9jvWq"><img src="https://img.shields.io/badge/UltraWorkers-Discord-5865F2?logo=discord&style=for-the-badge" alt="UltraWorkers Discord" /></a>
</p>

Join the [**UltraWorkers Discord**](https://discord.gg/6ztZB9jvWq) — the community around CYGNIS CODE and the UltraWorkers ecosystem. Come chat about LLMs, harness engineering, agent workflows, and autonomous software development.

---

## Ownership / Affiliation Disclaimer

- This repository does **not** claim ownership of the original Claude Code source material.
- This repository is **not affiliated with, endorsed by, or maintained by Anthropic**.
- CYGNIS CODE is an independent reimplementation.
