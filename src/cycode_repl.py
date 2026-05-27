"""
CyCode v2.3 REPL — Équivalent Claude Code
Fonctionnalités :
  • L'IA lit les fichiers dont elle a besoin (affichage live de la lecture)
  • Modifications de fichiers avec diff + Accepter/Refuser interactif
  • Contexte projet injecté automatiquement (scan profond)
  • Thinking animé : Thinking / Constructing / Analyzing / Sending
  • Balises [RÉFLEXION] filtrées silencieusement, jamais affichées
  • Notification discrète sous la réponse si l'IA a réfléchi
  • Ctrl+T / /thinking : panneau jaune de raisonnement instantané
  • Alerte automatique si le contexte dépasse la limite du modèle
  • Plugins : Google Search, GitHub
  • Skills : code_review, refactor, tests, docs, commit
"""
from __future__ import annotations

import difflib, json, os, re, subprocess, sys, threading, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional
from uuid import uuid4

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.syntax import Syntax
    from rich.rule import Rule
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.columns import Columns
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

try:
    from prompt_toolkit import PromptSession, prompt as pt_prompt
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style as PtStyle
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    HAS_PT = True
except ImportError:
    HAS_PT = False


# ─── Constants ────────────────────────────────────────────────────────────────

VERSION       = "2.3.0"

# Limites de contexte par modèle (en tokens estimés ~4 chars/token)
CTX_LIMITS = {
    "alpha1": 4_000,
    "alpha2": 8_000,
    "auto":   8_000,
}
CTX_WARN_RATIO = 0.80  # alerte à 80% de la limite
BASE_URL      = "https://needlessly-faithful-gopher.ngrok-free.app/v3"
HISTORY_FILE  = Path.home() / ".cycode_history"
SESSION_DIR   = Path.home() / ".cycode_sessions"
CONFIG_FILE   = Path.home() / ".cycode_config.json"
PLUGINS_FILE  = Path.home() / ".cycode_plugins.json"
DEFAULT_MODEL = "alpha2"

THINKING_STATES = [
    ("dots",  "Thinking…"),
    ("dots2", "Constructing…"),
    ("dots3", "Analyzing…"),
    ("line",  "Sending…"),
    ("dots",  "Processing…"),
]

_THINKING_RE = re.compile(
    r"\[RÉFLEXION\].*?\[/RÉFLEXION\]|\[THINKING\].*?\[/THINKING\]"
    r"|\[REFLECTION\].*?\[/REFLECTION\]|<thinking>.*?</thinking>"
    r"|<reflection>.*?</reflection>",
    re.DOTALL | re.IGNORECASE,
)
_ANSWER_TAGS = re.compile(r"\[/?RÉPONSE\]|\[/?RESPONSE\]|\[/?ANSWER\]", re.IGNORECASE)
_THINKING_CAPTURE = re.compile(
    r"\[RÉFLEXION\](.*?)\[/RÉFLEXION\]|\[THINKING\](.*?)\[/THINKING\]"
    r"|<thinking>(.*?)</thinking>",
    re.DOTALL | re.IGNORECASE,
)

# Détecte les blocs de modification que l'IA veut appliquer
# Format: <<<EDIT:path/to/file>>> ... code ... <<<END>>>
_EDIT_BLOCK_RE = re.compile(
    r"<<<EDIT:([^>]+)>>>\n?(.*?)<<<END>>>",
    re.DOTALL,
)
# Détecte aussi le format markdown avec indication de fichier
_FILE_BLOCK_RE = re.compile(
    r"(?:^|\n)(?:###?\s+(?:Fichier|File|Modif[^\n]*)|`([^`\n]+\.[a-z]{1,6})`\s*:?\s*\n)```(\w*)\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

def clean_output(text: str) -> tuple[str, str]:
    thinking = ""
    m = _THINKING_CAPTURE.search(text)
    if m:
        thinking = next((g for g in m.groups() if g), "").strip()
    clean = _THINKING_RE.sub("", text)
    clean = _ANSWER_TAGS.sub("", clean)
    return clean.strip(), thinking


# ─── Config ───────────────────────────────────────────────────────────────────

@dataclass
class Config:
    api_key: str = ""
    default_model: str = DEFAULT_MODEL
    max_tokens: int = 2048
    use_memory: bool = True
    stream: bool = True
    theme: str = "monokai"
    workspace: str = ""
    auto_read_workspace: bool = True

    def __post_init__(self):
        if not self.workspace:
            self.workspace = str(Path.cwd())

    def save(self) -> None:
        CONFIG_FILE.write_text(json.dumps(self.__dict__, indent=2))

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if CONFIG_FILE.exists():
            try:
                for k, v in json.loads(CONFIG_FILE.read_text()).items():
                    if hasattr(cfg, k): setattr(cfg, k, v)
            except: pass
        if k := os.environ.get("CYGNISAI_API_KEY", ""):
            cfg.api_key = k
        cfg.workspace = str(Path.cwd())
        return cfg


# ─── Plugins ──────────────────────────────────────────────────────────────────

BUILTIN_PLUGINS = {
    "google_search": {
        "name": "Google Search", "icon": "🔍",
        "description": "Search the web via Google Custom Search API",
        "requires": ["GOOGLE_API_KEY", "GOOGLE_CSE_ID"],
    },
    "github": {
        "name": "GitHub", "icon": "🐙",
        "description": "Read repos, issues, PRs via GitHub API",
        "requires": ["GITHUB_TOKEN"],
    },
    "filesystem": {
        "name": "Filesystem", "icon": "📁",
        "description": "Read/write files in workspace (built-in)",
        "requires": [],
    },
    "web_fetch": {
        "name": "Web Fetch", "icon": "🌐",
        "description": "Fetch and summarize any URL",
        "requires": [],
    },
}

BUILTIN_SKILLS = {
    "code_review": {"name": "Code Review",      "prompt_prefix": "Perform a thorough code review. Check for bugs, security issues, performance, and style:\n"},
    "explain":     {"name": "Explain Code",     "prompt_prefix": "Explain the following code clearly, step by step:\n"},
    "refactor":    {"name": "Refactor",         "prompt_prefix": "Refactor for clarity, performance, and best practices. Show the improved version:\n"},
    "tests":       {"name": "Generate Tests",   "prompt_prefix": "Generate comprehensive unit tests:\n"},
    "docs":        {"name": "Generate Docs",    "prompt_prefix": "Generate clear documentation:\n"},
    "commit":      {"name": "Commit Message",   "prompt_prefix": "Generate a conventional commit message (feat/fix/chore/refactor/docs):\n"},
}

class PluginManager:
    def __init__(self):
        self._active: dict = {}
        self._load()

    def _load(self):
        if PLUGINS_FILE.exists():
            try: self._active = json.loads(PLUGINS_FILE.read_text())
            except: self._active = {}

    def _save(self):
        PLUGINS_FILE.write_text(json.dumps(self._active, indent=2))

    def enable(self, pid: str) -> bool:
        p = BUILTIN_PLUGINS.get(pid)
        if not p: return False
        missing = [k for k in p["requires"] if not os.environ.get(k)]
        if missing: return False
        self._active[pid] = {}; self._save(); return True

    def disable(self, pid: str):
        self._active.pop(pid, None); self._save()

    def is_active(self, pid: str) -> bool:
        return pid in self._active

    def active_context(self) -> str:
        if not self._active: return ""
        return "Available plugins:\n" + "\n".join(
            f"- {BUILTIN_PLUGINS[p]['name']}: {BUILTIN_PLUGINS[p]['description']}"
            for p in self._active if p in BUILTIN_PLUGINS
        )

    def run_google_search(self, query: str) -> str:
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        cse_id  = os.environ.get("GOOGLE_CSE_ID", "")
        if not api_key or not cse_id:
            return "Google Search not configured. Set GOOGLE_API_KEY and GOOGLE_CSE_ID."
        try:
            r = requests.get("https://www.googleapis.com/customsearch/v1",
                             params={"key": api_key, "cx": cse_id, "q": query, "num": 5}, timeout=10)
            items = r.json().get("items", [])
            return "\n\n".join(f"**{i['title']}**\n{i['link']}\n{i.get('snippet','')}" for i in items) or "No results."
        except Exception as e: return f"Search error: {e}"

    def run_github(self, query: str) -> str:
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {"Accept": "application/vnd.github+json"}
        if token: headers["Authorization"] = f"Bearer {token}"
        try:
            if "/" in query and not query.startswith("search "):
                owner, repo = query.strip().split("/", 1)
                r = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=10)
                d = r.json()
                return (f"**{d.get('full_name')}** — {d.get('description','')}\n"
                        f"⭐ {d.get('stargazers_count',0)}  🍴 {d.get('forks_count',0)}\n"
                        f"Language: {d.get('language','')}  Issues: {d.get('open_issues_count',0)}\n"
                        f"{d.get('html_url','')}")
            else:
                r = requests.get("https://api.github.com/search/repositories",
                                 params={"q": query.replace("search ",""), "sort":"stars","per_page":5},
                                 headers=headers, timeout=10)
                return "\n".join(f"**{i['full_name']}** ⭐{i['stargazers_count']} — {i.get('description','')}"
                                 for i in r.json().get("items",[])) or "No repos found."
        except Exception as e: return f"GitHub error: {e}"


# ─── API Client ───────────────────────────────────────────────────────────────

class CygnisClient:
    def __init__(self, config: Config):
        self.config = config

    def _h(self):
        h = {"Content-Type": "application/json"}
        if self.config.api_key: h["Authorization"] = f"Bearer {self.config.api_key}"
        return h

    def _url(self, path: str):
        return f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"

    def health(self) -> dict:
        try:
            r = requests.get(self._url("/health"), headers=self._h(), timeout=4)
            return r.json() if r.ok else {"status": "error"}
        except Exception as e: return {"status": "unreachable", "error": str(e)}

    def models(self) -> list:
        try:
            r = requests.get(self._url("/models"), headers=self._h(), timeout=5)
            d = r.json(); return d if isinstance(d, list) else d.get("models", [])
        except: return []

    def create_session(self) -> str:
        try:
            r = requests.post(self._url("/session"), headers=self._h(), timeout=5)
            d = r.json(); return d.get("id") or d.get("session_id") or uuid4().hex
        except: return uuid4().hex

    def chat(self, prompt: str, session_id: str = "", messages: list = [], system: str = "") -> dict:
        payload = {"prompt": prompt, "target": self.config.default_model,
                   "max_new_tokens": self.config.max_tokens,
                   "stream": False, "use_memory": self.config.use_memory}
        if session_id: payload["session_id"] = session_id
        if messages:   payload["messages"]   = messages
        if system:     payload["system"]      = system
        try:
            r = requests.post(self._url("/chat"), json=payload, headers=self._h(), timeout=120)
            return r.json()
        except Exception as e: return {"error": str(e)}

    def chat_stream(self, prompt: str, session_id: str = "", messages: list = [], system: str = "") -> Iterator[str]:
        payload = {"prompt": prompt, "target": self.config.default_model,
                   "max_new_tokens": self.config.max_tokens,
                   "stream": True, "use_memory": self.config.use_memory}
        if session_id: payload["session_id"] = session_id
        if messages:   payload["messages"]   = messages
        if system:     payload["system"]      = system
        try:
            with requests.post(self._url("/chat"), json=payload, headers=self._h(),
                               stream=True, timeout=180) as r:
                r.raise_for_status()
                buf = ""
                for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        buf += chunk
                        lines = buf.split("\n"); buf = lines[-1]
                        for line in lines[:-1]:
                            line = line.strip()
                            if not line: continue
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]": return
                                try:
                                    obj = json.loads(data)
                                    tok = obj.get("token") or obj.get("text") or obj.get("answer") or ""
                                    if tok: yield tok
                                except: yield data
                            else:
                                try:
                                    obj = json.loads(line)
                                    tok = obj.get("token") or obj.get("text") or obj.get("answer") or ""
                                    if tok: yield tok
                                except: yield line
        except Exception as e: yield f"\n[Stream error: {e}]\n"

    def execute_code(self, code: str, language: str = "python") -> dict:
        try:
            r = requests.post(self._url("/code/execute"),
                              json={"language": language, "code": code, "timeout": 30},
                              headers=self._h(), timeout=40)
            return r.json()
        except Exception as e: return {"error": str(e)}

    def generate_image(self, prompt: str) -> dict:
        try:
            r = requests.post(self._url("/image/generate"),
                              json={"prompt": prompt, "quality": "standard"},
                              headers=self._h(), timeout=60)
            return r.json()
        except Exception as e: return {"error": str(e)}

    def rag_add(self, text: str) -> dict:
        try:
            r = requests.post(self._url("/rag/documents"),
                              json={"text": text, "collection": "default"},
                              headers=self._h(), timeout=30)
            return r.json()
        except Exception as e: return {"error": str(e)}


# ─── Session ──────────────────────────────────────────────────────────────────

@dataclass
class Msg:
    role: str; content: str; ts: float = field(default_factory=time.time)

@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid4().hex)
    messages: list[Msg] = field(default_factory=list)
    model: str = DEFAULT_MODEL
    token_count: int = 0
    created_at: float = field(default_factory=time.time)


    max_history: int = 15  # Limite de la fenêtre glissante

    def add(self, role: str, content: str):
        self.messages.append(Msg(role=role, content=content))
        if role in ("user", "assistant"):
            self.token_count += len(content.split())

    def as_api(self, limit_context: bool = True) -> list:
        """Retourne les messages pour l'API avec fenêtre glissante."""
        if not limit_context or len(self.messages) <= self.max_history:
            return [{"role": m.role, "content": m.content} for m in self.messages]

        # Garder le premier message (souvent le contexte système/projet)
        # et les N derniers messages
        system_msgs = [m for m in self.messages if "PROJECT INFO" in m.content or m.role == "system"]
        recent_msgs = self.messages[-(self.max_history):]

        combined = []
        if system_msgs:
            combined.append(system_msgs[0])

        for m in recent_msgs:
            if m not in combined:
                combined.append(m)

        return [{"role": m.role, "content": m.content} for m in combined]

    @property
    def real_user_count(self) -> int:
        return sum(1 for m in self.messages
                   if m.role == "user"
                   and not m.content.startswith("[File:")
                   and not m.content.startswith("=== PROJECT INFO ==="))

    def save(self) -> Path:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        p = SESSION_DIR / f"{self.session_id}.json"
        p.write_text(json.dumps({
            "session_id": self.session_id, "model": self.model,
            "token_count": self.token_count, "created_at": self.created_at,
            "messages": [{"role": m.role, "content": m.content, "ts": m.ts} for m in self.messages],
        }, indent=2)); return p

    @classmethod
    def load(cls, sid: str) -> "Session":
        p = SESSION_DIR / f"{sid}.json"
        d = json.loads(p.read_text())
        s = cls(session_id=d["session_id"], model=d.get("model", DEFAULT_MODEL),
                token_count=d.get("token_count", 0), created_at=d.get("created_at", time.time()))
        s.messages = [Msg(role=m["role"], content=m["content"], ts=m.get("ts", 0))
                      for m in d.get("messages", [])]
        return s

    @classmethod
    def list_all(cls) -> list:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        result = []
        for p in sorted(SESSION_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                d = json.loads(p.read_text())
                result.append({"id": d["session_id"], "model": d.get("model","?"),
                                "messages": len(d.get("messages",[])),
                                "tokens": d.get("token_count",0), "ts": d.get("created_at",0)})
            except: pass
        return result


# ─── File Reader (affichage live comme Claude Code) ───────────────────────────

class FileReader:
    """
    Lit les fichiers dont l'IA a besoin et affiche la progression en temps réel.
    Identique au comportement de Claude Code : "Reading file.py..." avec spinner.
    """
    def __init__(self, console: Optional[Console], renderer):
        self.console  = console
        self.renderer = renderer

    def read_with_display(self, path: str) -> str:
        """Lit un fichier en affichant un indicateur visuel."""
        p = Path(path)
        if not p.exists():
            # Chercher dans le workspace
            root = Path.cwd()
            candidates = list(root.glob(f"**/{p.name}"))
            if candidates:
                p = candidates[0]
            else:
                self._show_read_error(path, "File not found")
                return f"[File not found: {path}]"

        try:
            self._show_reading(str(p))
            content = p.read_text(encoding="utf-8", errors="replace")
            lines   = content.count("\n") + 1
            size_kb = p.stat().st_size / 1024
            self._show_read_done(str(p.relative_to(Path.cwd()) if p.is_relative_to(Path.cwd()) else p),
                                 lines, size_kb)
            return content
        except Exception as e:
            self._show_read_error(path, str(e))
            return f"[Error reading {path}: {e}]"

    def read_files_for_context(self, file_list: list[str]) -> dict[str, str]:
        """Lit plusieurs fichiers en affichant chacun."""
        results = {}
        if HAS_RICH and self.console:
            self.console.print()
            self.console.print(Text.from_markup("[dim]Reading project files…[/dim]"))
        for path in file_list:
            results[path] = self.read_with_display(path)
        if HAS_RICH and self.console:
            self.console.print()
        return results

    def _show_reading(self, path: str):
        if HAS_RICH and self.console:
            rel = self._rel(path)
            self.console.print(
                Text.from_markup(f"  [dim]Reading[/dim]  [cyan]{rel}[/cyan]"),
                end="\r"
            )
        else:
            print(f"  Reading {path}...", end="\r")

    def _show_read_done(self, path: str, lines: int, size_kb: float):
        if HAS_RICH and self.console:
            self.console.print(
                Text.from_markup(
                    f"  [green]✔[/green]  [cyan]{path}[/cyan]  "
                    f"[bright_black]{lines} lines · {size_kb:.1f}KB[/bright_black]"
                )
            )
        else:
            print(f"  ✔  {path}  ({lines} lines)")

    def _show_read_error(self, path: str, error: str):
        if HAS_RICH and self.console:
            self.console.print(Text.from_markup(f"  [red]✗[/red]  [dim]{path}[/dim]  [red]{error}[/red]"))
        else:
            print(f"  ✗  {path}: {error}")

    @staticmethod
    def _rel(path: str) -> str:
        try: return str(Path(path).relative_to(Path.cwd()))
        except: return path

    def detect_needed_files(self, prompt: str) -> list[str]:
        """
        Détecte quels fichiers le prompt demande implicitement.
        Ex: "note mon projet" → lit tous les .py/.ts/.js importants
        Ex: "regarde startup_screen.py" → lit ce fichier précis
        """
        root   = Path.cwd()
        needed = []

        # 1. Fichiers explicitement mentionnés
        for word in re.findall(r'[\w./\\-]+\.\w{1,6}', prompt):
            candidates = list(root.glob(f"**/{word}")) + [Path(word)]
            for c in candidates:
                if c.exists() and str(c.relative_to(root) if c.is_relative_to(root) else c) not in needed:
                    needed.append(str(c.relative_to(root) if c.is_relative_to(root) else c))

        # 2. Intent "project evaluation / note / review"
        eval_keywords = re.compile(
            r"\b(note|évalue|evaluat|review|analyse|analyz|lis|read|examine|regarde|check|audit|scan)\b"
            r".*?\b(projet|project|code|fichier|file|app|src|tout|all|everything|workspace)\b",
            re.IGNORECASE,
        )
        if eval_keywords.search(prompt) or ("note" in prompt.lower() and "projet" in prompt.lower()):
            # Lit les fichiers Python/TS/JS clés (pas trop pour ne pas exploser le contexte)
            for ext in ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx"]:
                for f in sorted(root.glob(f"src/**/{ext}"))[:4]:
                    rel = str(f.relative_to(root))
                    if rel not in needed: needed.append(rel)
                for f in sorted(root.glob(ext))[:3]:
                    rel = str(f.relative_to(root))
                    if rel not in needed: needed.append(rel)
            # Configs importants
            for cfg_file in ["setup.py", "pyproject.toml", "package.json", "requirements.txt",
                             "CYGNISAI.md", "README.md"]:
                if (root / cfg_file).exists() and cfg_file not in needed:
                    needed.append(cfg_file)

        return needed[:12]  # max 12 fichiers à la fois


# ─── File Editor (diff + Accepter/Refuser comme Claude Code) ──────────────────

class FileEditor:
    """
    Propose des modifications de fichiers avec affichage du diff coloré
    et boutons interactifs Accepter / Refuser — identique à Claude Code.
    """
    def __init__(self, console: Optional[Console], renderer):
        self.console  = console
        self.renderer = renderer

    def propose_edit(self, path: str, new_content: str, description: str = "") -> bool:
        """
        Affiche le diff entre le fichier actuel et la nouvelle version,
        puis demande Accepter ou Refuser.
        Retourne True si accepté.
        """
        p = Path(path)
        old_content = ""
        if p.exists():
            try: old_content = p.read_text(encoding="utf-8", errors="replace")
            except: pass

        # Calculer le diff
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{path}", tofile=f"b/{path}",
            lineterm="",
        ))

        if not diff_lines and old_content == new_content:
            if HAS_RICH and self.console:
                self.console.print(Text.from_markup(f"  [dim]No changes in {path}[/dim]"))
            return False

        self._display_diff(path, diff_lines, description, old_lines, new_lines)
        return self._ask_accept(path)

    def _display_diff(self, path: str, diff_lines: list, description: str,
                      old_lines: list, new_lines: list):
        if not HAS_RICH or not self.console:
            print(f"\n--- Modifications proposées : {path} ---")
            print("".join(diff_lines[:80]))
            return

        c = self.console
        c.print()

        # Header
        added   = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

        header = Table.grid(padding=(0, 2)); header.add_column(); header.add_column()
        header.add_row(
            Text.from_markup(f"[bold white]{path}[/bold white]"),
            Text.from_markup(
                f"[green]+{added}[/green]  [red]-{removed}[/red]"
                + (f"  [dim]{description}[/dim]" if description else "")
            ),
        )
        c.print(Panel(header, border_style="bright_black", padding=(0, 1),
                      title="[bold yellow] Proposed Changes [/bold yellow]"))

        # Diff coloré — on reconstruit le diff en rich markup
        diff_text = []
        for line in diff_lines[2:]:  # skip les lignes +++/---
            if line.startswith("@@"):
                diff_text.append(f"[bright_black]{line}[/bright_black]")
            elif line.startswith("+"):
                diff_text.append(f"[green]{line}[/green]")
            elif line.startswith("-"):
                diff_text.append(f"[red]{line}[/red]")
            else:
                diff_text.append(f"[dim]{line}[/dim]")

        # Affiche le diff dans un panel scrollable (max 60 lignes affichées)
        visible = diff_text[:60]
        if len(diff_text) > 60:
            visible.append(f"[bright_black]  … {len(diff_text)-60} more lines[/bright_black]")

        c.print(Panel(
            Text.from_markup("\n".join(visible)),
            border_style="bright_black",
            padding=(0, 1),
        ))

    def _ask_accept(self, path: str) -> bool:
        """Affiche les boutons Accepter / Refuser et attend la réponse."""
        if HAS_RICH and self.console:
            c = self.console
            c.print()
            c.print(
                Text.from_markup(
                    "  [bold green]❯ 1. Accept[/bold green]  "
                    "[dim]Apply changes to[/dim] [cyan]" + path + "[/cyan]"
                )
            )
            c.print(
                Text.from_markup("  [bold red]  2. Reject[/bold red]  [dim]Discard changes[/dim]")
            )
            c.print()

        # Lecture interactive
        if HAS_PT:
            try:
                ans = pt_prompt(
                    HTML("<ansicyan><b>  Apply? [1/2] </b></ansicyan>"),
                    default="1",
                ).strip()
            except (EOFError, KeyboardInterrupt):
                ans = "2"
        else:
            ans = input("  Apply changes? [1=Accept / 2=Reject]: ").strip()

        accepted = ans in ("", "1", "y", "yes", "o", "oui")

        if HAS_RICH and self.console:
            if accepted:
                self.console.print(Text.from_markup(f"  [bold green]✔  Changes applied → {path}[/bold green]"))
            else:
                self.console.print(Text.from_markup(f"  [bold red]✗  Changes rejected[/bold red]"))
        return accepted

    def apply(self, path: str, new_content: str):
        """Écrit le fichier après acceptation."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(new_content, encoding="utf-8")

    def extract_edits_from_response(self, response: str) -> list[dict]:
        """
        Extrait les blocs de modification de la réponse IA.
        Supporte les formats :
          <<<EDIT:path>>> ... <<<END>>>
          ```lang\n...``` avec un nom de fichier détectable au-dessus
        """
        edits = []

        # Format explicite <<<EDIT:path>>>
        for m in _EDIT_BLOCK_RE.finditer(response):
            edits.append({"path": m.group(1).strip(), "content": m.group(2)})

        # Format markdown avec fichier détectable
        if not edits:
            # Cherche: "### src/foo.py" ou "`src/foo.py`:" suivi d'un ```
            for m in re.finditer(
                r'(?:^|\n)(?:###?\s+|`)([\w./\\-]+\.[a-zA-Z]{1,6})`?\s*(?::|\n)\s*\n```\w*\n(.*?)```',
                response, re.DOTALL
            ):
                edits.append({"path": m.group(1).strip(), "content": m.group(2)})

        # Fallback : premier bloc de code si une seule mention de fichier dans le contexte
        if not edits:
            code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', response, re.DOTALL)
            file_mentions = re.findall(r'[\w./\\-]+\.[a-zA-Z]{1,6}', response)
            # Fichier le plus récemment mentionné
            existing = [f for f in file_mentions if Path(f).exists() or (Path.cwd() / f).exists()]
            if existing and code_blocks:
                edits.append({"path": existing[-1], "content": code_blocks[-1]})

        return edits


# ─── Tools ────────────────────────────────────────────────────────────────────

class Tools:
    @staticmethod
    def read(path: str) -> str:
        try: return Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as e: return f"Error reading {path}: {e}"

    @staticmethod
    def write(path: str, content: str) -> str:
        try:
            p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Written {len(content)} chars to {path}"
        except Exception as e: return f"Error writing {path}: {e}"

    @staticmethod
    def ls(pattern: str = "**/*") -> list[str]:
        try:
            root = Path.cwd()
            return [str(f.relative_to(root)) for f in sorted(root.glob(pattern))
                    if ".git" not in str(f) and "__pycache__" not in str(f)][:80]
        except: return []

    @staticmethod
    def run(cmd: str, timeout: int = 30) -> str:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            parts = []
            if r.stdout.strip(): parts.append(r.stdout.strip())
            if r.stderr.strip(): parts.append(f"[stderr] {r.stderr.strip()}")
            if r.returncode:     parts.append(f"[exit {r.returncode}]")
            return "\n".join(parts) or "(no output)"
        except subprocess.TimeoutExpired: return f"Timeout after {timeout}s"
        except Exception as e:           return f"Error: {e}"

    @staticmethod
    def workspace_context() -> str:
        root = Path.cwd()
        ctx  = "You are CygnisAI, a senior software engineer assistant with full visibility of the current workspace.\n"
        ctx += f"Project root: {root}\n\n"

        init_file = root / "CYGNISAI.md"
        if init_file.exists():
            ctx += f"=== CYGNISAI.md ===\n{init_file.read_text(encoding='utf-8', errors='replace')[:4000]}\n\n"

        readme = root / "README.md"
        if readme.exists():
            ctx += f"=== README.md ===\n{readme.read_text(encoding='utf-8', errors='replace')[:3000]}\n\n"

        ctx += "=== PROJECT STRUCTURE ===\n"
        files_found = []
        for ext in ["*.py","*.ts","*.tsx","*.js","*.rs","*.go","*.md","Cargo.toml","package.json","requirements.txt"]:
            files_found.extend(root.glob(f"src/**/{ext}"))
            files_found.extend(root.glob(f"**/{ext}"))

        unique_files = sorted({str(f.relative_to(root)) for f in files_found
                                if ".git" not in str(f) and "__pycache__" not in str(f)})
        if unique_files:
            ctx += "\n".join(f"  - {f}" for f in unique_files[:150])
        ctx += "\n\nIMPORTANT: You CAN see the project structure. Reference specific files in your analysis."
        return ctx

    @staticmethod
    def make_init(cwd: Optional[str] = None) -> str:
        root = Path(cwd or Path.cwd())
        target = root / "CYGNISAI.md"
        proj_name = root.name
        readme = root / "README.md"
        if readme.exists():
            m = re.search(r"^#\s+(.+)$", readme.read_text(), re.M)
            if m: proj_name = m.group(1).strip()

        files = list(root.glob("**/*"))
        exts  = {f.suffix for f in files if f.is_file()}
        profiles = []
        if ".py" in exts:                   profiles.append("Python (PEP8, snake_case)")
        if ".ts" in exts or ".tsx" in exts: profiles.append("TypeScript (Strict, camelCase)")
        if ".js" in exts:                   profiles.append("JavaScript")
        if ".rs" in exts:                   profiles.append("Rust")
        if ".go" in exts:                   profiles.append("Go")

        arch = []
        if (root/"src/app").is_dir():   arch.append("- Framework: Next.js (App Router)")
        if (root/"tailwind.config.ts").exists() or (root/"tailwind.config.js").exists():
            arch.append("- Styling: Tailwind CSS")
        if (root/"manage.py").exists(): arch.append("- Framework: Django")

        commands = []
        pkg = root / "package.json"
        if pkg.exists():
            try:
                scripts = json.loads(pkg.read_text()).get("scripts", {})
                for n in ["dev","build","test","lint"]:
                    if n in scripts: commands.append(f"- **{n.capitalize()}**: `npm run {n}`")
            except: pass
        if (root/"requirements.txt").exists():
            commands.append("- **Install**: `pip install -r requirements.txt`")
            commands.append("- **Test**: `pytest`")

        struct = []
        for d in ["src","lib","components","api","tests","docs"]:
            if (root/d).is_dir(): struct.append(f"- `{d}/`: Project folder")

        content = f"""# CYGNISAI.md

Context file for CygnisAI to work efficiently with `{proj_name}`.

## Development Commands
{chr(10).join(commands) if commands else "- (No build scripts detected)"}

## Project Architecture
{chr(10).join(arch) if arch else "- Profile: " + (", ".join(profiles) or "General")}
{chr(10).join(struct)}

## AI Guidelines
- Response language: match the user's language (default: French)
- Code style: {", ".join(profiles) or "Standard"}
- Always explain changes before applying them
- Use `/file <path>` to inject specific files for deep analysis

---
*Generated by CyCode v{VERSION} — {time.strftime("%Y-%m-%d %H:%M:%S")}*
"""
        target.write_text(content, encoding="utf-8"); return str(target)


# ─── Renderer ─────────────────────────────────────────────────────────────────

class Renderer:
    def __init__(self, console: Optional[Console] = None, theme: str = "monokai"):
        self.console = console; self.theme = theme

    def c(self) -> Console: return self.console  # type: ignore

    def response(self, text: str):
        if not text: return
        if not HAS_RICH or not self.console: print(text); return
        if "```" in text: self._mixed(text)
        else:
            try: self.c().print(Markdown(text))
            except: self.c().print(text)

    def _mixed(self, text: str):
        c = self.c()
        parts = re.split(r"```(\w*)\n?(.*?)```", text, flags=re.DOTALL)
        i = 0
        while i < len(parts):
            if i % 3 == 0:
                prose = parts[i].strip()
                if prose:
                    try: c.print(Markdown(prose))
                    except: c.print(prose)
            elif i % 3 == 1:
                lang = parts[i] or "text"; code = parts[i+1] if i+1 < len(parts) else ""
                try: c.print(Syntax(code.strip(), lang, theme=self.theme, line_numbers=True, word_wrap=True))
                except: c.print(f"```{lang}\n{code}\n```")
                i += 1
            i += 1

    def status_bar(self, session: Session, config: Config, api_ok: bool) -> str:
        sym = "●" if api_ok else "◌"
        auth = "Auth" if config.api_key else "no key"
        return f" {sym} {session.model} · {session.real_user_count} msgs · ~{session.token_count} tok · {auth} · {session.session_id[:8]}… "

    def info(self, msg: str):
        if HAS_RICH and self.console: self.c().print(f"[dim cyan]ℹ  {msg}[/dim cyan]")
        else: print(f"  {msg}")

    def ok(self, msg: str):
        if HAS_RICH and self.console: self.c().print(f"[bold green]✔  {msg}[/bold green]")
        else: print(f"OK: {msg}")

    def err(self, msg: str):
        if HAS_RICH and self.console: self.c().print(f"[bold red]✗  {msg}[/bold red]")
        else: print(f"ERROR: {msg}")

    def box(self, title: str, content: str):
        if HAS_RICH and self.console:
            self.c().print(Panel(content, title=f"[bold cyan]{title}[/bold cyan]",
                                 border_style="cyan", padding=(0,1)))
        else: print(f"[{title}]\n{content}")

    def thinking_panel(self, thinking: str):
        if not thinking: self.info("No thinking data available."); return
        if HAS_RICH and self.console:
            self.c().print(Panel(Text(thinking, style="dim"),
                                 title="[bold yellow] CygnisAI Thinking [/bold yellow]",
                                 border_style="yellow", padding=(1,2)))
        else: print(f"[Thinking]\n{thinking}")

    def file_reading_header(self, count: int):
        if HAS_RICH and self.console:
            self.c().print()
            self.c().print(Text.from_markup(
                f"[dim]Scanning [cyan]{count}[/cyan] file{'s' if count!=1 else ''}…[/dim]"
            ))


# ─── Slash commands ───────────────────────────────────────────────────────────

COMMANDS_HELP = [
    ("/help",     "Show this help"),
    ("/init",     "Scan project and create CYGNISAI.md"),
    ("/model",    "/model [id]  — show or change active model"),
    ("/models",   "List all CygnisAI models"),
    ("/session",  "/session [new|list|load <id>|save|clear|info]"),
    ("/clear",    "Clear conversation history"),
    ("/status",   "API health and config"),
    ("/config",   "/config [key] [value]"),
    ("/file",     "/file <path>  — inject file into context"),
    ("/edit",     "/edit <path>  — propose AI edit for a file"),
    ("/write",    "/write <path>  — write last response to file"),
    ("/ls",       "/ls [pattern]  — list workspace files"),
    ("/exec",     "/exec <cmd>  — run local shell command"),
    ("/sandbox",  "/sandbox <code>  — run via CygnisAI sandbox"),
    ("/image",    "/image <prompt>  — generate image via CyVision"),
    ("/memory",   "/memory <text>  — inject into RAG memory"),
    ("/plugins",  "/plugins [list|enable <id>|disable <id>|search <q>|github <q>]"),
    ("/skills",   "/skills [list|use <id> <prompt>]"),
    ("/thinking", "Show last CygnisAI thinking (also Ctrl+T)"),
    ("/history",  "Show conversation history"),
    ("/tokens",   "Show token usage"),
    ("/cd",       "/cd <path>  — change working directory"),
    ("/exit",     "Exit CyCode"),
]


# ─── REPL ─────────────────────────────────────────────────────────────────────

class REPL:
    def __init__(self, config: Config, show_banner: bool = True):
        self.config     = config
        self.client     = CygnisClient(config)
        self.session    = Session(model=config.default_model)
        self.console    = Console() if HAS_RICH else None
        self.renderer   = Renderer(self.console, theme=config.theme)
        self.tools      = Tools()
        self.plugins    = PluginManager()
        self.file_reader = FileReader(self.console, self.renderer)
        self.file_editor = FileEditor(self.console, self.renderer)
        self._last_resp  = ""
        self._last_think = ""
        self._api_ok     = False
        self._models_cache: list = []
        self._system_ctx = ""
        self._show_banner = show_banner
        self._probe()

    def _probe(self):
        def _run():
            h = self.client.health()
            self._api_ok = h.get("status") not in ("error","unreachable")
            self._models_cache = self.client.models()
            if self._api_ok and self.config.api_key:
                rid = self.client.create_session()
                if rid: self.session.session_id = rid
        t = threading.Thread(target=_run, daemon=True); t.start(); t.join(timeout=2.5)

    def _build_system(self) -> str:
        parts = []
        if self.config.auto_read_workspace:
            ctx = self.tools.workspace_context()
            if ctx: parts.append(ctx)
        plugin_ctx = self.plugins.active_context()
        if plugin_ctx: parts.append(plugin_ctx)
        return "\n\n".join(parts)

    def _make_ps(self) -> Optional["PromptSession"]:
        if not HAS_PT: return None
        kb = KeyBindings()
        @kb.add("c-c")
        def _cc(event): event.app.current_buffer.text = ""
        @kb.add("c-t")
        def _ct(event): event.app.exit(result="__SHOW_THINKING__")
        return PromptSession(
            history=FileHistory(str(HISTORY_FILE)),
            auto_suggest=AutoSuggestFromHistory(),
            style=PtStyle.from_dict({"prompt": "ansicyan bold"}),
            key_bindings=kb, enable_history_search=True,
        )

    def run(self):
        if self._show_banner: self._print_banner()
        self._system_ctx = self._build_system()
        ps = self._make_ps()

        while True:
            try:
                sb  = self.renderer.status_bar(self.session, self.config, self._api_ok)
                raw = (ps.prompt(HTML("<ansicyan><b>❯  </b></ansicyan>"),
                                 rprompt=HTML(f"<ansibrightblack>{sb}</ansibrightblack>"))
                       if ps else input("❯  "))
            except (EOFError, KeyboardInterrupt):
                self.renderer.info("Session saved. Goodbye."); self.session.save(); sys.exit(0)

            line = raw.strip() if isinstance(raw, str) else ""
            if line == "__SHOW_THINKING__":
                self.renderer.thinking_panel(self._last_think); continue
            if not line: continue
            self._cmd(line) if line.startswith("/") else self._msg(line)

    def _print_banner(self):
        if not HAS_RICH or not self.console: return
        try:
            from .startup_screen import render_banner, CygnisStatus as _St
            st = _St(api_key=self.config.api_key)
            st.connected = self._api_ok; st.model_fleet = self._models_cache
            render_banner(st, api_key=self.config.api_key, model=self.config.default_model,
                          session_id=self.session.session_id, console=self.console)
        except Exception as e:
            self.console.print(f"[dim]Banner error: {e}[/dim]")

    # ── Message ───────────────────────────────────────────────────────────────

    def _notify_thinking(self):
        """Affiche la notification discrète 'CygnisAI a réfléchi' sous la réponse."""
        if not self._last_think:
            return
        if HAS_RICH and self.console:
            self.console.print(Text.from_markup(
                "  [dim]ℹ  CygnisAI a réfléchi  ·  "
                "[bold]Ctrl+T[/bold] pour voir[/dim]"
            ))
        else:
            print("  ℹ  CygnisAI a réfléchi — tapez /thinking pour voir")

    def _check_context_size(self, prompt_text: str):
        """
        Estime la taille du contexte total et avertit si on approche de la limite.
        Affiche un avertissement jaune si > 80% de la limite, rouge si > 100%.
        """
        # Estimation : historique + system + nouveau prompt
        history_chars = sum(len(m.content) for m in self.session.messages)
        system_chars  = len(self._system_ctx)
        total_chars   = history_chars + system_chars + len(prompt_text)
        # ~4 chars par token
        total_tokens  = total_chars // 4

        limit = CTX_LIMITS.get(self.config.default_model, 8_000)
        ratio = total_tokens / limit

        if ratio >= 1.0:
            if HAS_RICH and self.console:
                self.console.print(Text.from_markup(
                    f"  [bold red]⚠  Contexte saturé[/bold red]  "
                    f"[red]~{total_tokens:,} tokens estimés — limite {limit:,} ({self.config.default_model})[/red]\n"
                    f"  [dim]Conseil : /clear pour vider l'historique, ou /session new pour une nouvelle session.[/dim]"
                ))
            else:
                print(f"  ⚠ Contexte saturé (~{total_tokens} tokens, limite {limit}). Utilise /clear.")
        elif ratio >= CTX_WARN_RATIO:
            pct = int(ratio * 100)
            if HAS_RICH and self.console:
                self.console.print(Text.from_markup(
                    f"  [yellow]⚠  Contexte chargé à {pct}%[/yellow]  "
                    f"[dim]~{total_tokens:,} / {limit:,} tokens estimés ({self.config.default_model})[/dim]  "
                    f"[dim]· /clear pour libérer[/dim]"
                ))
            else:
                print(f"  ⚠ Contexte à {pct}% (~{total_tokens}/{limit} tokens). Pense à /clear bientôt.")

    def _msg(self, prompt: str):
        # Plugin Google Search implicite
        if prompt.lower().startswith("search ") and self.plugins.is_active("google_search"):
            result = self.plugins.run_google_search(prompt[7:].strip())
            self.session.add("user", prompt); self.session.add("assistant", result)
            self._last_resp = result; self.renderer.response(result)
            if HAS_RICH and self.console: self.console.print(Rule(style="bright_black"))
            return

        # ── Lecture intelligente des fichiers nécessaires ──────────────────
        needed_files = self.file_reader.detect_needed_files(prompt)
        file_context = ""
        if needed_files:
            self.renderer.file_reading_header(len(needed_files))
            files_content = self.file_reader.read_files_for_context(needed_files)
            file_context = "\n\n".join(
                f"=== {path} ===\n{content[:3000]}"
                for path, content in files_content.items()
                if not content.startswith("[Error") and not content.startswith("[File not")
            )

        # ── Construction du prompt enrichi ────────────────────────────────
        if self.session.real_user_count == 0:
            project_info = self.tools.workspace_context()
            if file_context:
                enhanced = f"=== PROJECT INFO ===\n{project_info}\n\n=== FILE CONTENTS ===\n{file_context}\n\n=== USER QUERY ===\n{prompt}"
            else:
                enhanced = f"=== PROJECT INFO ===\n{project_info}\n\n=== USER QUERY ===\n{prompt}"
            self.session.add("user", enhanced)
        else:
            if file_context:
                self.session.add("user", f"=== FILE CONTENTS ===\n{file_context}\n\n{prompt}")
            else:
                self.session.add("user", prompt)

        msgs = self.session.as_api()[:-1]
        self._system_ctx = self._build_system()

        # ── Vérification taille du contexte ───────────────────────────────
        self._check_context_size(self.session.messages[-1].content)

        if self.config.stream: self._stream(prompt, msgs)
        else: self._blocking(prompt, msgs)

    def _stream(self, prompt: str, msgs: list):
        if HAS_RICH and self.console: self.console.print()
        actual_prompt = self.session.messages[-1].content
        full = ""
        try:
            chunks = list(self.client.chat_stream(actual_prompt, self.session.session_id, msgs, self._system_ctx))
            if not chunks: self._blocking(prompt, msgs); return

            if len(chunks) == 1:
                raw = chunks[0]
                try:
                    obj = json.loads(raw)
                    raw = obj.get("answer") or obj.get("text") or obj.get("content") or raw
                except: pass
                clean, thinking = clean_output(raw)
                self._last_think = thinking; full = clean
                self.renderer.response(clean)
            else:
                buf = ""
                for chunk in chunks:
                    buf += chunk
                    if HAS_RICH and self.console: self.console.print(chunk, end="", highlight=False)
                    else: print(chunk, end="", flush=True)
                print()
                full, thinking = clean_output(buf); self._last_think = thinking
        except Exception as e:
            self.renderer.err(f"Stream failed: {e}"); self._blocking(prompt, msgs); return

        if full:
            self.session.add("assistant", full); self._last_resp = full
            # ── Détection et proposition d'éditions ───────────────────────
            self._handle_edits(full)

        if HAS_RICH and self.console:
            self.console.print()
            # ── Notification thinking discrète ────────────────────────────
            self._notify_thinking()
            self.console.print(Rule(style="bright_black"))
        print()

    def _blocking(self, prompt: str, msgs: list):
        actual_prompt = self.session.messages[-1].content
        if HAS_RICH and self.console:
            idx = [0]
            def _spin(): return Text.from_markup(f"[cyan]{THINKING_STATES[idx[0]][1]}[/cyan]")
            with Live(Spinner("dots", text=_spin()), console=self.console, refresh_per_second=10) as live:
                done = threading.Event()
                def _cycle():
                    while not done.is_set():
                        time.sleep(0.8); idx[0] = (idx[0]+1) % len(THINKING_STATES)
                        live.update(Spinner(THINKING_STATES[idx[0]][0], text=_spin()))
                threading.Thread(target=_cycle, daemon=True).start()
                result = self.client.chat(actual_prompt, self.session.session_id, msgs, self._system_ctx)
                done.set()
        else:
            print("  Thinking…", end="", flush=True)
            result = self.client.chat(actual_prompt, self.session.session_id, msgs, self._system_ctx)
            print("\r           \r", end="")

        raw    = (result.get("answer") or result.get("text") or result.get("content")
                  or result.get("response") or result.get("error") or str(result))
        answer, thinking = clean_output(raw)
        self._last_think = thinking
        self.session.add("assistant", answer); self._last_resp = answer
        print(); self.renderer.response(answer)
        # ── Détection et proposition d'éditions ───────────────────────────
        self._handle_edits(answer)
        if HAS_RICH and self.console:
            self.console.print()
            # ── Notification thinking discrète ────────────────────────────
            self._notify_thinking()
            self.console.print(Rule(style="bright_black"))
        print()

    def _handle_edits(self, response: str):
        """Extrait les blocs d'édition de la réponse et propose Accepter/Refuser."""
        edits = self.file_editor.extract_edits_from_response(response)
        for edit in edits:
            path    = edit["path"]
            content = edit["content"]
            # Seulement si le fichier existe ou est clairement un chemin relatif au projet
            if Path(path).exists() or (Path.cwd() / path).exists() or "/" in path or "\\" in path:
                actual_path = path if Path(path).exists() else str(Path.cwd() / path)
                accepted = self.file_editor.propose_edit(actual_path, content)
                if accepted:
                    self.file_editor.apply(actual_path, content)

    # ── Commands ──────────────────────────────────────────────────────────────

    def _cmd(self, line: str):
        parts = line.split(maxsplit=1)
        cmd   = parts[0].lower()
        args  = parts[1].strip() if len(parts) > 1 else ""
        dispatch = {
            "/help":     self._c_help,
            "/init":     lambda: self._c_init(),
            "/model":    lambda: self._c_model(args),
            "/models":   lambda: self._c_models(),
            "/session":  lambda: self._c_session(args),
            "/clear":    lambda: self._c_clear(),
            "/status":   lambda: self._c_status(),
            "/config":   lambda: self._c_config(args),
            "/file":     lambda: self._c_file(args),
            "/edit":     lambda: self._c_edit(args),
            "/write":    lambda: self._c_write(args),
            "/ls":       lambda: self._c_ls(args),
            "/exec":     lambda: self._c_exec(args),
            "/sandbox":  lambda: self._c_sandbox(args),
            "/image":    lambda: self._c_image(args),
            "/memory":   lambda: self._c_memory(args),
            "/plugins":  lambda: self._c_plugins(args),
            "/skills":   lambda: self._c_skills(args),
            "/thinking": lambda: self.renderer.thinking_panel(self._last_think),
            "/history":  lambda: self._c_history(),
            "/tokens":   lambda: self._c_tokens(),
            "/cd":       lambda: self._c_cd(args),
            "/login":    lambda: self._c_login(),
            "/exit":     lambda: self._c_exit(),
            "/quit":     lambda: self._c_exit(),
        }
        h = dispatch.get(cmd)
        if h: h()
        else: self.renderer.err(f"Unknown command: {cmd}  (type /help)")

    def _c_help(self):
        if HAS_RICH and self.console:
            t = Table(show_header=False, box=box.SIMPLE, padding=(0,2))
            t.add_column(style="bold cyan", no_wrap=True, min_width=14); t.add_column(style="dim")
            for cmd, desc in COMMANDS_HELP: t.add_row(cmd, desc)
            self.console.print(Panel(t, title="[bold]CyCode Commands[/bold]", border_style="cyan"))
            self.console.print(Text.from_markup(
                "[bright_black]  Ctrl+T → CygnisAI thinking  ·  Ctrl+D → exit  ·  ↑↓ → history[/bright_black]"
            ))
        else:
            for cmd, desc in COMMANDS_HELP: print(f"  {cmd:18s}  {desc}")

    def _c_init(self):
        target = Path.cwd() / "CYGNISAI.md"
        if target.exists():
            if HAS_RICH and self.console:
                from rich.prompt import Confirm
                if not Confirm.ask("  [yellow]CYGNISAI.md already exists.[/yellow] Overwrite?",
                                   default=False, console=self.console):
                    self.renderer.info("Cancelled."); return
            else:
                if input("Overwrite? [y/N] ").lower() != "y": return
        path = self.tools.make_init()
        self._system_ctx = self._build_system()
        self.renderer.ok(f"Created: {path}")
        self.renderer.info("Edit this file to give CygnisAI context about your project.")

    def _c_model(self, args: str):
        if not args:
            self.renderer.info(f"Active model: [bold cyan]{self.session.model}[/bold cyan]")
            avail = "  ·  ".join(m.get("id","") for m in self._models_cache) or "alpha1 · alpha2 · auto"
            self.renderer.info(f"Available: {avail}"); return
        self.session.model = args; self.config.default_model = args; self.config.save()
        self.renderer.ok(f"Model → [bold]{args}[/bold]")

    def _c_models(self):
        default = [
            {"id":"alpha1","architecture":"ChatML 1.7B","context_window":"4k","use_case":"Fast response"},
            {"id":"alpha2","architecture":"Llama-3 8B", "context_window":"8k","use_case":"Complex reasoning"},
            {"id":"auto",  "architecture":"MoE Router",  "context_window":"Dynamic","use_case":"Auto-routing"},
        ]
        if HAS_RICH and self.console:
            with self.console.status("[cyan]Fetching models…[/cyan]"): live = self.client.models()
        else: live = self.client.models()
        models = live if live else default
        if HAS_RICH and self.console:
            t = Table(title="CygnisAI Models", box=box.SIMPLE_HEAD)
            t.add_column("ID", style="bold cyan"); t.add_column("Architecture")
            t.add_column("Context"); t.add_column("Use case")
            for m in models:
                mark = " ←" if m.get("id") == self.session.model else ""
                t.add_row(str(m.get("id","?"))+mark, str(m.get("architecture","—")),
                          str(m.get("context_window","—")), str(m.get("use_case","—")))
            self.console.print(t)
        else:
            for m in models: print(f"  {m.get('id','?'):10s} {m.get('use_case','')}")

    def _c_session(self, args: str):
        parts = args.split(maxsplit=1); sub = parts[0].lower() if parts else ""
        if not sub or sub == "info":
            self.renderer.box("Session",
                f"ID: {self.session.session_id}\nModel: {self.session.model}\n"
                f"Messages: {len(self.session.messages)}\nTokens: ~{self.session.token_count}")
        elif sub == "new":
            self.session.save(); self.session = Session(model=self.config.default_model)
            if self._api_ok and self.config.api_key:
                rid = self.client.create_session()
                if rid: self.session.session_id = rid
            self.renderer.ok(f"New session: {self.session.session_id[:16]}…")
        elif sub == "save": self.renderer.ok(f"Saved: {self.session.save()}")
        elif sub == "list":
            sessions = Session.list_all()
            if not sessions: self.renderer.info("No saved sessions."); return
            if HAS_RICH and self.console:
                import datetime
                t = Table(box=box.SIMPLE_HEAD)
                t.add_column("ID", style="cyan"); t.add_column("Model")
                t.add_column("Msgs", justify="right"); t.add_column("Tokens", justify="right"); t.add_column("Created")
                for s in sessions[:20]:
                    cr = datetime.datetime.fromtimestamp(s["ts"]).strftime("%Y-%m-%d %H:%M") if s["ts"] else "?"
                    t.add_row(s["id"][:18]+"…", s["model"], str(s["messages"]), str(s["tokens"]), cr)
                self.console.print(t)
            else:
                for s in sessions[:20]: print(f"  {s['id'][:18]}  {s['model']}  {s['messages']} msgs")
        elif sub == "load" and len(parts)>1:
            try:
                self.session = Session.load(parts[1].strip())
                self.renderer.ok(f"Loaded ({len(self.session.messages)} messages)")
            except Exception as e: self.renderer.err(f"Cannot load: {e}")
        elif sub == "clear": self._c_clear()
        else: self.renderer.info("Usage: /session [new|list|load <id>|save|clear|info]")

    def _c_clear(self):
        self.session.messages.clear(); self.session.token_count = 0
        self._last_resp = ""; self._last_think = ""
        self.renderer.ok("History cleared")

    def _c_status(self):
        if HAS_RICH and self.console:
            with self.console.status("[cyan]Checking API…[/cyan]"): h = self.client.health()
        else: h = self.client.health()
        self.renderer.box("Status",
            f"API    : {json.dumps(h)}\n"
            f"Auth   : {'Authenticated' if self.config.api_key else 'No key'}\n"
            f"Model  : {self.config.default_model}\n"
            f"Stream : {self.config.stream}\n"
            f"Plugins: {', '.join(self.plugins._active.keys()) or 'none'}\n"
            f"Theme  : {self.config.theme}\n"
            f"Worksp : {self.config.workspace}")

    def _c_config(self, args: str):
        parts = args.split(maxsplit=1)
        if not args:
            cfg = {k: ("***" if k=="api_key" and v else v) for k,v in self.config.__dict__.items()}
            self.renderer.box("Config", json.dumps(cfg, indent=2)); return
        key = parts[0]
        if len(parts) < 2: self.renderer.info(f"{key} = {getattr(self.config, key, '?')}"); return
        if not hasattr(self.config, key): self.renderer.err(f"Unknown key: {key}"); return
        cur = getattr(self.config, key); vs = parts[1]
        try:
            nv = vs.lower() in ("1","true","yes") if isinstance(cur, bool) \
                 else int(vs) if isinstance(cur, int) else vs
            setattr(self.config, key, nv); self.config.save(); self.renderer.ok(f"{key} = {nv}")
        except ValueError: self.renderer.err(f"Invalid value for {key}: {vs}")

    def _c_file(self, path: str):
        if not path: self.renderer.err("Usage: /file <path>"); return
        content = self.file_reader.read_with_display(path.strip())
        self.session.messages.append(Msg(role="user", content=f"[File: {path}]\n```\n{content}\n```"))
        self.renderer.ok(f"Injected into context")

    def _c_edit(self, path: str):
        """Demande à l'IA de proposer une modification d'un fichier spécifique."""
        if not path: self.renderer.err("Usage: /edit <path>"); return
        p = Path(path.strip())
        if not p.exists() and not (Path.cwd() / path).exists():
            self.renderer.err(f"File not found: {path}"); return
        actual = str(p) if p.exists() else str(Path.cwd() / path)
        content = self.file_reader.read_with_display(actual)
        self.session.messages.append(Msg(role="user", content=f"[File: {actual}]\n```\n{content}\n```"))
        self._msg(f"Propose improvements and modifications for {path}. "
                  f"Format your code changes as: <<<EDIT:{actual}>>> ... new code ... <<<END>>>")

    def _c_write(self, path: str):
        if not path: self.renderer.err("Usage: /write <path>"); return
        if not self._last_resp: self.renderer.err("No AI response to write."); return
        self.renderer.ok(self.tools.write(path.strip(), self._last_resp))

    def _c_ls(self, pattern: str):
        files = self.tools.ls(pattern.strip() or "**/*")
        if HAS_RICH and self.console:
            t = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
            t.add_column(style="cyan")
            for f in files: t.add_row(f)
            self.console.print(Panel(t, title=f"[bold]ls[/bold]", border_style="bright_black"))
        else:
            for f in files: print(f"  {f}")

    def _c_exec(self, cmd: str):
        if not cmd: self.renderer.err("Usage: /exec <command>"); return
        self.renderer.info(f"$ {cmd}")
        self.renderer.box("exec", self.tools.run(cmd.strip()))

    def _c_sandbox(self, code: str):
        if not code: self.renderer.err("Usage: /sandbox <code>"); return
        if HAS_RICH and self.console:
            with self.console.status("[cyan]Executing sandbox…[/cyan]"): r = self.client.execute_code(code.strip())
        else: r = self.client.execute_code(code.strip())
        self.renderer.box("Sandbox", r.get("output") or r.get("stdout") or r.get("error") or str(r))

    def _c_image(self, prompt: str):
        if not prompt: self.renderer.err("Usage: /image <prompt>"); return
        if HAS_RICH and self.console:
            with self.console.status("[cyan]Generating image…[/cyan]"): r = self.client.generate_image(prompt.strip())
        else: r = self.client.generate_image(prompt.strip())
        self.renderer.box("CyVision", f"URL: {r.get('url') or r.get('image_url') or r.get('error') or str(r)}")

    def _c_memory(self, text: str):
        if not text: self.renderer.err("Usage: /memory <text>"); return
        if HAS_RICH and self.console:
            with self.console.status("[cyan]Adding to RAG…[/cyan]"): r = self.client.rag_add(text.strip())
        else: r = self.client.rag_add(text.strip())
        self.renderer.ok(f"Memory updated: {r}")

    def _c_plugins(self, args: str):
        parts = args.split(maxsplit=1); sub = parts[0].lower() if parts else "list"; arg2 = parts[1].strip() if len(parts)>1 else ""
        if sub in ("list", ""):
            if HAS_RICH and self.console:
                t = Table(title="CyCode Plugins", box=box.SIMPLE_HEAD)
                t.add_column("ID", style="bold cyan"); t.add_column("Name"); t.add_column("Status"); t.add_column("Description", style="dim")
                for pid, p in BUILTIN_PLUGINS.items():
                    st = "[green]● Active[/green]" if self.plugins.is_active(pid) else "[bright_black]○ Inactive[/bright_black]"
                    t.add_row(pid, f"{p['icon']} {p['name']}", Text.from_markup(st), p["description"])
                self.console.print(t)
                self.console.print(Text.from_markup("[bright_black]  /plugins enable <id>  ·  /plugins disable <id>[/bright_black]"))
        elif sub == "enable":
            if not arg2: self.renderer.err("Usage: /plugins enable <id>"); return
            p = BUILTIN_PLUGINS.get(arg2.lower())
            if not p: self.renderer.err(f"Unknown plugin: {arg2}"); return
            missing = [k for k in p["requires"] if not os.environ.get(k)]
            if missing:
                self.renderer.err(f"Missing env vars: {', '.join(missing)}")
                if arg2 == "google_search":
                    self.renderer.info("GOOGLE_API_KEY: https://console.cloud.google.com/apis/credentials")
                    self.renderer.info("GOOGLE_CSE_ID: https://programmablesearchengine.google.com/")
                elif arg2 == "github":
                    self.renderer.info("GITHUB_TOKEN: https://github.com/settings/tokens")
                return
            self.plugins.enable(arg2.lower()); self._system_ctx = self._build_system()
            self.renderer.ok(f"Plugin enabled: {p['icon']} {p['name']}")
        elif sub == "disable":
            if not arg2: self.renderer.err("Usage: /plugins disable <id>"); return
            self.plugins.disable(arg2.lower()); self._system_ctx = self._build_system()
            self.renderer.ok(f"Plugin disabled: {arg2}")
        elif sub == "search":
            if not self.plugins.is_active("google_search"):
                self.renderer.err("Run: /plugins enable google_search"); return
            if HAS_RICH and self.console:
                with self.console.status(f"[cyan]Searching…[/cyan]"): result = self.plugins.run_google_search(arg2)
            else: result = self.plugins.run_google_search(arg2)
            self.renderer.box("Google Search", result)
        elif sub == "github":
            if not self.plugins.is_active("github"):
                self.renderer.err("Run: /plugins enable github"); return
            if HAS_RICH and self.console:
                with self.console.status("[cyan]GitHub…[/cyan]"): result = self.plugins.run_github(arg2)
            else: result = self.plugins.run_github(arg2)
            self.renderer.box("GitHub", result)

    def _c_skills(self, args: str):
        parts = args.split(maxsplit=2); sub = parts[0].lower() if parts else "list"
        if sub in ("list", ""):
            if HAS_RICH and self.console:
                t = Table(title="CyCode Skills", box=box.SIMPLE_HEAD)
                t.add_column("ID", style="bold cyan"); t.add_column("Name"); t.add_column("Description", style="dim")
                for sid, s in BUILTIN_SKILLS.items():
                    t.add_row(sid, s["name"], s.get("description", ""))
                self.console.print(t)
        elif sub == "use":
            if len(parts) < 2: self.renderer.err("Usage: /skills use <id> [prompt]"); return
            skill = BUILTIN_SKILLS.get(parts[1].lower())
            if not skill: self.renderer.err(f"Unknown skill: {parts[1]}"); return
            user_prompt = parts[2].strip() if len(parts) > 2 else ""
            if not user_prompt:
                for m in reversed(self.session.messages):
                    if m.role == "user" and m.content.startswith("[File:"): user_prompt = m.content; break
                if not user_prompt: self.renderer.err("No prompt and no /file injected."); return
            self.renderer.info(f"Running skill: {skill['name']}")
            self._msg(skill["prompt_prefix"] + user_prompt)

    def _c_history(self):
        if not self.session.messages: self.renderer.info("No messages."); return
        for m in self.session.messages:
            style = "bold cyan" if m.role == "user" else "bold green"
            prefix = "You" if m.role == "user" else "CygnisAI"
            preview = m.content[:400] + ("…" if len(m.content)>400 else "")
            if HAS_RICH and self.console:
                self.console.print(f"[{style}]{prefix}[/{style}]  {preview}")
                self.console.print(Rule(style="bright_black"))
            else: print(f"[{prefix}]  {preview}\n---")

    def _c_tokens(self):
        self.renderer.info(
            f"~{self.session.token_count} tokens  ·  "
            f"{self.session.real_user_count} exchanges  ·  "
            f"{len(self.session.messages)} total messages"
        )

    def _c_cd(self, path: str):
        if not path: self.renderer.info(f"cwd: {Path.cwd()}"); return
        try:
            os.chdir(path.strip()); self.config.workspace = str(Path.cwd())
            self._system_ctx = self._build_system(); self.renderer.ok(f"→ {Path.cwd()}")
        except Exception as e: self.renderer.err(str(e))

    def _c_login(self):
        if HAS_PT:
            try: key = pt_prompt(HTML("<ansicyan><b>  API Key: </b></ansicyan>"), is_password=True).strip()
            except: key = ""
        else: key = input("API Key: ").strip()
        if key:
            self.config.api_key = key; self.config.save()
            self.client = CygnisClient(self.config)
            self.renderer.ok("Authenticated."); self._probe()
        else: self.renderer.info("Cancelled.")

    def _c_exit(self):
        self.renderer.info("Saving session and exiting…")
        self.session.save(); sys.exit(0)


# ─── Entry point ──────────────────────────────────────────────────────────────

def launch_repl(api_key: Optional[str] = None):
    config = Config.load()
    if api_key: config.api_key = api_key
    REPL(config).run()

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--api-key", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--no-stream", action="store_true")
    a = p.parse_args()
    cfg = Config.load()
    if a.api_key:   cfg.api_key = a.api_key
    if a.model:     cfg.default_model = a.model
    if a.no_stream: cfg.stream = False
    REPL(cfg).run()
