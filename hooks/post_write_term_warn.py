#!/usr/bin/env python3
"""lhg-book-translate 硬门②：译文文件写入后，若术语表长期未更新则提醒。

触发：PostToolUse / Write|Edit。只关心 translated/ 下的译文文件，
其他文件 0 开销直接放行。

逻辑：译文文件写入后，检查项目目录下 glossary.md 的修改时间；
若术语表比本次写入的译文文件旧超过 STALE_DAYS 天，追加一条
additionalContext 提醒复核术语表（翻译进行中新增的术语可能没进表）。

逃生方式（按推荐度排序）：
  1. 按提醒复核术语表，把新增术语登记进去（推荐）。
  2. 紧急情况：LHG_BOOKTRANSLATE_HOOKS_OFF=1（单次豁免本次 hook）。
  3. /plugin disable lhg-book-translate（整个插件停用，hooks 不再触发）。

设计原则：任何内部出错（找不到文件、解析失败等）都 fail-open 静默放行，
绝不因提醒脚本自身故障打断翻译；本 hook 只提醒、不拦截。
零第三方依赖。
"""

import json
import os
import sys
import time

STALE_DAYS = 7
STALE_SECS = STALE_DAYS * 86400


def main() -> int:
    # 逃生开关
    if os.environ.get("LHG_BOOKTRANSLATE_HOOKS_OFF") == "1":
        return 0

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # 输入解析失败：fail-open

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "") or ""

    # 只关心译文文件
    norm = file_path.replace("\\", "/")
    if "/translated/" not in norm:
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        ch_mtime = os.path.getmtime(file_path)
    except OSError:
        return 0  # 译文文件不可读：fail-open

    glossary = os.path.join(project_dir, "glossary.md")
    try:
        age = ch_mtime - os.path.getmtime(glossary)
        label = "glossary.md（已 %d 天未更新）" % int(age // 86400)
        is_stale = age > STALE_SECS
    except OSError:
        label = "glossary.md（缺失）"
        is_stale = True

    if not is_stale:
        return 0

    msg = (
        "lhg-book-translate 提醒：译文文件已写入，但%s。"
        "翻译进行中新增的术语可能还没登记进表，建议顺手复核；"
        "确认无新增术语可忽略本提醒。"
        % label
    )
    sys.stdout.write(json.dumps({"additionalContext": msg}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
