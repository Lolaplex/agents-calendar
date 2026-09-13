"""
Auto-configure MCP servers across installed IDEs.
Supports Cursor, Antigravity IDE, Claude Desktop, Zed (context_servers), Codex, VS Code (Copilot/Cline/Roo-Code), Windsurf.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


def mcp_entry() -> Dict[str, Any]:
    """Returns standard MCP server descriptor for agents-calendar."""
    return {
        "command": sys.executable if sys.executable else "python",
        "args": ["-m", "agents_calendar", "serve"],
    }


def known_host_mcp_paths() -> List[Path]:
    """Returns a list of all potential MCP configuration file paths on the host system."""
    home = Path.home()
    paths: List[Path] = [
        home / ".cursor" / "mcp.json",
        home / ".agents" / "mcp.json",
        home / ".gemini" / "antigravity-ide" / "mcp_config.json",
        home / ".gemini" / "config" / "mcp_config.json",
        home / ".gemini" / "config" / "mcp.json",
        home / ".codex" / "mcp.json",
        home / ".codex" / "config.json",
    ]

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
        paths.extend([
            Path(appdata) / "Claude" / "claude_desktop_config.json",
            Path(appdata) / "Cursor" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json",
            Path(appdata) / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json",
            Path(appdata) / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
            Path(appdata) / "Windsurf" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json",
        ])
    elif sys.platform == "darwin":
        app_support = home / "Library" / "Application Support"
        paths.extend([
            app_support / "Claude" / "claude_desktop_config.json",
            app_support / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json",
            app_support / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
        ])
    else:
        config = home / ".config"
        paths.extend([
            config / "Claude" / "claude_desktop_config.json",
            config / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json",
            config / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
        ])

    return paths


def known_zed_paths() -> List[Path]:
    """Returns potential Zed settings.json paths."""
    home = Path.home()
    paths: List[Path] = [
        home / ".config" / "zed" / "settings.json",
    ]
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
        paths.append(Path(appdata) / "Zed" / "settings.json")
    elif sys.platform == "darwin":
        paths.append(home / "Library" / "Application Support" / "Zed" / "settings.json")
    return paths


def _strip_jsonc(text: str) -> str:
    """Strip single-line and multi-line comments from JSONC text."""
    out: List[str] = []
    i = 0
    n = len(text)
    in_str = False
    escape = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_str:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _merge_mcp_server_into_file(path: Path) -> str:
    """Safely insert or update agents-calendar in an MCP settings file."""
    if not path.parent.exists():
        return ""
    if path.exists():
        raw = path.read_text(encoding="utf-8", errors="replace")
        try:
            clean = _strip_jsonc(raw)
            data = json.loads(clean) if clean.strip() else {}
        except json.JSONDecodeError as e:
            return f"FAIL {path}: invalid JSON ({e})"
        if not isinstance(data, dict):
            return f"FAIL {path}: root is not an object"
    else:
        data = {}

    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        return f"FAIL {path}: mcpServers is not an object"

    servers["agents-calendar"] = mcp_entry()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"OK {path}"


def _merge_zed_settings(path: Path) -> str:
    """Safely insert or update agents-calendar in Zed context_servers."""
    if not path.parent.exists():
        return ""
    if path.exists():
        raw = path.read_text(encoding="utf-8", errors="replace")
        try:
            clean = _strip_jsonc(raw)
            data = json.loads(clean) if clean.strip() else {}
        except json.JSONDecodeError as e:
            return f"FAIL {path}: invalid JSON ({e})"
        if not isinstance(data, dict):
            return f"FAIL {path}: root is not an object"
    else:
        data = {}

    context_servers = data.setdefault("context_servers", {})
    if isinstance(context_servers, list):
        if "agents-calendar" not in context_servers:
            context_servers.append("agents-calendar")
    elif isinstance(context_servers, dict):
        context_servers["agents-calendar"] = mcp_entry()

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"OK {path} (Zed context_servers)"


def merge_agent_mcp() -> List[str]:
    """Insert/update the agents-calendar server in all installed host MCP configs and Zed."""
    results: List[str] = []
    seen: set[str] = set()

    cursor_p = Path.home() / ".cursor" / "mcp.json"
    cursor_p.parent.mkdir(parents=True, exist_ok=True)

    for target in known_host_mcp_paths():
        key = str(target.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        if target.parent.exists():
            res = _merge_mcp_server_into_file(target)
            if res:
                results.append(res)

    for zed_target in known_zed_paths():
        key = str(zed_target.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        if zed_target.parent.exists():
            res = _merge_zed_settings(zed_target)
            if res:
                results.append(res)

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync agents-calendar MCP server config.")
    parser.add_argument("--init", action="store_true", help="Auto-configure MCP server in all installed IDEs")
    parser.parse_args(argv)

    mcp_results = merge_agent_mcp()
    print(f"Configured MCP servers across {len(mcp_results)} host configs:")
    for r in mcp_results:
        print(f" * {r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
