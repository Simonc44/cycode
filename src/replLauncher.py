"""
CyCode replLauncher — startup screen + REPL launcher bridge.
"""
from __future__ import annotations

import os
from typing import Optional


def build_repl_banner() -> str:
    """Legacy text-only banner (kept for backwards compat)."""
    return (
        "CyCode v2.0  ·  CygnisAI Enterprise Gateway\n"
        "Run /init to configure your workspace.\n"
        "Use 'python3 -m src.main repl' for interactive mode, "
        "or 'python3 -m src.main chat <prompt>' for one-shot."
    )


def launch_startup_screen(api_key: Optional[str] = None, probe: bool = True) -> None:
    """Display the rich CyCode startup screen."""
    try:
        from .startup_screen import show_startup
        show_startup(api_key=api_key, probe=probe)
    except Exception as exc:
        print(build_repl_banner())
        print(f"[startup_screen unavailable: {exc}]")


def launch_repl(api_key: Optional[str] = None, model: Optional[str] = None,
                stream: bool = True, show_banner: bool = True) -> None:
    """Launch the interactive CyCode REPL."""
    try:
        from .cycode_repl import CyCodeConfig, CyCodeREPL
        config = CyCodeConfig.load()
        if api_key:
            config.api_key = api_key
        if model:
            config.default_model = model
        config.stream = stream
        if show_banner:
            launch_startup_screen(api_key=config.api_key)
        repl = CyCodeREPL(config)
        repl.run()
    except Exception as exc:
        print(f"REPL error: {exc}")
        raise
