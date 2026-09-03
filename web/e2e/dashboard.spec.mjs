import fs from 'node:fs/promises';
import ExcelJS from 'exceljs';
import { test, expect } from 'playwright/test';

async function openPlanningEditor(page, expectedVariant = 'base') {
  await page.getByRole('button', { name: 'Open editor' }).click();
  await expect(page.getByRole('dialog', { name: 'Planning Inputs' })).toBeVisible();
  await expect(page.getByText(new RegExp(`Showing 84 rows for ${expectedVariant} \\(252 total\\)`))).toBeVisible();
  await expect(page.getByText(/72 workforce rows/)).toBeVisible();
}

async function downloadTemplate(page) {
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download CSV' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('PlanTerm_planning_inputs.csv');
  return fs.readFile(await download.path());
}

async function uploadTemplate(page, template) {
  const responsePromise = page.waitForResponse((response) => response.url().includes('/planning-inputs/import') && response.status() === 200);
  await page.locator('input[type=file]').setInputFiles({ name: 'planning-inputs.csv', mimeType: 'text/csv', buffer: template });
  await responsePromise;
  await expect(page.getByText(/Showing 84 rows for (base|upside|downside) \(252 total\)/)).toBeVisible();
}

function parseCsvLine(line) {
  const values = [];
  let field = '';
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    const next = line[index + 1];
    if (character === '"') {
      if (quoted && next === '"') {
        field += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (character === ',' && !quoted) {
      values.push(field);
      field = '';
    } else {
      field += character;
    }
  }
  values.push(field);
  return values;
}

function findRowByFirstValue(sheet, value) {
  let found;
  sheet.eachRow((row, rowNumber) => {
    if (row.getCell(1).value === value) found = { row, rowNumber };
  });
  expect(found, `row headed ${value}`).toBeTruthy();
  return found;
}

function findRowByValues(sheet, expected) {
  let found;
  sheet.eachRow((row, rowNumber) => {
    const values = row.values.slice(1, expected.length + 1);
    if (values.every((value, index) => value === expected[index])) found = { row, rowNumber };
  });
  expect(found, `row with ${expected.join(', ')}`).toBeTruthy();
  return found;
}

function workforceFixture(variant = 'base') {
  const requiredRatio = variant === 'upside' ? 1.08 : variant === 'downside' ? 0.92 : 1;
  const variantOffset = variant === 'upside' ? 1 : variant === 'downside' ? -1 : 0;
  const periods = ['2026-07', '2026-08', '2026-09', '2026-10', '2026-11', '2026-12'];
  const businessUnits = ['MINISO - Chinese Mainland', 'MINISO - Overseas', 'TOP TOY - Global'];
  const roleRows = [
    ['store operations', 12 + variantOffset, 0.12, 120],
    ['commercial', 4, 0.2, 60],
    ['supply chain', 3, 0.18, 40],
    ['finance/support', 2, 0.22, 25],
  ];
  const headcountRows = periods.flatMap((period) => businessUnits.flatMap((businessUnit) => roleRows.map(([role, seedPlanned, monthlyCost, seedRevenue]) => {
    const isSeedRow = period === '2026-07' && businessUnit === 'MINISO - Chinese Mainland';
    const planned = isSeedRow ? seedPlanned : 0;
    const revenue = isSeedRow ? seedRevenue : 0;
    return {
      case_id: 'miniso-2026', plan_variant: variant, period, business_unit: businessUnit, role_group: role,
      planned_fte: planned, required_fte: planned * requiredRatio, monthly_loaded_cost: monthlyCost, loaded_cost: planned * monthlyCost,
      revenue, revenue_per_fte: planned > 0 ? revenue / planned : null, capacity_gap: planned * (requiredRatio - 1), productivity_basis: 'Revenue / planned FTE (RMB millions per FTE)',
      status: planned === 0 ? 'zero_capacity' : requiredRatio > 1 ? 'capacity_gap' : requiredRatio < 1 ? 'over_capacity' : 'balanced', provenance: 'calculated', input_provenance: 'synthetic_plan',
    };
  })));
  const rollups = Object.fromEntries(roleRows.map(([role, planned, monthlyCost]) => [role, {
    planned_fte: planned, required_fte: planned * requiredRatio, loaded_cost: planned * monthlyCost, capacity_gap: planned * (requiredRatio - 1), row_count: 1, provenance: 'calculated',
  }]));
  const total = roleRows.reduce((acc, [, planned, monthlyCost]) => ({
    planned_fte: acc.planned_fte + planned, required_fte: acc.required_fte + planned * requiredRatio, loaded_cost: acc.loaded_cost + planned * monthlyCost, capacity_gap: acc.capacity_gap + planned * (requiredRatio - 1),
  }), { planned_fte: 0, required_fte: 0, loaded_cost: 0, capacity_gap: 0 });
  return {
    case_id: 'miniso-2026', as_of_date: '2026-06-30', currency: 'RMB', unit: 'RMB millions unless stated otherwise', plan_variant: variant,
    headcount_rows: headcountRows, locked_rows: [{ period: '2026-06', business_unit: 'MINISO - Chinese Mainland', role_group: 'store operations', planned_fte: 12, provenance: 'synthetic_plan' }],
    rollups: { role_group: rollups, business_unit: { 'MINISO - Chinese Mainland': { ...total, row_count: 4, provenance: 'calculated' } }, role_group_business_unit: {}, portfolio: { ...total, row_count: 4, provenance: 'calculated' } },
    selected_vs_base_delta: { planned_fte: 0, required_fte: total.planned_fte * (requiredRatio - 1), loaded_cost: 0, capacity_gap: total.capacity_gap, 'store operations.loaded_cost': 0, 'commercial.loaded_cost': 0, 'supply chain.loaded_cost': 0, 'finance/support.loaded_cost': 0 },
    reconciliation_evidence: { status: 'reconciled', tolerance_rmb_millions: 0.01, residual: 0, max_residual: 0, no_double_counting: true }, provenance: 'calculated', input_provenance: 'synthetic_plan', disclosure: 'Headcount, payroll cost, and capacity are deterministic synthetic planning data; not MINISO reported or internal payroll/HRIS data.',
  };
}

function operatingPlanFixture(variant = 'base', reconciliation = { status: 'reconciled', tolerance_rmb_millions: 0.01, cash_bridge: { status: 'reconciled', max_residual: 0, }, category_rollup: { status: 'reconciled', revenue_residual: 0 } }) {
  const delta = variant === 'upside' ? 18.5 : variant === 'downside' ? -21.5 : 0;
  return {
    as_of_date: '2026-06-30',
    planning_horizon: { locked_through: '2026-06', editable_from: '2026-07', editable_to: '2026-12' },
    plan_variant: variant,
    provenance_legend: { synthetic_plan: 'Synthetic planning assumptions', calculated: 'Server-calculated output' },
    assumption_registry: { case_id: 'miniso-2026', assumption_version: 'miniso-2026@2026-06-30', git_sha: 'unavailable-local-build', provenance_labels: { public_reported: 'Public reported', synthetic_allocation: 'Synthetic allocation', synthetic_plan: 'Synthetic plan', calculated: 'Calculated' }, as_of_date: '2026-06-30', currency: 'RMB', unit: 'RMB millions' },
    decision_log: [{ decision_id: 'fixture-base-scenario', date: '2026-06-30', context: 'FY2026 base review', options: ['base', 'upside', 'downside'], decision: 'Use base plan for review', rationale: 'Fixture evidence is reconciled', owner_role: 'Group FP&A', affected_contracts: ['decision_table', 'reconciliation'], evidence: [{ metric: 'fy_revenue_delta', formula: 'selected - base', source: 'calculated fixture', provenance: 'calculated', reconciliation_status: 'reconciled' }], supersedes: null, status: 'Approved' }],
    working_capital: { unit: 'RMB millions', disclosure: 'Synthetic planning assumption; not public reported working capital.', rows: [{ case_id: 'miniso-2026', plan_variant: variant, period: '2026-12', business_unit: 'Portfolio', revenue: 100, cogs: 62, ar_days: 34, inventory_days: 51, ap_days: 42, ar_balance: 9.3, inventory_balance: 8.7, ap_balance: 7.1, nwc: 10.9, ccc: 43, provenance: 'calculated', status: 'eligible' }] },
    cash_bridge: { closing_illustrative_cash: 92.6 + delta, minimum_headroom: 12.6 + delta, disclosure: 'Illustrative cash balance; not a bank-reported cash balance.', rows: [{ case_id: 'miniso-2026', plan_variant: variant, period: '2026-12', opening_cash: 90, minimum_cash_buffer: 80, operating_profit: 20 + delta, prior_ar: 11.7, current_ar: 14.1, prior_inventory: 14, current_inventory: 17.2, current_ap: 9.5, prior_ap: 7.7, capex: 12.5, other_cash_items: -1.1, net_cash_change: 2.6 + delta, closing_illustrative_cash: 92.6 + delta, headroom: 12.6 + delta, status: 'eligible', provenance: 'calculated' }] },
    forecast_accuracy: { wape: null, bias: null, directional_hit_rate: null, eligible_periods: 0, status: 'not_eligible', provenance: 'calculated' },
    actions: [{ observation: 'Inventory cover elevated', driver: 'Inventory days', impact: -3.2, risk: 'Cash buffer pressure', action: '=Review purchase cadence', owner: 'Supply Chain', due_period: '2026-07-31', cadence: 'Monthly', provenance: 'synthetic_plan' }],
    decision_table: ['base', 'upside', 'downside'].map((planVariant) => { const planDelta = planVariant === 'upside' ? 18.5 : planVariant === 'downside' ? -21.5 : 0; return { plan_variant: planVariant, fy_revenue_delta: planDelta, fy_operating_profit_delta: planDelta, minimum_cash_month: planVariant === variant ? '2026-12' : null, cash_headroom: planVariant === variant ? 12.6 + planDelta : null, ccc: null, top_revenue_driver: 'H2 category drivers', top_profit_driver: 'Operating profit', top_cash_driver: 'Working capital', owner: 'Group FP&A', next_review_date: '2026-07-31', provenance: 'calculated' }; }),
    workforce_capacity: workforceFixture(variant),
    reconciliation,
  };
}

const responsiveViewports = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
  { width: 320, height: 568 },
];

async function assertResponsiveShell(page, viewport) {
  const evidence = await page.evaluate(() => {
    const allowedScrollOwners = ['.table-scroll', '.context-scroll', '.matrix-scroll'];
    const isAllowedScrollOwner = (element) => allowedScrollOwners.some((selector) => element.matches(selector) || element.closest(selector));
    const overflowElements = [...document.querySelectorAll('*')]
      .filter((element) => !['HTML', 'BODY'].includes(element.tagName))
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return !element.matches('.sr-only') && rect.width > 0 && rect.height > 0 && element.scrollWidth > element.clientWidth + 1;
      })
      .filter((element) => !isAllowedScrollOwner(element))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const parent = element.parentElement;
        const grandparent = parent?.parentElement;
        const describe = (node) => node ? `${node.tagName.toLowerCase()}.${node.className || ''}(${node.clientWidth}x${node.clientHeight};${getComputedStyle(node).display};${getComputedStyle(node).minWidth})` : 'none';
        return `${element.tagName.toLowerCase()}.${element.className || ''}#${element.id || ''} scroll=${element.scrollWidth} client=${element.clientWidth} rect=${Math.round(rect.x)},${Math.round(rect.y)},${Math.round(rect.width)},${Math.round(rect.height)} parent=${describe(parent)} grandparent=${describe(grandparent)}`;
      });
    const content = document.querySelector('.content')?.getBoundingClientRect();
    const cards = [...document.querySelectorAll('.kpi-card, .dashboard-stack > .panel, .dashboard-stack > .two-column > .panel, .export-row')]
      .filter((element) => getComputedStyle(element).display !== 'none')
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return { left: rect.left, right: rect.right, width: rect.width };
      });
    return {
      documentWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      viewportWidth: window.innerWidth,
      content: content ? { left: content.left, right: content.right, width: content.width } : null,
      cards,
      overflowElements,
      tableScrollOwners: [...document.querySelectorAll('.table-scroll')].map((element) => ({
        right: element.getBoundingClientRect().right,
        width: element.getBoundingClientRect().width,
        overflowX: getComputedStyle(element).overflowX,
      })),
    };
  });

  console.log(`RESPONSIVE_EVIDENCE ${viewport.width}x${viewport.height} ${JSON.stringify(evidence)}`);
  expect(evidence.viewportWidth).toBe(viewport.width);
  expect(evidence.documentWidth).toBe(evidence.clientWidth);
  expect(evidence.overflowElements, `unowned horizontal overflow at ${viewport.width}x${viewport.height}`).toEqual([]);
  expect(evidence.content?.left).toBeGreaterThanOrEqual(-1);
  expect(evidence.content?.right).toBeLessThanOrEqual(viewport.width + 1);
  for (const card of evidence.cards) {
    expect(card.left, `card left edge at ${viewport.width}x${viewport.height}`).toBeGreaterThanOrEqual((evidence.content?.left || 0) - 1);
    expect(card.right, `card right edge at ${viewport.width}x${viewport.height}`).toBeLessThanOrEqual((evidence.content?.right || viewport.width) + 1);
  }
  for (const owner of evidence.tableScrollOwners) {
    expect(owner.right).toBeLessThanOrEqual(viewport.width + 1);
    expect(owner.overflowX).toBe('auto');
  }
}

async function mockOperatingPlan(page, onPreview, onOperatingPlan, fixture = operatingPlanFixture) {
  await page.route('**/api/v1/cases/miniso-2026/operating-plan/preview', async (route) => {
    const body = route.request().postDataJSON();
    if (onPreview) await onPreview(route, body);
    else await route.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture(body.selected_plan_variant)) });
  });
  await page.route(/\/api\/v1\/cases\/miniso-2026\/operating-plan(?:\?.*)?$/, async (route) => {
    const variant = new URL(route.request().url()).searchParams.get('plan_variant') || 'base';
    if (onOperatingPlan) await onOperatingPlan(route, variant);
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture(variant)) });
  });
  await page.route('**/api/v1/cases/miniso-2026/forecast-accuracy', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(operatingPlanFixture().forecast_accuracy) });
  });
}

test('loads the offline MINISO planning case and renders the disclosure', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('PlanTerm', { exact: true })).toBeVisible();
  await expect(page.getByText('Public reported data anchors H1 Actual and Prior Year.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Monthly revenue trend' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Price / Volume / Mix' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Operating Profit bridge' })).toBeVisible();
});

test('governance decision log is add-only for the browser session and provenance is explicit', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Conclusion provenance' })).toBeVisible();
  for (const label of ['public reported', 'synthetic allocation', 'synthetic plan', 'calculated']) await expect(page.getByText(new RegExp(label, 'i')).first()).toBeVisible();
  await expect(page.getByText('assumption_version')).toBeVisible();
  await expect(page.getByText('git_sha')).toBeVisible();
  const decisionSection = page.locator('section[aria-labelledby="decision-log-title"]');
  const decisionForm = decisionSection.locator('[aria-label="Add decision"]');
  await expect(decisionSection.getByText('miniso-2026-base-scenario')).toBeVisible();
  await decisionForm.getByLabel('context').fill('July volume sensitivity');
  await decisionForm.getByLabel('options').fill('base | upside | downside');
  await decisionForm.getByLabel('decision').fill('Use base plan for review');
  await decisionForm.getByLabel('rationale').fill('Keeps the committed case anchor unchanged');
  await decisionForm.getByLabel('affected contracts').fill('decision_table | cash_bridge');
  await decisionForm.getByLabel('evidence').fill('fy_revenue_delta; selected - base; calculated; reconciled');
  await decisionForm.getByRole('button', { name: 'Add decision', exact: true }).click();
  await expect(decisionSection.getByText('July volume sensitivity')).toBeVisible();
  await expect(decisionSection.locator('tbody input, tbody textarea, tbody select')).toHaveCount(0);
  await page.reload();
  await expect(page.locator('section[aria-labelledby="decision-log-title"]').getByText('July volume sensitivity')).toHaveCount(0);
});

test('renders the empty business unit variance state', async ({ page }) => {
  await page.route('**/api/v1/cases/miniso-2026/dashboard?*', async (route) => {
    // Fetch the backend directly so this mutation does not depend on the
    // Vite proxy completing a second in-flight request under CI load.
    const response = await fetch(route.request().url().replace('http://127.0.0.1:4173', 'http://127.0.0.1:8000'));
    const payload = await response.json();
    payload.business_unit_variances = [];
    await route.fulfill({ status: response.status, contentType: 'application/json', body: JSON.stringify(payload) });
  });
  await page.goto('/');
  await expect(page.getByText('No business unit matches the selected filters')).toBeVisible();
});

test('filters update business unit rows and PVM values', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Brand').selectOption('MINISO');
  await page.getByLabel('Market').selectOption('mainland');
  const varianceRows = page.locator('section[aria-labelledby="variance-title"] tbody tr');
  await expect(varianceRows).toHaveCount(1);
  await expect(varianceRows.first()).toContainText('MINISO - Chinese Mainland');
  await expect(page.locator('section.pvm-panel').getByText('Reconciliation difference:')).toBeVisible();
  await page.getByRole('button', { name: 'Reset filters' }).click();
  await expect(varianceRows).toHaveCount(3);
});

test('disables incompatible markets and resets once on brand change', async ({ page }) => {
  let dashboardRequests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/cases/miniso-2026/dashboard?')) dashboardRequests += 1;
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Monthly revenue trend' })).toBeVisible();
  await page.getByLabel('Market').selectOption('global');
  await expect(page.getByLabel('Market')).toHaveValue('global');
  const varianceRows = page.locator('section[aria-labelledby="variance-title"] tbody tr');
  await expect(varianceRows).toHaveCount(1);
  const requestsBeforeBrandChange = dashboardRequests;
  await page.getByLabel('Brand').selectOption('MINISO');
  await expect(page.getByLabel('Market')).toHaveValue('all');
  await expect(varianceRows).toHaveCount(2);
  await expect(page.getByLabel('Market').locator('option[value="global"]')).toHaveAttribute('disabled', '');
  await expect.poll(() => dashboardRequests).toBe(requestsBeforeBrandChange + 1);
});

test('API errors are visible and recoverable', async ({ page }) => {
  let requests = 0;
  await page.route('**/api/v1/cases/miniso-2026/dashboard?*', async (route) => {
    requests += 1;
    if (requests <= 2) {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'Test failure', error_type: 'internal_server_error' }) });
    } else {
      await route.continue();
    }
  });
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Test failure');
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByRole('heading', { name: 'Monthly revenue trend' })).toBeVisible();
});

test('template download uses the frozen header and full 252-row matrix', async ({ page }) => {
  await page.goto('/');
  await openPlanningEditor(page);
  const template = await downloadTemplate(page);
  const lines = template.toString('utf8').trim().split(/\r?\n/);
  expect(lines).toHaveLength(253);
  expect(lines[0]).toBe('case_id,plan_variant,period,business_unit,category_id,volume_change_pct,average_ticket_change_pct,gross_margin_delta_pp,opex_ratio_delta_pp');
});

test('browser CSV export neutralizes text triggers and preserves numeric negatives', async ({ page }) => {
  await page.route('**/api/v1/cases/miniso-2026/planning-input-template', async (route) => {
    const response = await route.fetch();
    const lines = (await response.text()).trim().split(/\r?\n/);
    const fields = lines[1].split(',');
    fields[0] = '=SUM(A1)';
    fields[2] = '-label';
    fields[3] = '+1';
    fields[4] = '@cmd';
    fields[5] = '-0.25';
    lines[1] = fields.join(',');
    await route.fulfill({ response, body: lines.join('\n') });
  });
  await page.goto('/');
  await openPlanningEditor(page);
  const exported = await downloadTemplate(page);
  const firstRow = parseCsvLine(exported.toString('utf8').trim().split(/\r?\n/)[1]);
  expect(firstRow.slice(0, 5)).toEqual(["'=SUM(A1)", 'base', "'-label", "'+1", "'@cmd"]);
  expect(Number(firstRow[5])).toBe(-0.25);
});

test('browser CSV parser rejects empty numeric cells', async ({ page }) => {
  await page.route('**/api/v1/cases/miniso-2026/planning-input-template', async (route) => {
    const response = await route.fetch();
    const lines = (await response.text()).trim().split(/\r?\n/);
    const fields = lines[1].split(',');
    fields[5] = '   ';
    lines[1] = fields.join(',');
    await route.fulfill({ response, body: lines.join('\n') });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Open editor' }).click();
  await expect(page.getByRole('dialog', { name: 'Planning Inputs' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Invalid CSV row values');
});

test('malformed planning upload is rejected visibly', async ({ page }) => {
  await page.goto('/');
  await openPlanningEditor(page);
  const template = await downloadTemplate(page);
  const lines = template.toString('utf8').trim().split(/\r?\n/);
  lines[1] = lines[1].replace(/,[^,]+,[^,]+,[^,]+,[^,]+$/, ',NaN,NaN,NaN,NaN');
  lines[2] = lines[2].replace(/,[^,]+,[^,]+,[^,]+,[^,]+$/, ',Infinity,Infinity,Infinity,Infinity');
  const rejected = page.waitForResponse((response) => response.url().includes('/planning-inputs/import') && response.status() === 422);
  await page.locator('input[type=file]').setInputFiles({ name: 'bad.csv', mimeType: 'text/csv', buffer: Buffer.from(lines.join('\n')) });
  await rejected;
  await expect(page.getByRole('alert')).toContainText(/Invalid|finite|row/i);
});

test('valid upload previews all variants, supports edits and discard, and exports provenance', async ({ page }) => {
  await page.goto('/');
  await openPlanningEditor(page);
  const template = await downloadTemplate(page);
  await uploadTemplate(page, template);

  const workforceInput = page.getByLabel('planned_fte 2026-07 MINISO - Chinese Mainland store operations');
  const baseWorkforceValue = await workforceInput.inputValue();
  expect(Number(baseWorkforceValue)).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'upside', exact: true }).click();
  await expect(workforceInput).toHaveValue(baseWorkforceValue);
  await workforceInput.fill(String(Number(baseWorkforceValue) + 1));
  await expect(workforceInput).toHaveValue(String(Number(baseWorkforceValue) + 1));
  await page.getByRole('button', { name: 'base', exact: true }).click();
  await expect(workforceInput).toHaveValue(baseWorkforceValue);

  for (const variant of ['base', 'upside', 'downside']) {
    await page.getByRole('button', { name: variant, exact: true }).click();
    await expect(page.getByRole('button', { name: variant, exact: true })).toHaveClass(/active/);
    await expect(page.getByText(new RegExp(`Showing 84 rows for ${variant} \\(252 total\\)`))).toBeVisible();
  }

  await page.getByRole('button', { name: 'base', exact: true }).click();
  const editedInput = page.locator('input[type=number]').first();
  const originalValue = await editedInput.inputValue();
  await editedInput.fill('0.123456');
  await expect(editedInput).toHaveValue('0.123456');
  await page.getByRole('button', { name: 'Discard All' }).click();
  await expect(page.getByRole('dialog', { name: 'Planning Inputs' })).toBeHidden();

  await openPlanningEditor(page);
  await uploadTemplate(page, template);
  await page.getByRole('button', { name: 'base', exact: true }).click();
  await expect(page.locator('input[type=number]').first()).not.toHaveValue('0.123456');
  await expect(page.locator('input[type=number]').first()).toHaveValue(originalValue);
  await page.getByRole('button', { name: 'upside', exact: true }).click();
  const previewResponse = page.waitForResponse((response) => response.url().includes('/dashboard/preview') && response.status() === 200);
  await page.getByRole('button', { name: /Apply & preview/ }).click();
  await previewResponse;
  await expect(page.getByRole('dialog', { name: 'Planning Inputs' })).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Scenario comparison' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Product Category Detail' })).toBeVisible();
  await expect(page.getByText('Synthetic planning input — not reported category data').first()).toBeVisible();
  await expect(page.locator('.category-detail-panel tbody tr')).toHaveCount(98);
  let injectedPreviewCount = 0;
  await page.route('**/api/v1/cases/miniso-2026/dashboard/preview*', async (route) => {
    expect(route.request().method()).toBe('POST');
    injectedPreviewCount += 1;
    const response = await route.fetch();
    const payload = await response.json();
    const triggerValues = ['=SUM(A1)', '+1', '-label', '@cmd'];
    payload.category_detail.filter((row) => row.plan_variant === 'upside').slice(0, triggerValues.length).forEach((row, index) => { row.category_name = triggerValues[index]; });
    await route.fulfill({ response, body: JSON.stringify(payload) });
  });
  await page.getByLabel('Brand').selectOption('MINISO');
  await expect.poll(() => injectedPreviewCount).toBe(1);
  await expect(page.getByRole('heading', { name: 'Scenario comparison' })).toBeVisible();
  await expect(page.locator('.category-detail-panel tbody tr')).toHaveCount(70);
  await openPlanningEditor(page, 'upside');
  await expect(page.getByText(/Showing 84 rows for upside \(252 total\)/)).toBeVisible();
  await page.getByRole('button', { name: 'Close' }).click();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Excel management pack' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('PlanTerm_MINISO_2026H1_Management_Pack.xlsx');
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await fs.readFile(await download.path()));
  expect(workbook.worksheets.map((sheet) => sheet.name)).toEqual([
    'Executive Summary', 'Monthly Trend', 'Business Unit Variance', 'PVM Bridge', 'Assumptions & Sources', 'Product Category Detail', 'Scenario Inputs & Provenance', 'Operating Decision',
  ]);
  const provenance = workbook.getWorksheet('Scenario Inputs & Provenance');
  const selectedVariant = findRowByFirstValue(provenance, 'Selected plan variant');
  expect(selectedVariant.row.getCell(2).value).toBe('upside');
  expect(findRowByFirstValue(provenance, 'Locked horizon').row.getCell(2).value).toContain('through 2026-06');
  expect(findRowByFirstValue(provenance, 'Planning input source').row.getCell(2).value).toBe('upload');
  expect(findRowByFirstValue(provenance, 'Disclosure').row.getCell(2).value).toContain('Synthetic planning allocation');
  expect(findRowByValues(provenance, ['Category ID', 'Planning Category', 'Brand', 'Market', 'Business Unit mapping', 'Provenance'])).toBeTruthy();
  expect(findRowByFirstValue(provenance, 'Official label registry')).toBeTruthy();
  expect(findRowByValues(provenance, ['Official source label', 'Brand', 'Planning category ID', 'Source URL', 'Source period', 'Taxonomy provenance'])).toBeTruthy();
  const matrixHeader = findRowByValues(provenance, ['case_id', 'plan_variant', 'period', 'business_unit', 'category_id', 'volume_change_pct', 'average_ticket_change_pct', 'gross_margin_delta_pp', 'opex_ratio_delta_pp']);
  const inputRows = Array.from({ length: 252 }, (_, index) => provenance.getRow(matrixHeader.rowNumber + 1 + index).values.slice(1, 10));
  expect(new Set(inputRows.map((row) => row.slice(0, 5).join('|'))).size).toBe(252);
  expect(new Set(inputRows.map((row) => row[1]))).toEqual(new Set(['base', 'upside', 'downside']));
  expect(inputRows.every((row) => row.slice(5).every((value) => typeof value === 'number'))).toBe(true);
  expect(inputRows.some((row) => typeof row[5] === 'number' && row[5] < 0)).toBe(true);
  expect(provenance.autoFilter).toBeTruthy();
  [6, 7, 8, 9].forEach((column) => expect(provenance.getCell(matrixHeader.rowNumber + 1, column).numFmt).toContain('%'));
  expect(workbook.getWorksheet('PVM Bridge').getCell('B8').value).toHaveProperty('formula');
  expect(findRowByFirstValue(workbook.getWorksheet('PVM Bridge'), 'Operating profit variance').row.getCell(2).value).toHaveProperty('formula');
  expect(findRowByValues(workbook.getWorksheet('PVM Bridge'), ['Driver', 'Amount', '% of OP variance', 'Direction', 'Provenance', 'Action owner'])).toBeTruthy();
  const categorySheet = workbook.getWorksheet('Product Category Detail');
  const categoryHeader = findRowByValues(categorySheet, ['Period', 'Plan Variant', 'Business Unit', 'Category', 'Revenue', 'Revenue Mix %', 'Gross Margin %', 'Opex Ratio %', 'Operating Margin %', 'Provenance']);
  const categoryRows = Array.from({ length: categorySheet.rowCount - categoryHeader.rowNumber }, (_, index) => categorySheet.getRow(categoryHeader.rowNumber + 1 + index));
  expect(categoryRows).toHaveLength(70);
  expect(categoryRows.every((row) => row.getCell(2).value === 'upside')).toBe(true);
  expect(categoryRows[0].getCell(6).numFmt).toContain('%');
  const categoryNames = categoryRows.map((row) => row.getCell(4).value);
  expect(categoryNames).toEqual(expect.arrayContaining(["'=SUM(A1)", "'+1", "'-label", "'@cmd"]));
  expect(categoryNames.every((value) => typeof value === 'string')).toBe(true);
});

test('operating decision loads, previews selected variants, and exports safe illustrative disclosures', async ({ page }) => {
  const previewBodies = [];
  const operatingPlanVariants = [];
  await mockOperatingPlan(page, async (route, body) => {
    previewBodies.push(body);
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(operatingPlanFixture(body.selected_plan_variant)) });
  }, (_route, variant) => operatingPlanVariants.push(variant));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Working capital and illustrative cash' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Forecast accuracy' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Scenario decision table' })).toBeVisible();
  await expect(page.getByText('Synthetic planning assumptions and calculated illustrative cash - not public reported or actual cash.')).toBeVisible();
  await expect(page.getByText('not_eligible').first()).toBeVisible();
  await expect(page.getByText('Not available').first()).toBeVisible();

  await page.getByLabel('Action 1', { exact: true }).fill('Session-only action');
  await page.reload();
  await expect(page.getByLabel('Action 1', { exact: true })).toHaveValue('=Review purchase cadence');

  await openPlanningEditor(page);
  const template = await downloadTemplate(page);
  await uploadTemplate(page, template);
  await page.getByRole('button', { name: 'downside', exact: true }).click();
  const editedHeadcount = page.getByLabel('planned_fte 2026-07 MINISO - Chinese Mainland store operations');
  await editedHeadcount.fill('13');
  await expect(editedHeadcount).toHaveValue('13');
  await page.getByRole('button', { name: /Apply & preview/ }).click();
  await expect.poll(() => previewBodies.length).toBe(1);
  expect(previewBodies[0]).toMatchObject({ case_id: 'miniso-2026', selected_plan_variant: 'downside', planning_input_source: 'upload' });
  expect(previewBodies[0].rows).toHaveLength(252);
  expect(previewBodies[0].working_capital_rows).toHaveLength(1);
  expect(previewBodies[0].cash_assumption_rows).toHaveLength(1);
  expect(previewBodies[0].headcount_rows).toHaveLength(72);
  expect(previewBodies[0].headcount_rows.every((row) => row.plan_variant === 'downside')).toBe(true);
  expect(previewBodies[0].headcount_rows.find((row) => row.period === '2026-07' && row.business_unit === 'MINISO - Chinese Mainland' && row.role_group === 'store operations').planned_fte).toBe(13);
  expect(operatingPlanVariants).toContain('downside');
  expect(previewBodies[0].working_capital_rows.every((row) => row.plan_variant === 'downside')).toBe(true);
  expect(previewBodies[0].cash_assumption_rows.every((row) => row.plan_variant === 'downside')).toBe(true);
  await expect(page.getByText('Selected downside · RMB millions', { exact: true })).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Excel management pack' }).click();
  const download = await downloadPromise;
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await fs.readFile(await download.path()));
  expect(workbook.worksheets).toHaveLength(8);
  const operating = workbook.getWorksheet('Operating Decision');
  expect(operating).toBeTruthy();
  expect(findRowByFirstValue(operating, 'assumption_version').row.getCell(2).value).toBe('miniso-2026@2026-06-30');
  expect(findRowByFirstValue(operating, 'assumption_version').row.getCell(4).value).toBe('unavailable-local-build');
  expect(findRowByFirstValue(operating, 'Disclosure').row.getCell(2).value).toContain('not public reported or actual cash');
  expect(findRowByFirstValue(operating, 'Other cash').row.getCell(2).value).toBe(-1.1);
  const actionRow = findRowByFirstValue(operating, 'Inventory cover elevated');
  expect(actionRow.row.getCell(5).value).toBe("'=Review purchase cadence");
});

test('evidence-object reconciliation renders and exports residual status', async ({ page }) => {
  const fixture = (variant = 'base') => operatingPlanFixture(variant, {
    status: 'not_reconciled',
    tolerance_rmb_millions: 0.01,
    cash_bridge: { status: 'not_reconciled', max_residual: 0.75 },
    category_rollup: { status: 'not_reconciled', revenue_residual: -1.25 },
  });
  await mockOperatingPlan(page, undefined, undefined, fixture);
  await page.goto('/');
  const reconciliation = page.locator('section[aria-labelledby="operating-cash-title"] .reconciliation');
  await expect(reconciliation).toContainText('cash bridge not_reconciled');
  await expect(reconciliation).toContainText('max residual 0.8');
  await expect(reconciliation).toContainText('category roll-up not_reconciled');
  await expect(reconciliation).toContainText('revenue residual -1.3');

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Excel management pack' }).click();
  const download = await downloadPromise;
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await fs.readFile(await download.path()));
  const operating = workbook.getWorksheet('Operating Decision');
  const row = findRowByFirstValue(operating, 'Reconciliation status').row;
  expect(row.getCell(2).value).toBe('not_reconciled');
  expect(row.getCell(4).value).toBe('not_reconciled');
  expect(row.getCell(6).value).toBe(0.75);
  expect(row.getCell(8).value).toBe('not_reconciled');
  expect(row.getCell(10).value).toBe(-1.25);
  expect(row.values).not.toContain('[object Object]');
});

test('workforce capacity renders bounded role groups and exports in the operating decision sheet', async ({ page }) => {
  await mockOperatingPlan(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Workforce Capacity' })).toBeVisible();
  for (const role of ['store operations', 'commercial', 'supply chain', 'finance/support']) await expect(page.getByText(role, { exact: true })).toBeVisible();
  await expect(page.getByText(/Locked horizon through 2026-06; editable workforce planning begins 2026-07/)).toBeVisible();
  await expect(page.locator('section[aria-labelledby="workforce-capacity-title"] .reconciliation')).toContainText('no double counting');

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Excel management pack' }).click();
  const download = await downloadPromise;
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await fs.readFile(await download.path()));
  expect(workbook.worksheets).toHaveLength(8);
  const operating = workbook.getWorksheet('Operating Decision');
  expect(operating).toBeTruthy();
  expect(findRowByFirstValue(operating, 'Workforce disclosure').row.getCell(2).value).toContain('not MINISO reported');
  expect(findRowByFirstValue(operating, 'Portfolio total').row.getCell(2).value).toBe(21);
  expect(findRowByFirstValue(operating, 'Reconciliation status').row.getCell(2).value).toBe('reconciled');
  const roleSummary = findRowByFirstValue(operating, 'store operations').row;
  expect(roleSummary.getCell(2).value).toBe(12);
  expect(typeof roleSummary.getCell(2).value).toBe('number');
  expect(roleSummary.getCell(2).numFmt).toContain('#,##0.0');
  const detailHeader = findRowByValues(operating, ['Period', 'Business Unit', 'Role Group', 'Planned FTE', 'Required FTE', 'Capacity Gap', 'Loaded Cost', 'Revenue / FTE', 'Status', 'Provenance']);
  expect(operating.autoFilter).toBeTruthy();
  expect(operating.getCell(detailHeader.rowNumber + 1, 4).numFmt).toContain('#,##0.0');
  expect(operating.getRows(1, operating.rowCount).flatMap((row) => row.values)).not.toContain('[object Object]');
});

test('an older operating preview response cannot overwrite a newer selected variant', async ({ page }) => {
  let resolveFirstPreview;
  const firstPreviewReleased = new Promise((resolve) => { resolveFirstPreview = resolve; });
  let previews = 0;
  await mockOperatingPlan(page, async (route, body) => {
    previews += 1;
    if (previews === 1) {
      await firstPreviewReleased;
      try { await route.fulfill({ contentType: 'application/json', body: JSON.stringify(operatingPlanFixture(body.selected_plan_variant)) }); } catch { /* abort is expected */ }
      return;
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(operatingPlanFixture(body.selected_plan_variant)) });
  });
  await page.goto('/');
  await openPlanningEditor(page);
  const template = await downloadTemplate(page);
  await uploadTemplate(page, template);
  await page.getByRole('button', { name: 'downside', exact: true }).click();
  await page.getByRole('button', { name: /Apply & preview/ }).click();
  await expect.poll(() => previews).toBe(1);
  await openPlanningEditor(page, 'downside');
  await page.getByRole('button', { name: 'upside', exact: true }).click();
  await page.getByRole('button', { name: /Apply & preview/ }).click();
  await expect.poll(() => previews).toBe(2);
  resolveFirstPreview();
  await expect(page.getByText('Selected upside · RMB millions', { exact: true })).toBeVisible();
});

test('an older committed dashboard response cannot replace an applied preview', async ({ page }) => {
  let releaseStaleResponse;
  const staleResponseReleased = new Promise((resolve) => { releaseStaleResponse = resolve; });
  let initialResponse;
  const initialResponseCaptured = new Promise((resolve) => { initialResponse = resolve; });
  await page.route('**/api/v1/cases/miniso-2026/dashboard?*', async (route) => {
    const response = await route.fetch();
    initialResponse(response);
    await staleResponseReleased;
    try {
      await route.fulfill({ response });
    } catch {
      // Applying the preview aborts this request; cancellation may race this
      // deterministic delayed fulfill.
    }
  });

  await page.goto('/');
  await initialResponseCaptured;
  await openPlanningEditor(page);
  const template = await downloadTemplate(page);
  await uploadTemplate(page, template);
  await page.getByRole('button', { name: 'downside', exact: true }).click();
  const previewResponse = page.waitForResponse((response) => response.url().includes('/dashboard/preview') && response.status() === 200);
  await page.getByRole('button', { name: /Apply & preview/ }).click();
  const preview = await (await previewResponse).json();
  releaseStaleResponse();
  const delta = preview.scenario_comparison.revenue.delta;
  const formattedDelta = Math.abs(delta).toFixed(1).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  await expect(page.getByText(new RegExp(`^${delta >= 0 ? '\\+' : '-'}${formattedDelta.replace('.', '\\.') } vs base$`))).toBeVisible();
});

test('responsive shell has no page overflow and aligned card edges at the viewport matrix', async ({ page }) => {
  test.setTimeout(60_000);
  for (const viewport of responsiveViewports) {
    await page.setViewportSize(viewport);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Monthly revenue trend' })).toBeVisible();
    await assertResponsiveShell(page, viewport);
  }
});

test('planning dialog fits narrow viewports and keeps scroll inside labeled surfaces', async ({ page }) => {
  for (const viewport of [{ width: 1024, height: 768 }, { width: 768, height: 1024 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await page.addInitScript(() => localStorage.removeItem('planterm.locale'));
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Monthly revenue trend' })).toBeVisible();
    await openPlanningEditor(page);

    const evidence = await page.evaluate(() => {
      const dialog = document.querySelector('.planning-dialog');
      const contentScroll = document.querySelector('.planning-content-scroll');
      const matrixScrolls = [...document.querySelectorAll('.matrix-scroll')];
      const contextScroll = document.querySelector('.context-scroll');
      const rect = dialog?.getBoundingClientRect();
      return {
        bodyWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
        dialog: rect ? { left: rect.left, right: rect.right, bottom: rect.bottom } : null,
        contentOverflowY: contentScroll ? getComputedStyle(contentScroll).overflowY : null,
        matrixOverflow: matrixScrolls.map((element) => ({ overflowX: getComputedStyle(element).overflowX, overflowY: getComputedStyle(element).overflowY, right: element.getBoundingClientRect().right })),
        contextOverflow: contextScroll ? { overflowX: getComputedStyle(contextScroll).overflowX, right: contextScroll.getBoundingClientRect().right } : null,
      };
    });

    expect(evidence.bodyWidth).toBe(evidence.clientWidth);
    expect(evidence.dialog?.left).toBeGreaterThanOrEqual(-1);
    expect(evidence.dialog?.right).toBeLessThanOrEqual(viewport.width + 1);
    expect(evidence.dialog?.bottom).toBeLessThanOrEqual(viewport.height + 1);
    expect(evidence.contentOverflowY).toBe('auto');
    expect(evidence.matrixOverflow.length).toBeGreaterThanOrEqual(2);
    for (const matrix of evidence.matrixOverflow) {
      expect(matrix.overflowX).toBe('auto');
      expect(matrix.overflowY).toBe('auto');
      expect(matrix.right).toBeLessThanOrEqual(viewport.width + 1);
    }
    if (evidence.contextOverflow) {
      expect(evidence.contextOverflow.overflowX).toBe('auto');
      expect(evidence.contextOverflow.right).toBeLessThanOrEqual(viewport.width + 1);
    }
    await expect(page.getByRole('button', { name: 'Close' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Apply & preview' })).toBeVisible();

    // B-owned JSX contract: preserve these classes while adding tabindex and
    // accessible names to scroll wrappers, plus a real dialog focus trap.
    await page.getByRole('button', { name: 'Close' }).focus();
    expect(await page.evaluate(() => document.activeElement?.closest('.planning-dialog') !== null)).toBe(true);
    await page.getByRole('button', { name: 'Close' }).click();
  }
});

test('locale switcher translates, persists and safely falls back', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const selector = page.locator('header select');
  await expect(selector).toBeVisible();
  await expect(selector).toHaveAttribute('aria-label', 'Language');
  await selector.selectOption('zh-TW');
  await expect(page.getByRole('heading', { name: '組合計畫與績效' })).toBeVisible();
  await expect(selector).toHaveValue('zh-TW');
  await page.reload();
  await expect(selector).toHaveValue('zh-TW');
  await expect(page.getByRole('heading', { name: '組合計畫與績效' })).toBeVisible();

  await selector.selectOption('zh-CN');
  await expect(page.getByRole('heading', { name: '组合计划与绩效' })).toBeVisible();
  await expect(page.getByText('MINISO - 中国大陆', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('关注：MINISO - 海外 低于年初至今计划', { exact: true })).toBeVisible();
  await expect(page.getByText('门店运营', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('2026 财年基准经营计划结论', { exact: true })).toBeVisible();
  await expect(page.getByText('本次复核采用基准计划变体', { exact: true })).toBeVisible();
  await expect(page.locator('section[aria-labelledby="decision-log-title"] td').filter({ hasText: '已批准' }).first()).toBeVisible();

  await page.evaluate(() => localStorage.setItem('planterm.locale', 'fr-FR'));
  await page.reload();
  await expect(selector).toHaveValue('en');
  await expect(page.getByRole('heading', { name: 'Portfolio planning & performance' })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('planterm.locale'))).toBeNull();
});
