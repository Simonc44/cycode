"""CyCode v2.1 — Startup screen"""
from __future__ import annotations
import json, os, sys, threading, time
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.rule import Rule
    from rich.prompt import Prompt
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

CYCODE_VERSION    = "2.1.0"
CYGNISAI_BASE_URL = "https://needlessly-faithful-gopher.ngrok-free.app/v3"
CONFIG_FILE       = Path.home() / ".cycode_config.json"
TRUST_FILE        = Path.home() / ".cycode_trusted_workspaces.json"

# Logo CYCODE — ASCII Art Block Style
CYCODE_LOGO = [
    r" ██████╗██╗   ██╗ ██████╗ ██████╗ ██████╗ ███████╗",
    r"██╔════╝╚██╗ ██╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝",
    r"██║      ╚████╔╝ ██║     ██║   ██║██║  ██║█████╗  ",
    r"██║       ╚██╔╝  ██║     ██║   ██║██║  ██║██╔══╝  ",
    r"╚██████╗   ██║   ╚██████╗╚██████╔╝██████╔╝███████╗",
    r" ╚═════╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
]

TIPS = [
    ("/init",          "Scan project and create project context"),
    ("/models",        "List all available CygnisAI inference models"),
    ("/file <path>",   "Read a file and inject into context"),
    ("/exec <cmd>",    "Run a shell command locally"),
    ("/image <txt>",   "Generate an image via CyVision SDXL"),
    ("/sandbox",       "Execute Python/Bash via CygnisAI sandbox"),
    ("/plugins",       "Manage Google, GitHub and other plugins"),
    ("/help",          "Full command reference"),
]
WHATSNEW = [
    ("CygnisAI v3 API",     "Live MoE routing — alpha1 · alpha2 · auto"),
    ("CyVision",            "SDXL-Turbo image generation"),
    ("Neural Memory (RAG)", "Persistent ChromaDB vector context"),
    ("Plugins",             "Google Search, GitHub, and more"),
    ("Ctrl+T",              "Inspect CygnisAI thinking in real time"),
]

class CygnisStatus:
    def __init__(self, api_key: str = ""):
        self.api_key     = api_key or os.environ.get("CYGNISAI_API_KEY", "")
        self.connected   = False
        self.model_fleet: list[dict] = []
    def probe(self) -> None:
        if not HAS_REQUESTS: return
        h = {"Content-Type": "application/json"}
        if self.api_key: h["Authorization"] = f"Bearer {self.api_key}"
        try:
            r = requests.get(f"{CYGNISAI_BASE_URL}/health", headers=h, timeout=3)
            self.connected = r.status_code < 500
        except: self.connected = False
        try:
            r = requests.get(f"{CYGNISAI_BASE_URL}/models", headers=h, timeout=3)
            if r.ok:
                d = r.json()
                self.model_fleet = d if isinstance(d, list) else d.get("models", [])
        except: pass

def _load_cfg() -> dict:
    if CONFIG_FILE.exists():
        try: return json.loads(CONFIG_FILE.read_text())
        except: pass
    return {}

def _save_cfg(key: str, value) -> None:
    cfg = _load_cfg(); cfg[key] = value
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

def is_trusted(cwd: Optional[str] = None) -> bool:
    cwd = cwd or str(Path.cwd())
    if TRUST_FILE.exists():
        try: return cwd in set(json.loads(TRUST_FILE.read_text()))
        except: pass
    return False

def trust_workspace(cwd: Optional[str] = None) -> None:
    cwd = cwd or str(Path.cwd())
    paths: set = set()
    if TRUST_FILE.exists():
        try: paths = set(json.loads(TRUST_FILE.read_text()))
        except: pass
    paths.add(cwd)
    TRUST_FILE.write_text(json.dumps(list(paths)))

def show_trust_page(console: Console) -> bool:
    cwd = str(Path.cwd())
    inner = Table.grid(expand=True); inner.add_column()
    inner.add_row(Text(""))
    inner.add_row(Text("Accessing workspace:", style="bold white"))
    inner.add_row(Text(f"  {cwd}", style="cyan"))
    inner.add_row(Text(""))
    inner.add_row(Rule(style="bright_black"))
    inner.add_row(Text(""))
    inner.add_row(Text(
        "Quick safety check: Is this a project you created or one you trust?\n"
        "CyCode will be able to read, edit, and execute files here.",
        style="dim"
    ))
    inner.add_row(Text(""))
    ch = Table.grid(padding=(0, 2)); ch.add_column(style="bold cyan", no_wrap=True); ch.add_column(style="dim")
    ch.add_row("❯ 1.", "Yes, I trust this folder")
    ch.add_row("  2.", "No, exit")
    inner.add_row(ch)
    console.print(Panel(inner, box=box.ROUNDED, border_style="bright_black", padding=(0, 2)))
    try:
        ans = Prompt.ask("  Choice", choices=["1","2",""], default="1", console=console, show_choices=False)
    except (EOFError, KeyboardInterrupt): return False
    if ans == "2": return False
    trust_workspace(cwd)
    return True

def show_auth_page(console: Console) -> Optional[str]:
    inner = Table.grid(expand=True); inner.add_column()
    inner.add_row(Text("CygnisAI Authentication", style="bold white"))
    inner.add_row(Rule(style="bright_black"))
    inner.add_row(Text("Option 1: Enter key below (saved to ~/.cycode_config.json)"))
    inner.add_row(Text("Option 2: Set CYGNISAI_API_KEY environment variable"))
    inner.add_row(Text(""))
    console.print(Panel(inner, box=box.ROUNDED, border_style="cyan", title="[bold] Login [/bold]"))
    try:
        key = Prompt.ask("  API Key", default="", password=True, console=console)
    except (EOFError, KeyboardInterrupt): return None
    if key.strip():
        _save_cfg("api_key", key.strip())
        return key.strip()
    return None

def _short_path(p: str) -> str:
    home = str(Path.home())
    return p.replace(home, "~")

def render_banner(status: CygnisStatus, api_key: str = "", model: str = "alpha2", 
                  session_id: str = "", console: Optional[Console] = None) -> None:
    c = console or Console()
    auth_ok  = bool(api_key)
    conn_col = "green" if status.connected else "red"
    conn_lbl = "CONNECTED" if status.connected else "OFFLINE"
    model_lbl = (status.model_fleet[0].get("id", model) if status.model_fleet else model)
    full_cwd = str(Path.cwd())
    cwd_display = _short_path(full_cwd)

    # --- TOP LEFT: Welcome + Logo ---
    top_left = Table.grid(); top_left.add_column()
    top_left.add_row(Text("Welcome back!", style="bold white"))
    top_left.add_row(Text(""))
    for line in CYCODE_LOGO:
        top_left.add_row(Text(line, style="bold cyan", no_wrap=True))
    top_left.add_row(Text(""))

    # --- TOP RIGHT: Tips ---
    tips_t = Table.grid(padding=(0, 2))
    tips_t.add_column(style="bold cyan", no_wrap=True)
    tips_t.add_column(style="dim")
    for cmd, desc in TIPS: tips_t.add_row(cmd, desc)
    
    top_right = Table.grid(); top_right.add_column()
    top_right.add_row(Text("Tips for getting started", style="bold white"))
    top_right.add_row(Rule(style="bright_black"))
    top_right.add_row(tips_t)

    # --- BOTTOM LEFT: Authentication & Status ---
    bottom_left = Table.grid(); bottom_left.add_column()
    
    # Titre d'auth (plus de fixed width ici)
    auth_title = Text("MESSAGE AUTHENTIFIÉ", style="bold green" if auth_ok else "bold yellow")
    bottom_left.add_row(auth_title)
    bottom_left.add_row(Text(""))
    
    # Grille de détails avec icônes
    details = Table.grid(padding=(0, 1)); details.add_column(width=3); details.add_column()
    if auth_ok:
        details.add_row(Text("✔", style="green"), Text(f"Session active: {api_key}", style="green", no_wrap=True))
        details.add_row(Text("●", style=conn_col), Text(f"{conn_lbl} ({model_lbl})", style=conn_col))
    else:
        details.add_row(Text("⚠", style="yellow"), Text("Mode restreint (clé manquante)", style="yellow"))
    
    details.add_row(Text("~", style="bright_black"), Text(cwd_display, style="bright_black"))
    
    bottom_left.add_row(details)

    # --- BOTTOM RIGHT: What's New ---
    news_t = Table.grid(padding=(0, 2))
    news_t.add_column(style="bold cyan", no_wrap=True)
    news_t.add_column(style="dim")
    for title, desc in WHATSNEW: news_t.add_row(title, desc)
    
    bottom_right = Table.grid(); bottom_right.add_column()
    bottom_right.add_row(Text("What's new", style="bold white"))
    bottom_right.add_row(Rule(style="bright_black"))
    bottom_right.add_row(news_t)

    # Main Layout Grid
    layout = Table.grid(expand=True, padding=(1, 4))
    layout.add_column(ratio=1)
    layout.add_column(ratio=1)
    layout.add_row(top_left, top_right)
    layout.add_row(Rule(style="bright_black"), Rule(style="bright_black"))
    layout.add_row(bottom_left, bottom_right)

    c.print(Panel(layout, box=box.ROUNDED, border_style="bright_black", padding=(1, 2)))

def show_startup(api_key: Optional[str] = None, probe: bool = True,
                 check_trust: bool = True, check_auth: bool = True,
                 model: str = "alpha2", console: Optional[Console] = None) -> dict:
    c = console or Console()
    cfg = _load_cfg()
    effective_key = api_key or os.environ.get("CYGNISAI_API_KEY", "") or cfg.get("api_key", "")
    
    if check_trust and not is_trusted():
        if not show_trust_page(c): sys.exit(0)
        c.clear()

    if check_auth and not effective_key:
        entered = show_auth_page(c)
        if entered: effective_key = entered
        c.clear()

    status = CygnisStatus(api_key=effective_key)
    if probe:
        t = threading.Thread(target=status.probe, daemon=True)
        t.start(); t.join(timeout=2.0)

    render_banner(status, api_key=effective_key, model=model, console=c)
    return {"api_key": effective_key}

if __name__ == "__main__":
    show_startup()
