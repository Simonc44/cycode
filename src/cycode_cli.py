"""
CyCode CLI — main entry point that wires together startup screen + REPL.
Equivalent to the `claude` binary in Claude Code.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cycode",
        description="CyCode — AI-powered coding assistant powered by CygnisAI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cycode                         Start interactive REPL
  cycode "explain this code"     One-shot prompt, then exit
  cycode --model alpha2          Force model selection
  cycode --file main.py          Inject file into first prompt
  cycode --no-stream             Disable streaming output
  cycode startup                 Show startup banner only
  cycode --version               Show version and exit

Environment:
  CYGNISAI_API_KEY               API key (alternative to --api-key)
""",
    )

    p.add_argument("prompt", nargs="?", default=None,
                   help="One-shot prompt (omit for interactive REPL)")
    p.add_argument("--api-key", "-k", default=None,
                   help="CygnisAI API key (overrides CYGNISAI_API_KEY env var)")
    p.add_argument("--model", "-m", default=None,
                   help="Model to use: alpha1 | alpha2 | auto (default: alpha2)")
    p.add_argument("--file", "-f", default=None,
                   help="Inject file contents into initial context")
    p.add_argument("--no-stream", action="store_true",
                   help="Disable token streaming")
    p.add_argument("--no-probe", action="store_true",
                   help="Skip CygnisAI API health probe at startup")
    p.add_argument("--no-banner", action="store_true",
                   help="Skip startup banner")
    p.add_argument("--version", "-v", action="store_true",
                   help="Show version and exit")
    p.add_argument("--print", "-p", dest="print_only", action="store_true",
                   help="One-shot: print response and exit (no REPL)")

    # Sub-commands
    subs = p.add_subparsers(dest="subcommand")
    subs.add_parser("startup", help="Show startup banner")
    subs.add_parser("version", help="Show version")

    cfg_p = subs.add_parser("config", help="View or edit persistent configuration")
    cfg_p.add_argument("key", nargs="?", default=None)
    cfg_p.add_argument("value", nargs="?", default=None)

    return p


def main(argv: Optional[list] = None) -> int:
    from .cycode_repl import Config as CyCodeConfig, REPL as CyCodeREPL, VERSION as CYCODE_VERSION

    parser = build_parser()
    args = parser.parse_args(argv)

    # ── --version ─────────────────────────────────────────────────────────────
    if args.version or getattr(args, "subcommand", None) == "version":
        print(f"CyCode v{CYCODE_VERSION}  ·  CygnisAI Enterprise Gateway")
        return 0

    # ── load config ───────────────────────────────────────────────────────────
    config = CyCodeConfig.load()
    if args.api_key:
        config.api_key = args.api_key
    if args.model:
        config.default_model = args.model
    if args.no_stream:
        config.stream = False

    # ── startup subcommand ────────────────────────────────────────────────────
    if getattr(args, "subcommand", None) == "startup":
        from .startup_screen import show_startup
        show_startup(api_key=config.api_key, probe=not args.no_probe)
        return 0

    # ── config subcommand ─────────────────────────────────────────────────────
    if getattr(args, "subcommand", None) == "config":
        import json
        key = getattr(args, "key", None)
        value = getattr(args, "value", None)
        if not key:
            cfg = {k: ("***" if k == "api_key" and v else v)
                   for k, v in config.__dict__.items()}
            print(json.dumps(cfg, indent=2))
        elif value is None:
            print(f"{key} = {getattr(config, key, '(not found)')}")
        else:
            if not hasattr(config, key):
                print(f"Unknown key: {key}", file=sys.stderr)
                return 1
            current = getattr(config, key)
            if isinstance(current, bool):
                new_val = value.lower() in ("1", "true", "yes")
            elif isinstance(current, int):
                new_val = int(value)
            else:
                new_val = value
            setattr(config, key, new_val)
            config.save()
            print(f"Set {key} = {new_val}")
        return 0

    # ── Interactive REPL ──────────────────────────────────────────────────────
    # We remove the banner call from here because REPL will handle it once
    repl = CyCodeREPL(config, show_banner=not args.no_banner)

    if args.file:
        from .cycode_repl import Tools
        content = Tools.read(args.file)
        repl.session.add("user", f"[File: {args.file}]\n```\n{content}\n```")
        repl.renderer.ok(f"Injected {args.file} into context")

    if args.prompt or args.print_only:
        prompt = args.prompt or ""
        if prompt:
            repl._msg(prompt)
        return 0

    repl.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
