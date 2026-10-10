#!/usr/bin/env python3
"""lhg-book-translate 确定性翻译一致性审计：17 条规则，零第三方依赖。

扫描翻译项目目录（约定文件：glossary.md / source/*.md /
translated/*.md / translation-log.md），检查术语一致性、未译残留、
中英文标点、章节结构、翻译腔。

用法：
    python3 translation_audit.py --target <项目目录> [--format json|text]
                                 [--fail-on blocker|warning|nit]

有 >= fail-on 级别发现时以 exit code 2 退出（供 hooks 与 CI 使用）。

规则文案均为本项目原创（思路受 deusyu/translate-book 的"术语表一致性"
高层思想启发，未复制任何第三方原文）；密度阈值为通用经验启发值，
详见 lhg-bt-audit skill 第 8 节调参指南。
"""

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"
TOOL = "lhg-book-translate/translation-audit"

SKIP_DIRS = {".git", "__pycache__", "docs", "node_modules"}

CJK = r"\u4e00-\u9fff"
CJK_RE = re.compile(r"[%s]" % CJK)
FENCE_RE = re.compile(r"^\s*```")
HEADING_RE = re.compile(r"^#{1,6}\s")
NUM_PREFIX_RE = re.compile(r"^(\d+)")
# 连续英文单词片段（2 个词以上）
EN_RUN_RE = re.compile(
    r"(?<![A-Za-z])[A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*){1,}(?![A-Za-z])"
)
# 全大写缩写（API/GPU/LLM）
ACRONYM_RE = re.compile(r"(?<![A-Z0-9])[A-Z][A-Z0-9]{1,}(?![A-Z0-9])")
# 中文句末误用英文句号（排除小数点）
EN_PERIOD_RE = re.compile(r"[%s]\.(?!\d)" % CJK)
# 中文旁的半角括号
HALF_PAREN_RE = re.compile(r"[%s]\(|\)[%s]" % (CJK, CJK))
DEGREE_ADV = ("非常", "十分", "极其", "特别")

# 翻译腔密度阈值（启发值，见 lhg-bt-audit 第 8 节）
DE_PER_100_WARN = 7.0      # "的"字每百汉字
JINXING_PER_1000_WARN = 5  # "进行"每千字
BEI_PER_1000_WARN = 8       # "被"每千字
ADV_PER_1000_NIT = 6        # 程度副词每千字
LONG_SENT_CJK = 80          # 超长句阈值（汉字数）


class Finding:
    __slots__ = ("rule_id", "severity", "category", "title", "file",
                 "line", "snippet", "detail")

    def __init__(self, rule_id, severity, category, title, file, line,
                 snippet, detail):
        self.rule_id = rule_id
        self.severity = severity
        self.category = category
        self.title = title
        self.file = file
        self.line = line
        self.snippet = snippet
        self.detail = detail

    def to_dict(self):
        return {
            "rule_id": self.rule_id, "severity": self.severity,
            "category": self.category, "title": self.title,
            "file": self.file, "line": self.line,
            "snippet": self.snippet, "detail": self.detail,
        }


RULES = []
_RULE_BY_ID = {}


def rule(rule_id, severity, category, title, detail):
    def deco(fn):
        r = {"id": rule_id, "severity": severity, "category": category,
             "title": title, "detail": detail}
        _RULE_BY_ID[rule_id] = r
        r["check"] = fn
        RULES.append(r)
        return fn
    return deco


class Project:
    """翻译项目：术语表 + 原文/译文章节。"""

    def __init__(self, target):
        self.target = target
        self.terms = []          # (source, locked, [banned], glossary_lineno)
        self.glossary_path = None
        self.sources = {}        # stem -> {path, lines, headings}
        self.translated = {}     # stem -> {path, lines, headings}

    def load(self):
        g = os.path.join(self.target, "glossary.md")
        if os.path.isfile(g):
            self.glossary_path = g
            self.terms = parse_glossary(g)
        for sub, store in (("source", self.sources),
                           ("translated", self.translated)):
            d = os.path.join(self.target, sub)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(".md"):
                    continue
                stem = fn[:-3]
                path = os.path.join(d, fn)
                lines = read_text_lines(path)
                store[stem] = {
                    "path": path,
                    "rel": os.path.join(sub, fn),
                    "lines": lines,          # [(lineno, text)]，已剔除围栏代码块
                    "headings": sum(1 for _, t in lines if HEADING_RE.match(t)),
                    "text": "\n".join(t for _, t in lines),
                }


def read_text_lines(path):
    """读文件，剔除围栏代码块，返回 [(行号, 文本)]。"""
    out = []
    in_fence = False
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read().split("\n")
    except OSError:
        return out
    for i, ln in enumerate(raw, 1):
        if FENCE_RE.match(ln):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # 行内代码 span 内容不参与文本检查
        out.append((i, re.sub(r"`[^`]*`", "", ln)))
    return out


def parse_glossary(path):
    """解析 | 原文 | 统一译法 | 禁用译法 | 备注 | 表格。"""
    terms = []
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read().split("\n")
    except OSError:
        return terms
    for i, ln in enumerate(raw, 1):
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if re.fullmatch(r"[-: ]+", cells[0] or ""):
            continue  # 分隔行
        if "原文" in cells[0] or "统一译法" in cells[1]:
            continue  # 表头
        src, locked = cells[0], cells[1]
        banned = []
        if len(cells) >= 3 and cells[2] not in ("", "无", "-", "/"):
            banned = [b.strip() for b in
                      re.split(r"[、，,／/]", cells[2]) if b.strip()]
        if src and locked:
            terms.append((src, locked, banned, i))
    return terms


def is_acronym_term(src):
    return re.fullmatch(r"[A-Z0-9]+", src) is not None


def latin_pattern(src):
    """拉丁术语的匹配模式：避开 CJK 包裹时的 \b 陷阱。"""
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(src) +
                      r"(?![A-Za-z0-9])",
                      re.IGNORECASE if re.search(r"[A-Za-z]", src) else 0)


def cjk_count(text):
    return len(CJK_RE.findall(text))


# ---------------- 术语类 ----------------

@rule("BT-TERM-001", "blocker", "术语", "术语原文残留在译文",
      "术语表的原文直接出现在译文中，说明该处没有翻译。")
def check_term_residual(proj, emit):
    for stem, ch in proj.translated.items():
        for src, locked, _banned, _ln in proj.terms:
            if len(src) < 2:
                continue
            # 缩写类术语：同文件出现过中文全称则放行（首次全称+后文缩写是规范做法）
            if is_acronym_term(src) and locked in ch["text"]:
                continue
            pat = latin_pattern(src)
            hits = 0
            for lineno, text in ch["lines"]:
                if pat.search(text):
                    emit("BT-TERM-001", ch["rel"], lineno,
                         text.strip()[:80],
                         "术语「%s」残留在译文，应统一译为「%s」"
                         % (src, locked))
                    hits += 1
                    if hits >= 3:
                        break


@rule("BT-TERM-002", "warning", "术语", "使用了术语表禁用译法",
      "译文出现了术语表明确禁用的译法，前后不统一。")
def check_term_banned(proj, emit):
    for stem, ch in proj.translated.items():
        for src, locked, banned, _ln in proj.terms:
            for b in banned:
                if not b or len(b) < 2:
                    continue
                hits = 0
                for lineno, text in ch["lines"]:
                    if b in text:
                        emit("BT-TERM-002", ch["rel"], lineno,
                             text.strip()[:80],
                             "术语「%s」用了禁用译法「%s」，应统一为「%s」"
                             % (src, b, locked))
                        hits += 1
                        if hits >= 3:
                            break


@rule("BT-TERM-003", "nit", "术语", "术语表条目在译文中零引用",
      "术语的统一译法在译文中从未出现：可能是漏译，也可能是术语表冗余。")
def check_term_unused(proj, emit):
    all_trans = "\n".join(ch["text"] for ch in proj.translated.values())
    all_src = "\n".join(ch["text"] for ch in proj.sources.values())
    rel = os.path.basename(proj.glossary_path) if proj.glossary_path else "glossary.md"
    for src, locked, _banned, lineno in proj.terms:
        if locked not in all_trans and src.lower() in all_src.lower():
            emit("BT-TERM-003", rel, lineno, locked,
                 "术语「%s」→「%s」在译文中零引用，请确认是漏译还是术语表冗余"
                 % (src, locked))


# ---------------- 未译残留类 ----------------

@rule("BT-UNTR-001", "warning", "残留", "英文片段残留在译文",
      "连续英文单词出现在译文（非术语表术语），疑似整句/半句漏译。")
def check_en_residual(proj, emit):
    glossary_latin = {src.lower() for src, _, _, _ in proj.terms
                      if re.search(r"[A-Za-z]", src)}
    for stem, ch in proj.translated.items():
        for lineno, text in ch["lines"]:
            for m in EN_RUN_RE.finditer(text):
                frag = m.group(0)
                low = frag.lower()
                if any(g in low or low in g for g in glossary_latin):
                    continue
                emit("BT-UNTR-001", ch["rel"], lineno,
                     text.strip()[:80],
                     "英文片段残留：「%s」，请翻译或确认为刻意保留" % frag)
                break  # 每行只报一次


@rule("BT-UNTR-002", "warning", "残留", "缩写无中文对照",
      "大写缩写首次出现时没有中文全称对照，读者可能看不懂。")
def check_acronym_no_cjk(proj, emit):
    glossary_src = {src.upper() for src, _, _, _ in proj.terms}
    for stem, ch in proj.translated.items():
        for lineno, text in ch["lines"]:
            for m in ACRONYM_RE.finditer(text):
                ac = m.group(0)
                if ac.upper() in glossary_src:
                    continue
                before = text[max(0, m.start() - 12):m.start()]
                if not CJK_RE.search(before):
                    emit("BT-UNTR-002", ch["rel"], lineno,
                         text.strip()[:80],
                         "缩写「%s」附近 12 字内无中文，建议首次出现用「中文全称（%s）」"
                         % (ac, ac))
                    break  # 每行只报一次


# ---------------- 标点类 ----------------

@rule("BT-PUNC-001", "warning", "标点", "中英文标点混用",
      "中文句子混入英文半角标点（, ; : ? ! 与句末英文句号），数字小数点除外。")
def check_mixed_punct(proj, emit):
    for stem, ch in proj.translated.items():
        for lineno, text in ch["lines"]:
            if not CJK_RE.search(text) or "http" in text:
                continue
            bad = [c for c in ",;:?!" if c in text]
            m = EN_PERIOD_RE.search(text)
            if bad or m:
                hit = "".join(bad) + ("句末英文句号" if m else "")
                emit("BT-PUNC-001", ch["rel"], lineno,
                     text.strip()[:80],
                     "中文句子混用英文标点：%s，请改用全角标点" % hit)


@rule("BT-PUNC-002", "warning", "标点", "英文直引号残留",
      "中文文本用了英文直引号 \"，应改用弯引号 “”。")
def check_straight_quotes(proj, emit):
    for stem, ch in proj.translated.items():
        for lineno, text in ch["lines"]:
            if CJK_RE.search(text) and '"' in text:
                emit("BT-PUNC-002", ch["rel"], lineno,
                     text.strip()[:80],
                     "英文直引号残留，请改用中文弯引号")


@rule("BT-PUNC-003", "nit", "标点", "中英文括号混用",
      "中文旁边用了半角括号，请统一为全角括号（）。")
def check_half_paren(proj, emit):
    for stem, ch in proj.translated.items():
        for lineno, text in ch["lines"]:
            if HALF_PAREN_RE.search(text):
                emit("BT-PUNC-003", ch["rel"], lineno,
                     text.strip()[:80],
                     "半角括号出现在中文旁，请改用全角括号")


# ---------------- 结构类 ----------------

@rule("BT-STRUCT-001", "blocker", "结构", "原文章节没有对应译文",
      "source/ 下的章节在 translated/ 下找不到同名文件，疑似缺译。")
def check_missing_translation(proj, emit):
    for stem, ch in proj.sources.items():
        if stem not in proj.translated:
            emit("BT-STRUCT-001", ch["rel"], 0, "",
                 "原文章节「%s」没有对应译文" % stem)


@rule("BT-STRUCT-002", "warning", "结构", "译文章节编号断层",
      "译文文件名开头的数字编号不连续，可能漏了一章。")
def check_number_gap(proj, emit):
    nums = set()
    for stem in proj.translated:
        m = NUM_PREFIX_RE.match(stem)
        if m:
            nums.add(int(m.group(1)))
    if len(nums) >= 2:
        missing = [n for n in range(min(nums), max(nums) + 1)
                   if n not in nums]
        if missing:
            emit("BT-STRUCT-002", "translated/", 0, "",
                 "译文章节编号断层，缺失编号：%s" % missing)


@rule("BT-STRUCT-003", "warning", "结构", "标题数量与原文严重错位",
      "单章标题数与原文差异过大，可能丢了标题或结构走样。")
def check_heading_mismatch(proj, emit):
    for stem in proj.sources:
        if stem not in proj.translated:
            continue
        s, t = proj.sources[stem], proj.translated[stem]
        if s["headings"] > 0 and (t["headings"] == 0 or
           abs(s["headings"] - t["headings"]) > max(2, 0.5 * s["headings"])):
            emit("BT-STRUCT-003", t["rel"], 0, "",
                 "标题数原文 %d / 译文 %d，差异过大请核对"
                 % (s["headings"], t["headings"]))


@rule("BT-STRUCT-004", "warning", "结构", "译文文件没有对应原文",
      "translated/ 下的文件在 source/ 下找不到同名原文，可能放错或多译。")
def check_orphan_translation(proj, emit):
    for stem, ch in proj.translated.items():
        if stem not in proj.sources:
            emit("BT-STRUCT-004", ch["rel"], 0, "",
                 "译文「%s」没有对应原文" % stem)


# ---------------- 翻译腔类 ----------------

def _density_stats(proj):
    for stem, ch in proj.translated.items():
        n = cjk_count(ch["text"])
        if n == 0:
            continue
        yield stem, ch, n


@rule("BT-LIT-001", "warning", "翻译腔", "“的”字密度过高",
      "欧化句式的第一信号：定语层层嵌套，中文宜拆短。")
def check_de_density(proj, emit):
    for stem, ch, n in _density_stats(proj):
        per100 = ch["text"].count("的") / n * 100
        if per100 > DE_PER_100_WARN:
            emit("BT-LIT-001", ch["rel"], 0, "",
                 "“的”字密度 %.1f/百字（阈值 %.1f），建议拆分定语从句"
                 % (per100, DE_PER_100_WARN))


@rule("BT-LIT-002", "warning", "翻译腔", "“进行”滥用",
      "“进行分析/进行讨论”类名物化结构，中文可直接用动词。")
def check_jinxing(proj, emit):
    for stem, ch, n in _density_stats(proj):
        per1000 = ch["text"].count("进行") / n * 1000
        if per1000 > JINXING_PER_1000_WARN:
            emit("BT-LIT-002", ch["rel"], 0, "",
                 "“进行”出现 %d 次（%.1f/千字，阈值 %.1f），建议改为直接动词"
                 % (ch["text"].count("进行"), per1000, JINXING_PER_1000_WARN))


@rule("BT-LIT-003", "warning", "翻译腔", "被动句“被”高频",
      "英文被动句直译堆砌，中文能主动就主动。")
def check_bei(proj, emit):
    for stem, ch, n in _density_stats(proj):
        per1000 = ch["text"].count("被") / n * 1000
        if per1000 > BEI_PER_1000_WARN:
            emit("BT-LIT-003", ch["rel"], 0, "",
                 "“被”出现 %d 次（%.1f/千字，阈值 %.1f），建议改主动句"
                 % (ch["text"].count("被"), per1000, BEI_PER_1000_WARN))


@rule("BT-LIT-004", "nit", "翻译腔", "超长未断句",
      "单句过长且无逗号断句，读者一口气读不完。")
def check_long_sentence(proj, emit):
    for stem, ch in proj.translated.items():
        hits = 0
        for sent in re.split(r"[。！？]", ch["text"]):
            if cjk_count(sent) > LONG_SENT_CJK and "，" not in sent:
                emit("BT-LIT-004", ch["rel"], 0,
                     sent.strip()[:60] + "…",
                     "单句 %d 字无断句，建议拆成 2-3 个短句"
                     % cjk_count(sent))
                hits += 1
                if hits >= 3:
                    break


@rule("BT-LIT-005", "nit", "翻译腔", "程度副词堆砌",
      "非常/十分/极其/特别高频， weaken 中文表达的力度。")
def check_degree_adv(proj, emit):
    for stem, ch, n in _density_stats(proj):
        cnt = sum(ch["text"].count(w) for w in DEGREE_ADV)
        per1000 = cnt / n * 1000
        if per1000 > ADV_PER_1000_NIT:
            emit("BT-LIT-005", ch["rel"], 0, "",
                 "程度副词共 %d 次（%.1f/千字，阈值 %.1f），建议删减或换具体描述"
                 % (cnt, per1000, ADV_PER_1000_NIT))


# ---------------- 主流程 ----------------

def run(target):
    proj = Project(target)
    proj.load()
    findings = []

    def emit(rule_id, file, line, snippet, detail):
        r = _RULE_BY_ID[rule_id]
        findings.append(Finding(rule_id, r["severity"], r["category"],
                                r["title"], file, line, snippet, detail))

    for r in RULES:
        try:
            r["check"](proj, emit)
        except Exception as e:
            findings.append(Finding(r["id"], "nit", "脚本",
                                    "规则执行异常", "translation_audit.py", 0,
                                    "", "规则 %s 执行出错：%s（已跳过）"
                                    % (r["id"], e)))
    return proj, findings


def main(argv=None):
    ap = argparse.ArgumentParser(description="lhg-book-translate 翻译一致性审计")
    ap.add_argument("--target", default=".", help="翻译项目目录")
    ap.add_argument("--format", choices=["json", "text"], default="text")
    ap.add_argument("--fail-on", choices=["blocker", "warning", "nit"],
                    default="blocker")
    args = ap.parse_args(argv)

    target = os.path.abspath(args.target)
    if not os.path.isdir(target):
        print("target 不是目录：%s" % args.target, file=sys.stderr)
        return 1

    proj, findings = run(target)
    sev_rank = {"blocker": 3, "warning": 2, "nit": 1}
    counts = {"blocker": 0, "warning": 0, "nit": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    result = {
        "tool": TOOL,
        "version": VERSION,
        "target": args.target,
        "summary": {
            "files_scanned": len(proj.translated),
            "terms_loaded": len(proj.terms),
            "rules_run": len(RULES),
            "blocker": counts["blocker"],
            "warning": counts["warning"],
            "nit": counts["nit"],
        },
        "findings": [f.to_dict() for f in sorted(
            findings, key=lambda x: (-sev_rank.get(x.severity, 0),
                                     x.file, x.line))],
    }

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        s = result["summary"]
        print("翻译审计：扫描 %d 个译文文件，载入 %d 条术语，运行 %d 条规则" % (
            s["files_scanned"], s["terms_loaded"], s["rules_run"]))
        print("blocker=%d warning=%d nit=%d" % (
            s["blocker"], s["warning"], s["nit"]))
        for f in result["findings"]:
            print("[%s][%s] %s:%d %s" % (
                f["severity"].upper(), f["rule_id"], f["file"],
                f["line"], f["title"]))
            print("    %s" % f["detail"])
            if f["snippet"]:
                print("    → %s" % f["snippet"])

    level = sev_rank[args.fail_on]
    bad = any(sev_rank.get(f.severity, 0) >= level for f in findings)
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
