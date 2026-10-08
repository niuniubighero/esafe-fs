#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
esafe-fs MCP Server
===================

E-Safe 透明加密环境下的文件读写 MCP Server。

功能
----
在 E-Safe (EsafeNet Cobra DocGuard) 透明加密环境下，为 AI 工具提供
标准化的文件读写能力。当 Python 被 E-Safe 信任时，读写透明（驱动自动
加解密）；当 Python 不受信任时，读取走 ``cmd /c type`` 桥接解密。

提供的工具 (tools)
-------------------
- read_file        读取文件明文（自动处理加密/编码）
- write_file       写入文件（驱动自动加密）
- get_file_info    获取文件信息（大小/行数/编码/加密状态）
- read_file_lines  读取指定行范围
- scan_directory   扫描目录下文件（可按扩展名过滤）
- list_directory   列出目录内容

适用 AI 工具
------------
任何支持 MCP 协议的客户端：WorkBuddy / Cursor / Claude Code /
Trae / VS Code Copilot / MIMO Code / Open Code 等。

传输方式：stdio（默认，所有 MCP 客户端通用）

环境变量
--------
ESAFE_FS_ENCODING  默认文本编码（默认 utf-8）。
                   项目源文件为 GBK，可在 mcp.json 的 env 里设为 gbk。

依赖
----
- Python 3.10+
- mcp >= 1.0, < 2.0  (FastMCP)

作者：WorkBuddy
版本：1.0.0
"""

from __future__ import annotations

import fnmatch
import io
import json
import os
import shutil
import subprocess
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

__version__ = "1.0.0"

# ─── 常量 ──────────────────────────────────────────────────────────────────

# E-Safe 加密文件魔术字
ESAFE_MAGIC = b"E-SafeNetLOCK"

# 默认编码回退链
_ENCODING_FALLBACK = ("utf-8", "gbk", "gb18030")

# cmd /c type 超时（秒）
_TYPE_TIMEOUT = 60

# 二进制头部探测字节数
_HEADER_PROBE = 64

# 默认写入编码（可通过环境变量 ESAFE_FS_ENCODING 覆盖）
_DEFAULT_WRITE_ENCODING = os.environ.get("ESAFE_FS_ENCODING", "utf-8")


# ─── 内部工具函数 ───────────────────────────────────────────────────────────


def _is_encrypted(filepath: str) -> bool:
    """
    检测文件是否为 E-Safe 加密格式。

    注意：当 Python 在 E-Safe 信任列表中时，open() 读到的是解密后的明文，
    此函数会返回 False（检测失效）。这不影响读取功能，但无法准确判断
    磁盘上的真实加密状态。
    """
    try:
        with open(filepath, "rb") as f:
            header = f.read(_HEADER_PROBE)
        return ESAFE_MAGIC in header
    except Exception:
        return False


def _check_cmd_available() -> bool:
    """检测 cmd.exe 是否可用（用于加密文件桥接读取）。"""
    return sys.platform == "win32" and bool(shutil.which("cmd"))


def _decode_bytes(raw: bytes, encoding: Optional[str]) -> str:
    """按编码回退链解码字节流。"""
    if encoding:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError as e:
            raise ValueError(f"使用编码 '{encoding}' 解码失败: {e}") from e
    for enc in _ENCODING_FALLBACK:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _read_bytes_direct(filepath: str) -> bytes:
    """直接读取文件原始字节。"""
    with open(filepath, "rb") as f:
        return f.read()


def _read_bytes_via_cmd(filepath: str) -> bytes:
    """通过 cmd /c type 读取加密文件的明文字节（Python 不受信任时的桥接）。"""
    result = subprocess.run(
        ["cmd", "/c", "type", filepath],
        capture_output=True,
        encoding=None,
        timeout=_TYPE_TIMEOUT,
    )
    if result.returncode != 0 or not result.stdout:
        stderr = ""
        if result.stderr:
            try:
                stderr = result.stderr.decode("gbk", errors="replace").strip()
            except Exception:
                stderr = str(result.stderr)
        raise IOError(f"cmd /c type 失败 (code={result.returncode}): {stderr}")
    return result.stdout


def _read_file_content(filepath: str, encoding: Optional[str]) -> str:
    """
    读取文件明文内容（核心逻辑）。

    策略：
    1. Python 受信任时，直接 open() 读到明文
    2. 检测到 E-Safe 加密头时，走 cmd /c type 桥接
    3. 按编码回退链解码
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    if _is_encrypted(filepath):
        # Python 不受信任，走 cmd 桥接
        raw = _read_bytes_via_cmd(filepath)
    else:
        # 明文 或 Python 受信任（驱动透明解密）
        raw = _read_bytes_direct(filepath)

    return _decode_bytes(raw, encoding)


def _write_file_content(filepath: str, content: str, encoding: Optional[str]) -> None:
    """
    写入文件内容。

    当 Python 在 E-Safe 信任列表中时，写入会被驱动自动加密，磁盘上存密文。
    当 Python 不受信任时，写入的是明文，可能破坏加密文件——此时应通过
    受信任编辑器修改。
    """
    enc = encoding or _DEFAULT_WRITE_ENCODING
    data = content.encode(enc)
    # 确保目录存在
    dirpath = os.path.dirname(filepath)
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(data)


def _detect_encoding(filepath: str) -> str:
    """探测文件实际编码。"""
    try:
        with open(filepath, "rb") as f:
            raw = f.read()
    except Exception:
        return "unknown"
    for enc in _ENCODING_FALLBACK:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "unknown"


def _format_file_info(filepath: str) -> dict:
    """收集文件信息。"""
    stat = os.stat(filepath)
    encrypted = _is_encrypted(filepath)
    encoding = _detect_encoding(filepath)
    line_count = 0
    try:
        content = _read_file_content(filepath, None)
        line_count = len(content.splitlines())
    except Exception:
        pass
    return {
        "path": filepath,
        "size_bytes": stat.st_size,
        "line_count": line_count,
        "encoding": encoding,
        "esafe_encrypted": encrypted,
        "note": (
            "Python 受 E-Safe 信任时，encrypted 字段可能为 False"
            "（读到的是解密后的明文，看不到密文头）"
        ),
    }


# ─── MCP 工具定义 ──────────────────────────────────────────────────────────

mcp = FastMCP("esafe-fs")


@mcp.tool()
def read_file(path: str, encoding: str = "") -> str:
    """读取文件的明文内容。

    自动处理 E-Safe 透明加密和文本编码。当 Python 受 E-Safe 信任时直接读取
    （驱动自动解密）；检测到加密头时走 cmd /c type 桥接。

    Args:
        path: 文件绝对路径或相对路径
        encoding: 指定编码（如 utf-8 / gbk）；留空则自动回退 utf-8→gbk→gb18030

    Returns:
        文件明文内容字符串

    适用场景：读取 .c / .h / .py / .md 等文本源文件。
    """
    try:
        enc = encoding if encoding else None
        return _read_file_content(path, enc)
    except FileNotFoundError as e:
        return f"[ERROR] {e}"
    except Exception as e:
        return f"[ERROR] 读取失败: {e}"


@mcp.tool()
def write_file(path: str, content: str, encoding: str = "") -> str:
    """写入文件内容（覆盖写入）。

    在 E-Safe 信任环境下，写入会被驱动自动加密，磁盘上存密文，安全可靠。
    默认编码由环境变量 ESAFE_FS_ENCODING 决定（默认 utf-8）。
    项目源文件为 GBK，请在 mcp.json 的 env 里设 ESAAFE_FS_ENCODING=gbk，
    或在此处传 encoding='gbk'。

    Args:
        path: 文件路径
        content: 要写入的内容
        encoding: 指定编码；留空用默认（ESAFE_FS_ENCODING 或 utf-8）

    Returns:
        写入结果信息
    """
    try:
        enc = encoding if encoding else None
        _write_file_content(path, content, enc)
        used = enc or _DEFAULT_WRITE_ENCODING
        size = len(content.encode(used))
        return f"[OK] 已写入 {path}（{size} 字节，编码 {used}）"
    except Exception as e:
        return f"[ERROR] 写入失败: {e}"


@mcp.tool()
def get_file_info(path: str) -> str:
    """获取文件信息：大小、行数、编码、加密状态。

    Args:
        path: 文件路径

    Returns:
        JSON 格式的文件信息
    """
    try:
        if not os.path.isfile(path):
            return f"[ERROR] 文件不存在: {path}"
        info = _format_file_info(path)
        return json.dumps(info, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"[ERROR] {e}"


@mcp.tool()
def read_file_lines(
    path: str, start: int = 1, end: int = 50, encoding: str = ""
) -> str:
    """读取文件的指定行范围（带行号）。

    适合查看大文件的局部内容，避免一次性返回过多文本。

    Args:
        path: 文件路径
        start: 起始行号（从 1 开始）
        end: 结束行号（含）
        encoding: 指定编码；留空自动回退

    Returns:
        带行号的文本内容
    """
    try:
        enc = encoding if encoding else None
        content = _read_file_content(path, enc)
        lines = content.splitlines()
        start = max(1, start)
        end = min(len(lines), end)
        if start > end:
            return f"[ERROR] 行范围无效: {start}-{end}（文件共 {len(lines)} 行）"
        result = []
        for i in range(start - 1, end):
            result.append(f"{i + 1:5d}: {lines[i]}")
        result.append(f"\n[显示 {start}-{end} 行，文件共 {len(lines)} 行]")
        return "\n".join(result)
    except Exception as e:
        return f"[ERROR] {e}"


@mcp.tool()
def scan_directory(
    path: str, pattern: str = "*.c;*.h", recursive: bool = True
) -> str:
    """扫描目录下匹配的文件列表。

    Args:
        path: 目录路径
        pattern: 文件名匹配模式，多个用分号分隔（如 *.c;*.h;*.py）
        recursive: 是否递归子目录

    Returns:
        JSON 格式的文件列表，含每个文件的路径和大小
    """
    try:
        if not os.path.isdir(path):
            return f"[ERROR] 目录不存在: {path}"
        patterns = [p.strip() for p in pattern.split(";") if p.strip()]
        results = []
        if recursive:
            walker = os.walk(path)
        else:
            walker = [(path, [], os.listdir(path))]
        for root, _dirs, files in walker:
            for fname in files:
                if not any(fnmatch.fnmatch(fname, p) for p in patterns):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    size = os.path.getsize(fpath)
                except Exception:
                    size = -1
                results.append({"path": fpath, "size": size})
        return json.dumps(
            {"directory": path, "count": len(results), "files": results},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return f"[ERROR] {e}"


@mcp.tool()
def list_directory(path: str) -> str:
    """列出目录内容（文件和子目录）。

    Args:
        path: 目录路径

    Returns:
        JSON 格式的目录列表
    """
    try:
        if not os.path.isdir(path):
            return f"[ERROR] 目录不存在: {path}"
        entries = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            entry_type = "dir" if os.path.isdir(full) else "file"
            size = 0
            if entry_type == "file":
                try:
                    size = os.path.getsize(full)
                except Exception:
                    pass
            entries.append({"name": name, "type": entry_type, "size": size})
        return json.dumps(
            {"directory": path, "count": len(entries), "entries": entries},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return f"[ERROR] {e}"


# ─── 启动 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
