import fs from 'node:fs/promises';
import ExcelJS from 'exceljs';
import { test, expect } from 'playwright/test';

async function openPlanningEditor(page, expectedVariant = 'base') {
  await page.getByRole('button', { name: 'Open editor' }).click();
  await expect(page.getByRole('dialog', { name: 'Planning Inputs' })).toBeVisible();
  await expect(page.getByText(new RegExp(`Showing 84 rows for ${expectedVariant} \\(252 total\\)`))).toBeVisible();
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

test('loads the offline MINISO planning case and renders the disclosure', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('PlanTerm', { exact: true })).toBeVisible();
  await expect(page.getByText('Public reported data anchors H1 Actual and Prior Year.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Monthly revenue trend' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Price / Volume / Mix' })).toBeVisible();
});

test('filters update business unit rows and PVM values', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Brand').selectOption('MINISO');
  await page.getByLabel('Market').selectOption('mainland');
  const varianceRows = page.locator('section[aria-labelledby="variance-title"] tbody tr');
  await expect(varianceRows).toHaveCount(1);
  await expect(varianceRows.first()).toContainText('MINISO - Chinese Mainland');
  await expect(page.getByText('Reconciliation difference:')).toBeVisible();
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
  await page.getByLabel('Brand').selectOption('MINISO');
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
    'Executive Summary', 'Monthly Trend', 'Business Unit Variance', 'PVM Bridge', 'Assumptions & Sources', 'Product Category Detail', 'Scenario Inputs & Provenance',
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
  expect(provenance.autoFilter).toBeTruthy();
  [6, 7, 8, 9].forEach((column) => expect(provenance.getCell(matrixHeader.rowNumber + 1, column).numFmt).toContain('%'));
  expect(workbook.getWorksheet('PVM Bridge').getCell('B8').value).toHaveProperty('formula');
  const categorySheet = workbook.getWorksheet('Product Category Detail');
  const categoryHeader = findRowByValues(categorySheet, ['Period', 'Plan Variant', 'Business Unit', 'Category', 'Revenue', 'Revenue Mix %', 'Gross Margin %', 'Opex Ratio %', 'Operating Margin %', 'Provenance']);
  const categoryRows = Array.from({ length: categorySheet.rowCount - categoryHeader.rowNumber }, (_, index) => categorySheet.getRow(categoryHeader.rowNumber + 1 + index));
  expect(categoryRows).toHaveLength(70);
  expect(categoryRows.every((row) => row.getCell(2).value === 'upside')).toBe(true);
  expect(categoryRows[0].getCell(6).numFmt).toContain('%');
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
  await expect(page.getByText(`${delta >= 0 ? '+' : ''}${delta.toFixed(1)} vs base`)).toBeVisible();
});
