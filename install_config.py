#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
esafe-fs MCP Server 一键配置生成脚本
=====================================

自动生成各 AI 工具的 MCP 配置，支持自动写入或打印供手动粘贴。

用法
----
    python install_config.py                  # 打印所有工具的配置
    python install_config.py --install workbuddy   # 写入 WorkBuddy 配置
    python install_config.py --install cursor      # 写入 Cursor 配置
    python install_config.py --install claude      # 写入 Claude Code 配置
    python install_config.py --install trae        # 写入 Trae 配置
    python install_config.py --install vscode      # 写入 VS Code 配置
    python install_config.py --install-all         # 写入所有工具配置
    python install_config.py --encoding utf-8      # 指定默认编码（默认 gbk）

支持的工具
----------
WorkBuddy / Cursor / Claude Code / Trae / VS Code Copilot
"""

import json
import os
import sys
from pathlib import Path

# ─── 路径自动检测 ──────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
SERVER_PATH = SCRIPT_DIR / "esafe_mcp_server.py"

# 检测可用 Python（优先 managed，回退 system）
PYTHON_CANDIDATES = [
    Path.home() / ".workbuddy" / "binaries" / "python" / "versions" / "3.13.12" / "python.exe",
    Path.home() / ".workbuddy" / "binaries" / "python" / "versions" / "3.14.3" / "python.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python313" / "python.exe",
    Path.home() / "miniconda3" / "python.exe",
    Path.home() / "AppData" / "Local" / "miniconda3" / "python.exe",
]

def find_python() -> str:
    """找到第一个可用的 Python 路径。"""
    for p in PYTHON_CANDIDATES:
        if p.exists():
            return str(p)
    # 最后回退到当前 python
    return sys.executable


# ─── 各工具配置路径 ─────────────────────────────────────────────────────────

HOME = Path.home()

TOOL_CONFIGS = {
    "workbuddy": {
        "name": "WorkBuddy",
        "path": HOME / ".workbuddy" / "mcp.json",
        "desc": "腾讯 WorkBuddy（全局配置）",
    },
    "cursor": {
        "name": "Cursor",
        "path": HOME / ".cursor" / "mcp.json",
        "desc": "Cursor IDE（全局配置）",
    },
    "claude": {
        "name": "Claude Code",
        "path": HOME / ".claude.json",
        "desc": "Anthropic Claude Code（全局配置，合并 mcpServers 字段）",
    },
    "trae": {
        "name": "Trae",
        "path": HOME / ".trae" / "mcp.json",
        "desc": "Trae IDE（全局配置）",
    },
    "vscode": {
        "name": "VS Code Copilot",
        "path": HOME / ".vscode" / "mcp.json",
        "desc": "VS Code Copilot Chat（全局配置）",
    },
}


def build_server_config(encoding: str = "gbk") -> dict:
    """生成 esafe-fs 的 MCP server 配置片段。"""
    return {
        "command": find_python(),
        "args": [str(SERVER_PATH)],
        "env": {"ESAFE_FS_ENCODING": encoding},
    }


def read_existing_json(path: Path) -> dict:
    """读取现有 JSON 配置，不存在返回空 dict。"""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_json(path: Path, data: dict) -> None:
    """写入 JSON 配置，自动创建目录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def install_to_tool(tool_key: str, encoding: str, dry_run: bool = False) -> str:
    """
    将 esafe-fs 配置写入指定工具的配置文件（合并模式，不覆盖其他 server）。

    Returns: 操作结果描述
    """
    cfg = TOOL_CONFIGS[tool_key]
    config_path = cfg["path"]
    server_cfg = build_server_config(encoding)

    existing = read_existing_json(config_path)
    servers = existing.get("mcpServers", {})

    if "esafe-fs" in servers:
        status = "更新"
    else:
        status = "新增"

    servers["esafe-fs"] = server_cfg
    existing["mcpServers"] = servers

    if dry_run:
        return f"[预览] {cfg['name']}: {config_path}（{status}）"

    write_json(config_path, existing)
    return f"[{status}] {cfg['name']}: {config_path}"


def print_config(tool_key: str, encoding: str) -> None:
    """打印指定工具的配置片段。"""
    cfg = TOOL_CONFIGS[tool_key]
    server_cfg = build_server_config(encoding)
    full = {"mcpServers": {"esafe-fs": server_cfg}}

    print(f"\n{'=' * 60}")
    print(f"{cfg['name']} — {cfg['desc']}")
    print(f"配置文件路径: {cfg['path']}")
    print(f"{'=' * 60}")
    print(json.dumps(full, ensure_ascii=False, indent=2))


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="esafe-fs MCP Server 一键配置生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python install_config.py                       # 打印所有工具配置
  python install_config.py --install workbuddy   # 写入 WorkBuddy
  python install_config.py --install-all         # 写入所有工具
  python install_config.py --encoding utf-8      # 用 utf-8 编码
""",
    )
    parser.add_argument(
        "--install",
        choices=list(TOOL_CONFIGS.keys()),
        help="写入指定工具的配置文件",
    )
    parser.add_argument(
        "--install-all",
        action="store_true",
        help="写入所有工具的配置文件",
    )
    parser.add_argument(
        "--encoding",
        default="gbk",
        help="默认文件编码（默认 gbk，适合项目源文件；其他场景可设 utf-8）",
    )
    args = parser.parse_args()

    # 检查 server 文件
    if not SERVER_PATH.exists():
        print(f"[ERROR] 找不到 MCP Server: {SERVER_PATH}", file=sys.stderr)
        return 1

    python_path = find_python()
    print(f"Python: {python_path}")
    print(f"Server: {SERVER_PATH}")
    print(f"编码:   {args.encoding}")

    # 写入模式
    if args.install_all:
        print(f"\n写入所有工具配置...")
        for key in TOOL_CONFIGS:
            result = install_to_tool(key, args.encoding)
            print(f"  {result}")
        print(f"\n[完成] 所有工具配置已写入。")
        print(f"[提示] 重启对应 AI 工具后生效。WorkBuddy 需在连接器管理页点'信任'。")
        return 0

    if args.install:
        result = install_to_tool(args.install, args.encoding)
        print(f"\n{result}")
        cfg = TOOL_CONFIGS[args.install]
        print(f"\n[提示] 重启 {cfg['name']} 后生效。")
        if args.install == "workbuddy":
            print(f"[提示] WorkBuddy 需在连接器管理页点击 '信任' 启用此 MCP。")
        return 0

    # 打印模式（默认）
    print(f"\n以下为各工具的 MCP 配置（可手动复制粘贴到对应配置文件）：")
    for key in TOOL_CONFIGS:
        print_config(key, args.encoding)

    print(f"\n{'=' * 60}")
    print(f"自动写入：python install_config.py --install <工具名>")
    print(f"全部写入：python install_config.py --install-all")
    print(f"可用工具: {', '.join(TOOL_CONFIGS.keys())}")
    print(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
