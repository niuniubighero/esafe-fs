# esafe-fs MCP Server

> **关于路径脱敏**：本文档中的 `<USERNAME>`、`<REPO_DIR>` 均为占位符，分别对应本机的
> Windows 用户名和本仓库的克隆目录，实际使用时自行替换。

E-Safe 透明加密环境下的文件读写 MCP Server。让任何支持 MCP 协议的 AI 工具
（WorkBuddy / Cursor / Claude Code / Trae / VS Code Copilot / MIMO Code / Open Code）
都能正确读写 E-Safe 加密的源文件。

## 为什么需要它

公司使用 E-Safe (EsafeNet Cobra DocGuard) 透明加密源文件。当 Python 在 E-Safe
信任列表中时，`open()` 读写会透明加解密；不在信任列表时，直接读拿到密文乱码。
本 Server 封装了完整的读取（含 `cmd /c type` 桥接）和写入逻辑，AI 只管调用工具，
不用关心加密/编码/二进制检测等细节。

## 提供的工具 (tools)

| 工具 | 功能 |
|---|---|
| `read_file` | 读取文件明文（自动处理加密/编码） |
| `write_file` | 写入文件（E-Safe 信任环境下驱动自动加密） |
| `get_file_info` | 文件信息（大小/行数/编码/加密状态） |
| `read_file_lines` | 读取指定行范围（带行号，适合看大文件局部） |
| `scan_directory` | 扫描目录下匹配文件 |
| `list_directory` | 列出目录内容 |

## 快速配置

### 一键写入（推荐）

```cmd
cd "<REPO_DIR>"                                # 即本仓库的克隆目录
python install_config.py --install workbuddy    # 写入 WorkBuddy
python install_config.py --install cursor       # 写入 Cursor
python install_config.py --install-all          # 写入所有工具
```

写入后重启对应 AI 工具即可生效。

### 手动配置

在 AI 工具的 MCP 配置文件中加入：

```json
{
  "mcpServers": {
    "esafe-fs": {
      "command": "C:\\Users\\<USERNAME>\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe",
      "args": ["<REPO_DIR>\\esafe_mcp_server.py"],
      "env": { "ESAFE_FS_ENCODING": "gbk" }
    }
  }
}
```

## 各工具配置文件位置

| AI 工具 | 配置文件路径 |
|---|---|
| WorkBuddy | `~/.workbuddy/mcp.json` |
| Cursor | `~/.cursor/mcp.json` |
| Claude Code | `~/.claude.json`（合并 mcpServers 字段） |
| Trae | `~/.trae/mcp.json` |
| VS Code Copilot | `~/.vscode/mcp.json` |

> 配置文件不存在时，`install_config.py` 会自动创建。已存在的配置会**合并**，
> 不会覆盖其他 MCP Server。

## 编码设置

- **默认编码**：由环境变量 `ESAFE_FS_ENCODING` 控制，默认 `gbk`（项目源文件）
- 切换为 UTF-8：在 mcp.json 的 `env` 里改 `"ESAFE_FS_ENCODING": "utf-8"`
- 或调用工具时传 `encoding` 参数覆盖

## 使用示例（AI 调用）

AI 工具连接此 MCP 后，可直接调用工具：

```
AI: read_file("E:\\projects\\MyProject\\Driver\\Buzz\\DrvBUZZ.c")
→  返回文件明文内容

AI: get_file_info("...\\DrvBUZZ.c")
→  {"size_bytes": 2947, "line_count": 99, "encoding": "utf-8", ...}

AI: write_file("...\\DrvBUZZ.c", "修改后的内容", "gbk")
→  [OK] 已写入（驱动自动加密）

AI: scan_directory("...\\platform\\Driver", "*.c;*.h")
→  返回匹配文件列表
```

## 注意事项

1. **写入安全**：当 Python 在 E-Safe 信任列表中时，`write_file` 写入会被驱动
   自动加密，安全可靠。当 Python 不受信任时，写入的是明文，会破坏加密文件——
   此时请通过受信任编辑器修改。

2. **WorkBuddy 启用**：写入 mcp.json 后，WorkBuddy 不会自动激活新 MCP。
   需要在右上角连接器管理页点击「信任」启用。

3. **编码一致性**：项目源文件为 GBK，写入时务必保持 GBK 编码，否则会产生
   Git 差异。默认已设为 `gbk`。

4. **Python 路径**：配置中的 `command` 指向装有 mcp 包的 Python。当前为
   `C:\Users\<USERNAME>\.workbuddy\binaries\python\versions\3.13.12\python.exe`。
   如换机器需重新运行 `install_config.py` 检测路径。

## 文件结构

```
esafe-fs/                 # 即 <REPO_DIR>
├── esafe_mcp_server.py   # MCP Server 主体（FastMCP + 6 个工具）
├── install_config.py     # 一键配置生成脚本
├── requirements.txt      # 依赖清单
└── README.md             # 本文档
```

## 依赖

- Python 3.10+
- mcp >= 1.0, < 2.0 (FastMCP)

安装依赖：
```cmd
"C:\Users\<USERNAME>\.workbuddy\binaries\python\versions\3.13.12\python.exe" -m pip install "mcp<2"
```

## 版本

v1.0.0 — 2026-08-14 初始版本
