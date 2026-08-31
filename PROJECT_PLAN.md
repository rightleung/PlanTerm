# PlanTerm v0.1：MINISO FP&A Portfolio MVP

## Summary

在空目录 `/Users/rightleung/Documents/Python/PlanTerm` 建立独立的 Python 3.12 + FastAPI + React 19 项目，以 MINISO 为公开数据案例，展示：

- Actual / Budget / Forecast / Prior Year
- 品牌与区域经营分析
- Actual vs Budget、YoY、Forecast vs Budget
- Price / Volume / Mix
- Revenue、Gross Profit、Operating Profit、Margin
- 确定性管理层洞察
- 英文 Dashboard 和 Excel Management Pack

v0.1 只包含三个业务单元：

1. MINISO - Chinese Mainland
2. MINISO - Overseas
3. TOP TOY - Global

产品品类、情景编辑、CSV 上传、PDF、多语言和同行比较进入后续版本。

公开基准使用 MINISO 2025 年度 IFRS 数据和截至 2026-06-30 的半年数据；官方披露支持集团收入、成本、利润和上述品牌/地区拆分。[MINISO 2025 Form 20-F](https://ir.miniso.com/sec-filings?action=view&filer=Ticker:MNSO&item=1008095&pagetemplate=basic)、[MINISO 2026 H1 results](https://ir.miniso.com/2026-08-28-MINISO-Group-Announces-2026-June-Quarter-and-Interim-Unaudited-Financial-Results)。

## 1. Repository initialization and RiskLens migration

### Git structure

1. 在 PlanTerm 创建 `PROJECT_PLAN.md`，保存本计划作为执行来源。
2. `git init -b main`，不得复制 RiskLens 的 `.git`。
3. 从 RiskLens commit `55b2ae63` 选择性迁移：
   - FastAPI 错误响应、配置和 SPA serving 模式。
   - React/Vite/Tailwind 配置和 `web/src/components/ui/`。
   - ExcelJS、Playwright、CI、启动和重建脚本的结构。
4. 不迁移：
   - `zscore.py`、`ratio_analyzer.py`、`covenant_monitor.py`
   - AKShare/yfinance ticker search 和信用数据抓取层
   - PDF exporter、CJK 字体、翻译、legacy UI、CLI
   - RiskLens 测试、截图、文档和所有生成目录
5. 包名、应用名和版本统一为：
   - Python package：`planterm`
   - Product：`PlanTerm`
   - Description：`FP&A Planning and Performance Management Workbench`
   - Version：`0.1.0`
6. 使用 MIT License；README 说明工程基础源自作者自己的 RiskLens 项目，但 Git 历史独立。

### Commit sequence

- `chore: initialize PlanTerm foundation`
- `feat: add MINISO planning case and analysis API`
- `feat: build FP&A dashboard and Excel management pack`
- `test: add reconciliation, API, and browser coverage`
- `docs: prepare PlanTerm v0.1 portfolio release`

开发分支使用 `codex/v0.1-mvp`，全部验证通过后合并至 `main`。

## 2. Data and backend implementation

### Target structure

```text
PlanTerm/
├── PROJECT_PLAN.md
├── README.md
├── ROADMAP.md
├── pyproject.toml
├── requirements.txt
├── run_app.sh
├── scripts/
│   ├── rebuild_workspace.sh
│   ├── refresh_public_actuals.py
│   └── build_miniso_case.py
├── data/
│   ├── source/
│   │   └── miniso_public_actuals.json
│   └── cases/miniso-2026/
│       ├── metadata.json
│       ├── assumptions.json
│       └── planning_records.csv
├── src/
│   ├── api.py
│   ├── config.py
│   ├── models/planning.py
│   ├── repositories/case_repository.py
│   └── services/
│       ├── case_builder.py
│       ├── planning_service.py
│       ├── variance_service.py
│       ├── pvm_service.py
│       └── insight_service.py
├── tests/
└── web/
```

### Public snapshot and provenance

`miniso_public_actuals.json` 保存：

- Company：MINISO Group Holding Limited
- Tickers：NYSE `MNSO`、HKEX `9896`
- Currency/unit：RMB millions
- Accounting standard：IFRS
- Periods：FY2025、2025 H1、2026 Q1、2026 Q2、2026 H1
- Metrics：Revenue、Cost of Sales、Gross Profit、Operating Profit、Adjusted EBITDA、Operating Cash Flow、CAPEX、FCF
- Revenue split：MINISO Mainland、MINISO Overseas、TOP TOY
- 每个数据点包含 `source_url`、`source_date`、`period_end`、`provenance=public_reported`

`refresh_public_actuals.py`：

- 从固定的 MINISO IR/20-F URL 下载并解析公开表格。
- 默认只 dry-run 和显示差异。
- 只有传入 `--write` 才更新 snapshot。
- 写入前验证期间、币种、必需指标、合计关系和来源 URL。
- 页面结构变化时明确失败，不静默填入 `0` 或旧值。
- CI 不访问网络；解析测试使用最小 HTML fixture。

### Synthetic planning case

`build_miniso_case.py` 从公开 snapshot 和 `assumptions.json` 生成确定性的长表数据，不使用随机数。记录字段：

```text
period
scenario                actual | budget | forecast | prior_year
brand                   MINISO | TOP_TOY
market                  mainland | overseas | global
business_unit
metric
value
unit
provenance              public_reported | synthetic_allocation |
                        synthetic_plan | calculated
```

固定案例：

- Planning year：CY2026
- As-of date：2026-06-30
- H1 Actual：锚定官方 2026 H1 数据。
- Prior Year：锚定官方 2025 H1/FY2025 数据。
- FY2026 Budget：模拟。
- FY2026 Forecast：H1 Actual + 模拟 H2 latest estimate。
- 官方季度/半年数据按固定季节性权重拆成月度；月度必须标记 `synthetic_allocation`。
- 业务单元成本、交易量、客单价和利润分配均标记为模拟，不暗示属于 MINISO 内部数据。

固定预算假设：

| Business unit | Revenue growth vs FY2025 | Budget GM | Budget operating margin | Average ticket |
|---|---:|---:|---:|---:|
| MINISO Mainland | 18% | 43.5% | 14% | RMB 95 |
| MINISO Overseas | 22% | 47.5% | 16% | RMB 145 |
| TOP TOY | 45% | 48.0% | 15% | RMB 185 |

H2 forecast adjustment versus H2 budget：

- Mainland：`+3%`
- Overseas：`-5%`
- TOP TOY：`-8%`

月度季节性权重：

```text
Jan 7.5%, Feb 6.5%, Mar 8.0%
Apr 8.0%, May 8.5%, Jun 9.5%
Jul 8.0%, Aug 8.0%, Sep 9.5%
Oct 8.0%, Nov 8.5%, Dec 10.0%
```

生成后必须满足：

- 月度之和等于季度/半年/全年锚点。
- 业务单元收入之和等于集团收入。
- `revenue = volume × average_ticket`。
- `gross_profit = revenue - cost_of_sales`。
- `operating_profit = gross_profit - operating_expense`。
- 差异容忍度为 RMB 0.01 million。
- Future Actual 是缺失值，不得写成零。

### Models and calculations

`models/planning.py` 定义：

- `Scenario`
- `Provenance`
- `PlanningRecord`
- `KpiSnapshot`
- `VarianceRow`
- `PvmBridge`
- `ManagementInsight`
- `PlanningDashboardResponse`

核心指标注册表：

| Metric | Favorability |
|---|---|
| Revenue | higher is better |
| Gross Profit | higher is better |
| Gross Margin | higher is better |
| Operating Profit | higher is better |
| Operating Margin | higher is better |
| Volume | higher is better |
| Average Ticket | higher is better |
| Operating Expense | lower is better |

统一输出：

- Actual YTD
- Budget YTD
- Variance amount
- Variance %
- Prior-year YTD
- YoY %
- FY Budget
- FY Forecast
- Forecast gap
- Favorable / Unfavorable / Neutral

状态阈值为 `±1%`；除零和缺失分母返回 `null`，不得返回 Infinity、NaN 或伪造百分比。

PVM 使用 YTD Actual vs YTD Budget：

```text
Volume = (Total actual volume - Total budget volume)
         × Budget weighted average ticket

Mix = Σ[(Actual volume_i - Budget volume_i)
        × (Budget ticket_i - Budget weighted average ticket)]

Price = Σ[Actual volume_i
          × (Actual ticket_i - Budget ticket_i)]
```

要求：

```text
Volume + Mix + Price = Actual revenue - Budget revenue
```

reconciliation difference 必须小于 RMB 0.01 million。

`insight_service.py` 只生成确定性洞察：

- 找出绝对金额最大的两个不利业务单元。
- 解释主要来自 Price、Volume、Mix 或 Opex。
- 显示 FY Forecast gap。
- 根据驱动因素输出预定义行动：
  - Price：检查促销和折扣。
  - Volume：检查客流、转化率和单店效率。
  - Mix：调整高毛利品牌/区域组合。
  - Opex：复核销售与分销费用。
- 不使用 LLM，不生成数据无法支持的原因。

### Public API

```text
GET /health
GET /api/v1/cases
GET /api/v1/cases/{case_id}/dashboard
```

Dashboard query parameters：

```text
brand=all|MINISO|TOP_TOY
market=all|mainland|overseas|global
```

Response 包含：

```text
metadata
available_filters
selected_filters
kpis
monthly_trend
business_unit_variances
pvm_bridge
management_insights
data_sources
provenance_legend
```

错误规则：

- 未知 case：404
- 非法 filter：422
- 数据校验或 reconciliation 失败：500，并记录内部原因但不暴露堆栈
- 统一错误结构：`error`、`error_type`、`details`

运行时只读取固定案例，不依赖网络、数据库或用户账号。

## 3. Frontend and Excel deliverable

### Dashboard

重写 `web/src/App.tsx`，控制在约 250 行以内；业务组件分别放入：

```text
web/src/
├── api/client.ts
├── types/planning.ts
├── features/dashboard/
│   ├── FilterBar.tsx
│   ├── KpiGrid.tsx
│   ├── MonthlyTrendChart.tsx
│   ├── VarianceTable.tsx
│   ├── PvmBridge.tsx
│   ├── ManagementInsights.tsx
│   └── DataProvenance.tsx
└── export/managementPack.ts
```

使用 Recharts，页面顺序固定为：

1. PlanTerm header、案例名称、as-of date、公开/模拟数据声明
2. Brand/Market filters
3. Revenue、Gross Profit、Operating Profit、Operating Margin KPI cards
4. Monthly Actual/Budget/Forecast/Prior Year trend
5. Business-unit variance table
6. Price/Volume/Mix bridge
7. Management insights and actions
8. Assumptions、data source 和 provenance legend
9. Export Excel

必须包含 loading、API error、empty state 和 filter reset。英文 UI，不迁移 RiskLens 四语言逻辑。

### Excel Management Pack

`managementPack.ts` 使用 ExcelJS 输出：

1. `Executive Summary`
2. `Monthly Trend`
3. `Business Unit Variance`
4. `PVM Bridge`
5. `Assumptions & Sources`

要求：

- 数字单位明确为 RMB millions。
- Variance 使用公式或已验证数值。
- Favorable/Unfavorable 有一致颜色。
- Assumptions 页逐项区分公开数据和模拟数据。
- 文件名：`PlanTerm_MINISO_2026H1_Management_Pack.xlsx`
- 导出内容必须反映当前 Dashboard filter。

v0.1 不做 PDF。

## 4. Tests, CI and acceptance

### Backend tests

覆盖：

- Public snapshot schema 和必需来源字段。
- Refresh parser 对正常/缺字段/页面结构变化的处理。
- Case builder 可重复生成相同结果。
- 公开集团数据与业务单元/月度数据 reconciliation。
- Actual、Budget、Forecast、Prior Year 聚合。
- Revenue/profit 和 cost favorability 方向。
- Zero denominator、missing value、future actual。
- PVM bridge 精确回到 revenue variance。
- Brand/market filters。
- Deterministic management insights。
- API health、case list、dashboard、404、422 和安全错误响应。

### Frontend and browser tests

Playwright 验证：

- Dashboard 在无网络数据源的情况下启动。
- 默认 MINISO case 和数据声明可见。
- 切换 brand/market 后 KPI、表格和 PVM 更新。
- API error state 可恢复。
- Excel 下载成功。
- 用 ExcelJS 重新打开下载文件，验证五个 sheet、关键标题和汇总值。
- 生成 `docs/assets/planterm-dashboard.png` 作为 README 截图。

### CI

从 RiskLens CI 精简为：

- Python 3.12 package install、`pip check`、`pytest -q`
- Case generator `--check`，并要求生成结果与 committed CSV 一致
- Node 24 `npm ci`、lint、build、Playwright Chromium preflight
- `pip-audit` 和 `npm audit --audit-level=high`
- 不安装 Poppler，不验证字体，不运行 PDF 测试

本地 release gate：

```bash
python -m pip check
python -m pytest -q
python scripts/build_miniso_case.py --check
cd web
npm run lint
npm run build
npm run e2e:preflight
```

Acceptance criteria：

- 本地启动后首页无需联网即可展示完整案例。
- 所有公开数值带来源，所有模拟数值带明确标识。
- H1 Actual、FY2025、业务单元和集团合计全部 reconcile。
- PVM reconciliation difference ≤ RMB 0.01 million。
- Filters 和 Excel 导出一致。
- 页面、README、包名和输出中不存在 RiskLens、Altman、credit rating 或 covenant 残留。
- 全部 release gate 通过。

## 5. GitHub publication and later roadmap

当前 `gh auth status` 显示 `rightleung` token 无效。执行模型在远端写入前必须：

1. 完成本地 v0.1 和全部测试。
2. 运行 `gh auth login -h github.com --web`；如需用户浏览器确认则暂停等待。
3. 再次运行 `gh auth status`。
4. 确认 `rightleung/PlanTerm` 不存在；如果已存在，停止并让用户决定，不覆盖。
5. 创建并推送：

```bash
gh repo create rightleung/PlanTerm \
  --public \
  --source . \
  --remote origin \
  --description "FP&A planning and performance management workbench" \
  --push
```

6. 推送 `main` 和 `v0.1.0` annotated tag。
7. 确认 GitHub Actions 全部通过后结束 v0.1。

`ROADMAP.md` 记录但本轮不实现：

- v0.2：模拟产品品类、CSV template upload、Base/Upside/Downside scenario editor。
- v0.3：Working capital、cash forecast、headcount planning、forecast accuracy。
- v0.4：PDF management pack、中英界面、公开同行 benchmark。
- 不在用户明确启动下一版本前扩展 v0.1 范围。
