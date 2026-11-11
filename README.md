# Apex Lab · 枪械与排位实验室

一个可本地运行的数据库课程项目。Python / Flask 提供 API，SQLAlchemy 负责关系数据访问；Vue 3 与 ECharts 提供交互界面。默认 SQLite，预留 MySQL 配置。

## 开始使用

Windows 双击 **start.cmd**。首次运行会建立独立 Python 环境并安装依赖，随后打开浏览器：


需要 Python 3.9 或以上版本。首次安装需要联网；前端依赖与枪械图片已随源码保存，正常使用无需 CDN。运行时保留启动窗口；关闭窗口即可停止服务。若提示端口占用，先关闭已有的启动窗口，或在 `.env` 中修改 `PORT`。

请从 `start.cmd` 启动并使用浏览器。直接双击 `frontend/index.html` 会以本地文件方式打开，无法连接 Flask 应用。

命令行启动：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

安装环境的完整版本记录在 `requirements-lock.txt`。界面使用本地 Vue 浏览器发行版，不要求安装 Node.js，也不需要构建前端。

## 账号

- 访客可以查看枪械、版本与 TTK。
- 在“排位数据库”点击“用样例数据体验”即可登录普通演示账号。
- 也可以注册自己的账号，从空白日志开始。各账号的日志与收藏分开保存。
- 首次启动自动生成管理员账号与随机密码，保存在 **instance/initial-admin.txt**。用它登录“数据管理”。登录后点击右上角账号可修改密码。
- `.env`、`instance/` 内的数据库、会话密钥和初始密码文件均不应提交到代码仓库。
- 演示账号仅适合本地课堂演示。需要关闭快捷登录时，在 `.env` 中设置 `DEMO_MODE=false`。

## 已实现

1. 枪械搜索、分类、排序、收藏，图片详情和历史版本档案。
2. 设定生命值、命中部位、弹匣、换弹规则，计算理论 TTK、击倒所需发数、一弹匣伤害；条形排行与最多四把枪的伤害阶梯图。
3. 登录 / 注册 / 修改密码。个人比赛新增、修改、删除、日期及地图筛选、分页、CSV 导出；累计 RP、武器使用统计和可按最低场次筛选的地图表现。
4. 管理员新建枪械与赛季版本、录入 / 编辑参数、JSON 批量导入、审计记录。批次校验失败整批回滚；版本号防止旧编辑覆盖新数据。
5. SQLite 外键与约束、常用查询索引、密码哈希、会话与 CSRF 校验、用户数据隔离、SQL 参数化、CSV 公式转义。

## 数据边界

预置 **31 个武器档案、S30 的 29 条版本参数**、42 条用户提供的 TTK 参考记录，以及演示账号的 8 场教学比赛。旧版 TTK 截图记录暂存以供复核，目前不在页面展示；排行榜使用当前武器参数实时计算。S28 和 S29 暂无版本参数；未使用 S30 数值填充旧赛季。

- S30 参数来源为 Apex Weapon Stats，基准日期 2026-09-16。头部和腿部伤害由来源列出的伤害倍率计算；记录状态为“部分核实”，以标明非官方来源及模型近似。
- **TTK 是本项目逐发计算结果，不等于游戏实测排行。** 霰弹按每枚弹丸都命中同一部位计算；空仓换弹会替代正常射击间隔。逐发装填、加速射击、热量、弹道飞行、伤害减免、移动和网络延迟未完整模拟。没有传统弹匣的武器不参与 TTK 对比。
- 霰弹每次所有弹丸命中同一部位。连发间隔是本轮最后一发到下一轮第一发的间隔；换弹替代正常射击间隔。逐发装填、加速射击、伤害减免、技能、飞行时间、移动及网络延迟未模拟。
- 当前没有完整十赛季数据、动态视频或交互式 3D 素材。这些属于后续扩展。
- 枪械图片来自 Apex Legends Wiki，素材属于 EA / Respawn 等权利人，仅供课程项目使用。具体页面、资源地址与 SHA-256 记录见 `frontend/assets/sources.json`。

## 后续切换 MySQL

SQLite 已完成实际验证。MySQL 驱动、建表模型和 MySQL DDL 已准备，尚未使用你的 MySQL 账号实测。

1. 在 MySQL 8+ 建立专用数据库，例如 `apex_lab`，字符集使用 `utf8mb4`。建议创建仅能访问这个库的专用账号。
2. 本地 `.env` 设置：

```text
DATABASE_URL=mysql+pymysql://apex_user:URL编码后的密码@127.0.0.1:3306/apex_lab?charset=utf8mb4
```

3. 重启应用，首次启动会建立缺少的表并初始化演示数据。

这会连接一个新的数据库，**不会自动迁移 SQLite 中已经录入的数据**。需要保留现有日志时，先备份，再实施数据迁移。不要直接删除 SQLite 文件。

## 测试与备份

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/backup_sqlite.py
.\.venv\Scripts\python.exe scripts/export_schema.py
```

测试在临时数据库内进行，不会修改你的日志或管理员密码。备份工具使用 SQLite backup API，能在应用运行时生成一致性快照并做完整性检查。恢复时先停止服务、保留原 `instance/apex.db`，再用备份文件替换；会话密钥和账号仍需妥善保管。

`database/schema.sqlite.sql` 和 `database/schema.mysql.sql` 是由实际模型生成的 v1 基线。首版通过 `schema_version` 标记版本；将来修改已有表结构时要增加显式迁移，不能依赖 `create_all()` 自动改列。

## 源码入口

```text
backend/models.py     数据表、外键、约束与索引
backend/app.py        登录、查询、日志、管理与同步 API
backend/ttk.py        按发射事件计算 TTK
backend/seed.py       标注来源与局限的初始数据
frontend/index.html   Vue 页面模板
frontend/app.js       页面逻辑、接口调用与图表
frontend/styles.css   桌面与手机布局
tests/test_system.py  计算、权限、事务和 CRUD 测试
scripts/              备份、DDL 导出与素材准备工具
```

## Track 1 数据库设计与实验

本地 SQLite 文件位于 `instance/apex.db`。展示时可在 DB Browser for SQLite 中打开该文件，进入「浏览数据」，查看 `match`、`match_weapon` 和 `weapon` 等表。

[数据库设计说明](database/design.md)包含 ER 图、关键约束、规范化、索引策略及事务演示。项目启动过一次并保有演示账号时，可在项目目录运行以下命令：

```powershell
python scripts/run_sample_queries.py --username demo --min-matches 3
python scripts/benchmark_match_index.py --rows 10000
python scripts/benchmark_match_index.py --rows 100000
```

查询脚本以只读模式运行 [SQLite 示例 SQL](database/sample_queries.sql)，可用 `--from` 和 `--to` 指定日期。索引实验在内存中生成合成比赛数据，输出有无联合索引的执行计划和查询耗时中位数。

## S28–S30 数据更新

当前版本选择显示 S30、S29、S28，默认最新 S30 参数基线。S30 的枪械伤害、倍率、射速、弹匣与空仓换弹整理自 [Apex Weapon Stats](https://apex-legends.ttkdb.com/en)，基准日期为 2026-09-16；29 把常规枪械可查看档案并用于现有模型支持的 TTK 对比。头部与腿部伤害按来源倍率计算，管理员首次启动时会将缺少的参数导入当前数据库；重复启动不会覆盖管理员编辑记录。来源未提供弹匣时沿用基础容量，未使用传统弹匣的武器只展示档案、不参与 TTK 计算。模型不能完整表达热量、蓄力、逐发装填和全部特殊射击模式，相关记录标为“部分核实”并附来源。

旧版 S30 的 42 条紫甲 TTK 参考配置来自用户提供的图片（2026-08-05，老葛你又在打电动），原图保存在 frontend/assets/s30-ttk-reference.png。参考值暂时只存档，因与当前参数计算结果存在差异，页面不再展示或参与排序。S28/S29 武器参数仍待补充，不以 S30 数值代填。赛季汇总日期使用 1970-01-01 哨兵值，API 返回 null，不作为赛季发布日期展示。
