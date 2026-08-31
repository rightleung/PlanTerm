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
  expect(workbook.getWorksheet('Executive Summary').getCell('A1').value).toContain('PlanTerm');
  expect(workbook.getWorksheet('PVM Bridge').getCell('A8').value).toBe('Reconciliation difference');
});
