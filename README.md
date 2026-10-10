<!-- About 简介（推送后填写到仓库 About 栏）：
书籍翻译专家：术语表锁定→章节翻译→一致性审计→译者体润色，交付出版级中文译稿 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-book-translate
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, book-translation, glossary, proofreading, chinese, ai-agents -->

# lhg-book-translate：书籍翻译专家

> **一句话介绍**：给 AI 助手装上"书籍翻译工程线"——原文入库、术语表锁定、章节三遍翻译法、17 条确定性一致性审计、译者体润色，小白也能交付出版级中文译稿。
>
> **一键安装**：在 Claude Code 里运行
> ```
> /plugin marketplace add lhg-plugs/lhg-book-translate
> /plugin install lhg-book-translate@lhg-plugs
> ```

## 它是什么

`lhg-book-translate` 是一个 Claude Code 插件（plugin 为主、skill 为辅）：

- **4 个命令**（小白入口）：`book-translate` 整书翻译一条龙，`book-glossary` 术语表锁定，`book-audit` 一致性审计，`book-polish` 译者体润色
- **4 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：术语表锁定、章节三遍翻译法、一致性审计、去翻译腔润色
- **3 个专家 agent**：翻译官、术语守卫、毒舌译审
- **2 个硬门 hooks**：commit 前审计拦截（有 blocker 不许提交）、译文写入后术语表过期提醒（均可一键豁免）
- **17 条确定性审计规则**：纯 Python、零第三方依赖，秒级出结果

## 4 个命令用法

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-book-translate:book-translate` | 一句话 → 整书翻译工程（术语锁定→逐章翻译→审计→润色） | `/lhg-book-translate:book-translate "source/ 简体中文"` |
| `/lhg-book-translate:book-glossary` | 构建并锁定全书术语表 | `/lhg-book-translate:book-glossary "source/ AI科普"` |
| `/lhg-book-translate:book-audit` | 17 条规则审计 + 人工评审清单 | `/lhg-book-translate:book-audit` |
| `/lhg-book-translate:book-polish` | 去翻译腔润色（轻量/深度两档） | `/lhg-book-translate:book-polish --deep` |

## 翻译工程约定

插件审计脚本按以下项目结构工作（`/book-translate` 会自动建好）：

```
trans-<书名>/
├── glossary.md          # 术语表：| 原文 | 统一译法 | 禁用译法 | 备注 |
├── source/              # 原文章节 .md
├── translated/          # 译文章节 .md（与 source/ 文件名一一对应）
└── translation-log.md   # 翻译日志
```

## 自查说明

自查 = 确定性脚本（机器）+ 人工评审清单（人）：

1. 先跑 `scripts/audit/translation_audit.py`（17 条规则：术语 3、残留 2、标点 3、结构 4、翻译腔 5），零 LLM 成本；
2. 发现分三级：**blocker**（必须修，commit 前 hook 会拦截）、**warning**（修或写豁免理由）、**nit**（顺手修）；
3. 再按 `lhg-bt-audit` skill 的人工五项过一遍脚本抓不到的（语气统一、文化梗处理、长难句质量、数字单位、抽样回译）。

blocker 清零才算做完；为清零改规则、删术语表条目算作弊，不许。

## 目录结构

```
lhg-book-translate/
├── .claude-plugin/          # plugin.json（插件清单）+ marketplace.json（本仓即市场）
├── commands/                # 4 个命令：book-translate / book-glossary / book-audit / book-polish
├── skills/                  # 4 个平台中立 skill（lhg-bt-glossary/chapter/audit/polish）
├── agents/                  # 3 个专家 agent（book-translator / term-keeper / book-editor）
├── hooks/                   # 2 个硬门（commit 前审计拦截 / 术语表过期提醒）+ 豁免说明
├── scripts/audit/           # 17 条确定性审计规则（零第三方依赖）
├── fixtures/                # 冒烟测试用例（trans-bad 坏 / trans-good 好对照）
├── smoke_test.py            # 一键冒烟测试
├── ATTRIBUTION.md           # 灵感来源与许可声明
└── LICENSE                  # MIT
```

## 什么时候用 / 什么时候不用（FAQ）

**什么时候用：**

- 你有一本外文书/外文文档想翻成中文，但怕术语前后不一、翻译腔重时 → 用 `/lhg-book-translate:book-translate`
- 你已经在翻了，术语乱成一锅粥时 → 先跑 `/lhg-book-translate:book-glossary` 重建术语表，再统一替换
- 你拿到一份别人翻的译文想校对时 → 跑 `/lhg-book-translate:book-audit`，17 条规则先扫一遍定位重灾区
- 译文都对但读起来别扭时 → 用 `/lhg-book-translate:book-polish` 去翻译腔

**什么时候不用：**

- 你只想随手翻一段话、一条朋友圈 → 本插件是"工程线"，杀鸡不用牛刀，直接问 AI 翻译即可
- 你的原文是扫描版 PDF 且没转成文本 → 本插件不做 OCR/格式转换，先把文字版准备好再来
- 你要求"信达雅"的文学再创作级翻译 → 本插件保"忠实+通顺+一致"，文学性的再创作需要译者人工主导，插件只打辅助

## lhg-plugs 插件矩阵

| 插件 | 一句话 | 安装 |
|---|---|---|
| [lhg-fullstack](https://github.com/lhg-plugs/lhg-fullstack) | 小白一句话 → 高质量全栈应用 | `/plugin install lhg-fullstack@lhg-plugs` |
| [lhg-video-edit](https://github.com/lhg-plugs/lhg-video-edit) | 一句话把口播素材剪成爆款短视频（+口播脚本子命令） | `/plugin install lhg-video-edit@lhg-plugs` |
| [lhg-wechat-article](https://github.com/lhg-plugs/lhg-wechat-article) | 公众号写作专家：选题到排版一气呵成 | `/plugin install lhg-wechat-article@lhg-plugs` |
| [lhg-xiaohongshu](https://github.com/lhg-plugs/lhg-xiaohongshu) | 小红书种草专家：卖点到爆款笔记一键生成 | `/plugin install lhg-xiaohongshu@lhg-plugs` |
| [lhg-resume](https://github.com/lhg-plugs/lhg-resume) | 简历优化专家：ATS诊断到模拟面试一条龙 | `/plugin install lhg-resume@lhg-plugs` |
| [lhg-ppt](https://github.com/lhg-plugs/lhg-ppt) | PPT制作专家：述职融资答辩一键成稿 | `/plugin install lhg-ppt@lhg-plugs` |
| [lhg-excel](https://github.com/lhg-plugs/lhg-excel) | 表格数据专家：清洗透视图表一条龙 | `/plugin install lhg-excel@lhg-plugs` |
| [lhg-thesis](https://github.com/lhg-plugs/lhg-thesis) | 毕业论文助手：开题到盲审的写作流水线 | `/plugin install lhg-thesis@lhg-plugs` |
| [lhg-miniprogram](https://github.com/lhg-plugs/lhg-miniprogram) | 小程序开发专家：一句话生成微信小程序 | `/plugin install lhg-miniprogram@lhg-plugs` |
| [lhg-contract](https://github.com/lhg-plugs/lhg-contract) | 合同审查助手：风险条款标红+修改建议 | `/plugin install lhg-contract@lhg-plugs` |
| [lhg-geo](https://github.com/lhg-plugs/lhg-geo) | AI搜索优化专家：品牌在AI回答里的可见度 | `/plugin install lhg-geo@lhg-plugs` |
| [lhg-poster](https://github.com/lhg-plugs/lhg-poster) | 海报设计专家：一句话生成手机端海报 | `/plugin install lhg-poster@lhg-plugs` |
| [lhg-shopify](https://github.com/lhg-plugs/lhg-shopify) | 独立站建站专家：高转化店铺一键搭建 | `/plugin install lhg-shopify@lhg-plugs` |
| [lhg-fiction](https://github.com/lhg-plugs/lhg-fiction) | 网文写作专家：大纲到逐章+人设一致性检测 | `/plugin install lhg-fiction@lhg-plugs` |
| [lhg-drama-script](https://github.com/lhg-plugs/lhg-drama-script) | 短剧剧本专家：分集大纲到单集剧本 | `/plugin install lhg-drama-script@lhg-plugs` |
| [lhg-lit-review](https://github.com/lhg-plugs/lhg-lit-review) | 文献综述专家：框架到引用校验一条龙 | `/plugin install lhg-lit-review@lhg-plugs` |
| [lhg-salary-talk](https://github.com/lhg-plugs/lhg-salary-talk) | 薪酬谈判专家：策略到话术演练 | `/plugin install lhg-salary-talk@lhg-plugs` |
| [lhg-biz-report](https://github.com/lhg-plugs/lhg-biz-report) | 商业分析专家：数据到图文报告一键生成 | `/plugin install lhg-biz-report@lhg-plugs` |
| [lhg-study-abroad](https://github.com/lhg-plugs/lhg-study-abroad) | 留学文书专家：PS推荐信多轮打磨 | `/plugin install lhg-study-abroad@lhg-plugs` |
| [lhg-meal-plan](https://github.com/lhg-plugs/lhg-meal-plan) | 营养食谱专家：测算到一周食谱+采购单 | `/plugin install lhg-meal-plan@lhg-plugs` |
| [lhg-book-translate](https://github.com/lhg-plugs/lhg-book-translate) | 书籍翻译专家：术语锁定→章节翻译→一致性审计→译者体润色 | `/plugin install lhg-book-translate@lhg-plugs` |
| *（后续插件在此追加，保持表格格式一致）* | | |

## 自检与反馈

本插件自带质检：每次使用后可跑 `python3 smoke_test.py` 一键验证（JSON 合法、skill/command/agent 完整性、17 条规则、fixtures 命中、hooks 行为）。

发现 bug 或有改进建议，以 `[QC] <一句话问题>` 为标题提交到 https://github.com/lhg-plugs/lhg-book-translate/issues，正文写清"复现步骤 → 实际表现 → 期望表现"。

## 出品：刘洪光

本插件由真人出镜 IP「刘洪光」（安徽合肥）出品，归属 [lhg-skills](https://github.com/lhg-skills)。

- GitHub 主页：https://github.com/lhg-skills —— 全部 skill 开源在此，欢迎 star
- 视频号：搜「刘洪光实名上网」
- 微信：lhgsmsw
