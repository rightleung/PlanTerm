import fs from 'node:fs/promises';
import ExcelJS from 'exceljs';
import { test, expect } from 'playwright/test';

test('loads the offline MINISO planning case and renders the disclosure', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('PlanTerm', { exact: true })).toBeVisible();
  await expect(page.getByText('Public reported data anchors H1 Actual and Prior Year.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Monthly revenue trend' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Price / Volume / Mix' })).toBeVisible();
  await page.screenshot({ path: '../docs/assets/planterm-dashboard.png', fullPage: true });
});

test('filters update business unit rows and PVM values', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Brand').selectOption('MINISO');
  await page.getByLabel('Market').selectOption('mainland');
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await expect(page.locator('tbody tr').first()).toContainText('MINISO - Chinese Mainland');
  await expect(page.getByText('Reconciliation difference:')).toBeVisible();
  await page.getByRole('button', { name: 'Reset filters' }).click();
  await expect(page.locator('tbody tr')).toHaveCount(3);
});

test('disables incompatible markets and resets once on brand change', async ({ page }) => {
  let dashboardRequests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/cases/miniso-2026/dashboard')) dashboardRequests += 1;
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Monthly revenue trend' })).toBeVisible();
  await page.getByLabel('Market').selectOption('global');
  await expect(page.getByLabel('Market')).toHaveValue('global');
  await expect(page.locator('tbody tr')).toHaveCount(1);
  const requestsBeforeBrandChange = dashboardRequests;
  await page.getByLabel('Brand').selectOption('MINISO');
  await expect(page.getByLabel('Market')).toHaveValue('all');
  await expect(page.locator('tbody tr')).toHaveCount(2);
  await expect(page.getByLabel('Market').locator('option[value="global"]')).toHaveAttribute('disabled', '');
  await expect.poll(() => dashboardRequests).toBe(requestsBeforeBrandChange + 1);
});

test('API errors are visible and recoverable', async ({ page }) => {
  let requests = 0;
  await page.route('**/api/v1/cases/miniso-2026/dashboard*', async (route) => {
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

test('Excel management pack downloads five verified worksheets', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Brand').selectOption('MINISO');
  await page.getByLabel('Market').selectOption('overseas');
  await expect(page.locator('tbody tr')).toHaveCount(1);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Excel management pack' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('PlanTerm_MINISO_2026H1_Management_Pack.xlsx');
  const filePath = await download.path();
  expect(filePath).toBeTruthy();
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await fs.readFile(filePath));
  expect(workbook.worksheets.map((sheet) => sheet.name)).toEqual([
    'Executive Summary', 'Monthly Trend', 'Business Unit Variance', 'PVM Bridge', 'Assumptions & Sources',
  ]);
  const summary = workbook.getWorksheet('Executive Summary');
  const trend = workbook.getWorksheet('Monthly Trend');
  const variance = workbook.getWorksheet('Business Unit Variance');
  const pvm = workbook.getWorksheet('PVM Bridge');
  const assumptions = workbook.getWorksheet('Assumptions & Sources');
  expect(summary.getCell('A1').value).toContain('PlanTerm');
  expect(summary.getCell('A6').value).toBe('KPI');
  expect(summary.getCell('D7').value).toMatchObject({ formula: expect.stringContaining('B7-C7'), result: expect.any(Number) });
  expect(summary.getCell('E7').numFmt).toContain('%');
  expect(summary.getCell('K7').fill.fgColor.argb).toBeTruthy();
  expect(summary.views[0].ySplit).toBe(6);
  expect(summary.autoFilter).toBe('A6:K6');
  expect(trend.getCell('A2').value).toBe('Period');
  expect(trend.views[0].ySplit).toBe(2);
  expect(variance.getCell('A2').value).toBe('Business Unit');
  expect(variance.getRow(3).getCell(1).value).toBe('MINISO - Overseas');
  expect(variance.rowCount).toBe(3);
  expect(variance.getCell('J3').value).toMatchObject({ formula: expect.stringContaining('H3-I3'), result: expect.any(Number) });
  expect(variance.getCell('O3').value).toBeTruthy();
  expect(pvm.getCell('A8').value).toBe('Reconciliation difference');
  expect(pvm.getCell('B8').value).toMatchObject({ formula: 'SUM(B5:B7)-(B3-B4)', result: expect.any(Number) });
  expect(assumptions.getCell('A2').value).toBe('Source type');
  expect(assumptions.getColumn(3).width).toBeGreaterThan(50);
});
