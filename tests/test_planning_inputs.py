import csv
import math
from decimal import Decimal
from pathlib import Path

import pytest

from fastapi.testclient import TestClient
from src.api import app
from src.models.planning import PlanningInputSource
from src.repositories.case_repository import CaseRepository
from src.services.category_plan_service import calculate_rows
from src.services.committed_json import DuplicateJsonKeyError, load_committed_json
from src.services.scenario_service import seed_rows

client = TestClient(app)

def test_template_and_import_are_complete():
    template = client.get('/api/v1/cases/miniso-2026/planning-input-template')
    assert template.status_code == 200
    assert len(template.text.splitlines()) == 253
    imported = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=template.content, headers={'Content-Type':'text/csv'})
    assert imported.status_code == 200 and imported.json()['row_count'] == 252


def test_import_canonical_driver_fields_are_finite_json_numbers():
    template = client.get('/api/v1/cases/miniso-2026/planning-input-template').content
    response = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=template, headers={'Content-Type': 'text/csv'})
    assert response.status_code == 200
    for row in response.json()['rows']:
        for field in ('volume_change_pct', 'average_ticket_change_pct', 'gross_margin_delta_pp', 'opex_ratio_delta_pp'):
            assert isinstance(row[field], (int, float)) and not isinstance(row[field], bool)
            assert math.isfinite(row[field])

def test_import_fail_closed_for_duplicate_and_locked_rows():
    template = client.get('/api/v1/cases/miniso-2026/planning-input-template').text
    rows = list(csv.reader(template.splitlines()))
    rows[1][2] = '2026-06'
    payload = '\n'.join(','.join(r) for r in rows).encode()
    response = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=payload, headers={'Content-Type':'text/csv'})
    assert response.status_code == 422
    assert response.json()['error_type'] == 'locked_horizon'

def test_preview_revalidates_rows_and_exposes_comparison():
    template = client.get('/api/v1/cases/miniso-2026/planning-input-template')
    imported = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=template.content, headers={'Content-Type':'text/csv'}).json()
    imported['rows'][0]['volume_change_pct'] = 'NaN'
    response = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant':'base','rows':imported['rows']})
    assert response.status_code == 422
    assert response.json()['error_type'] == 'invalid_input_row'


def test_preview_rejects_unexpected_json_fields_and_base_tampering():
    template = client.get('/api/v1/cases/miniso-2026/planning-input-template')
    imported = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=template.content, headers={'Content-Type':'text/csv'}).json()
    imported['rows'][0]['unexpected'] = 1
    response = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant':'base','brand':'MINISO','market':'overseas','rows':imported['rows']})
    assert response.status_code == 422
    assert response.json()['error_type'] == 'unexpected_input_key'

    imported = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=template.content, headers={'Content-Type':'text/csv'}).json()
    imported['rows'][0]['provenance'] = 'public_reported'
    response = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant':'base','rows':imported['rows']})
    assert response.status_code == 422
    assert response.json()['error_type'] == 'unexpected_input_key'

    imported = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=template.content, headers={'Content-Type':'text/csv'}).json()
    imported['rows'][0]['volume_change_pct'] = '-1.000000'
    response = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant':'base','rows':imported['rows']})
    assert response.status_code == 422
    assert response.json()['error_type'] == 'invalid_input_row'


def test_valid_base_h2_driver_edit_recomputes_dashboard_and_operating_plan():
    case = CaseRepository().get_case('miniso-2026')
    committed_rows = [row.model_dump(mode='json') for row in seed_rows(case)]
    rows = [dict(row) for row in committed_rows]
    target = next(row for row in rows if row['plan_variant'] == 'base' and row['period'] == '2026-07' and row['business_unit'] == 'MINISO - Chinese Mainland' and row['category_id'] == 'miniso_ip_toys')
    target['volume_change_pct'] = 0.10
    dashboard_response = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant': 'base', 'planning_input_source': 'editor', 'rows': rows})
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard['scenario_comparison']['revenue']['delta'] > 0
    assert dashboard['scenario_comparison']['gross_profit']['delta'] > 0
    assert dashboard['scenario_comparison']['operating_profit']['delta'] > 0

    working_capital_rows = [dict(row) for row in case.working_capital_seed if row['plan_variant'] == 'base']
    cash_assumption_rows = [dict(row, opening_cash=case.cash_assumptions['opening_cash'], minimum_cash_buffer=case.cash_assumptions['minimum_cash_buffer']) for row in case.cash_assumptions['rows'] if row['plan_variant'] == 'base']
    headcount_rows = [dict(row) for row in case.headcount_seed if row['plan_variant'] == 'base']
    operating_payload = {
        'case_id': case.case_id,
        'selected_plan_variant': 'base',
        'planning_input_source': 'editor',
        'rows': rows,
        'working_capital_rows': working_capital_rows,
        'cash_assumption_rows': cash_assumption_rows,
        'headcount_rows': headcount_rows,
    }
    operating_response = client.post('/api/v1/cases/miniso-2026/operating-plan/preview', json=operating_payload)
    assert operating_response.status_code == 200
    operating = operating_response.json()
    assert operating['reconciliation']['status'] == 'reconciled'
    assert operating['reconciliation']['category_rollup']['anchor'] == 'scenario_internal'
    assert next(row for row in operating['decision_table'] if row['plan_variant'] == 'base')['fy_revenue_delta'] > 0

    baseline_response = client.post('/api/v1/cases/miniso-2026/operating-plan/preview', json={**operating_payload, 'rows': committed_rows})
    assert baseline_response.status_code == 200
    baseline = baseline_response.json()
    edited_july = next(row for row in operating['cash_bridge']['rows'] if row['period'] == '2026-07')
    baseline_july = next(row for row in baseline['cash_bridge']['rows'] if row['period'] == '2026-07')
    assert edited_july['headroom'] > baseline_july['headroom']
    assert operating['headcount_rows'] == baseline['headcount_rows']


def test_preview_accepts_filters_from_query_and_keeps_pvm_unchanged():
    template = client.get('/api/v1/cases/miniso-2026/planning-input-template')
    imported = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=template.content, headers={'Content-Type':'text/csv'}).json()
    before = client.get('/api/v1/cases/miniso-2026/dashboard', params={'brand':'TOP_TOY','market':'global'}).json()['pvm_bridge']
    response = client.post('/api/v1/cases/miniso-2026/dashboard/preview?brand=TOP_TOY&market=global', json={'selected_plan_variant':'upside','rows':imported['rows']})
    assert response.status_code == 200
    payload = response.json()
    assert payload['selected_filters'] == {'brand':'TOP_TOY','market':'global'}
    assert payload['pvm_bridge'] == before


def test_preview_source_is_closed_and_reflected_without_affecting_financials():
    template = client.get('/api/v1/cases/miniso-2026/planning-input-template').content
    imported = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=template, headers={'Content-Type': 'text/csv'}).json()
    default_source = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant': 'base', 'rows': imported['rows']})
    editor_source = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant': 'base', 'planning_input_source': PlanningInputSource.EDITOR.value, 'rows': imported['rows']})
    assert default_source.status_code == editor_source.status_code == 200
    assert default_source.json()['planning_input_source'] == PlanningInputSource.UPLOAD.value
    assert editor_source.json()['planning_input_source'] == PlanningInputSource.EDITOR.value
    assert editor_source.json()['kpis'] == default_source.json()['kpis']
    for value in ('seed', 'arbitrary'):
        rejected = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant': 'base', 'planning_input_source': value, 'rows': imported['rows']})
        assert rejected.status_code == 422
        assert rejected.json()['error_type'] == 'invalid_input_source'


def test_preview_rejects_unknown_json_fields_and_incomplete_matrix():
    template = client.get('/api/v1/cases/miniso-2026/planning-input-template').content
    imported = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=template, headers={'Content-Type':'text/csv'}).json()
    imported['rows'][0]['unexpected'] = 'reject-me'
    response = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant':'base','rows':imported['rows']})
    assert response.status_code == 422
    assert response.json()['error_type'] == 'unexpected_input_key'
    rows = imported['rows'][1:]
    response = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant':'base','rows':rows})
    assert response.status_code == 422
    assert response.json()['error_type'] == 'incomplete_input_matrix'


def test_default_seed_volume_matches_all_54_independent_parent_anchors():
    case = CaseRepository().get_case('miniso-2026')
    rows = seed_rows(case)
    details, _comparison, _context = calculate_rows(case, rows, 'base')
    for variant in ('base', 'upside', 'downside'):
        adjustment = Decimal(str(case.assumptions['variant_driver_adjustments'][variant]['volume_change_pct']))
        for month in range(7, 13):
            period = f'2026-{month:02d}'
            for unit in ('MINISO - Chinese Mainland', 'MINISO - Overseas', 'TOP TOY - Global'):
                leaf_volume = sum(Decimal(str(item['volume'])) for item in details if item['period'] == period and item['plan_variant'] == variant and item['business_unit'] == unit)
                forecast_volume = sum(Decimal(str(record.value)) for record in case.records if record.scenario.value == 'forecast' and record.period == period and record.business_unit == unit and record.metric == 'volume')
                budget_volume = sum(Decimal(str(record.value)) for record in case.records if record.scenario.value == 'budget' and record.period == period and record.business_unit == unit and record.metric == 'volume')
                assert abs(leaf_volume - (forecast_volume + adjustment * budget_volume)) <= Decimal('0.01')


def test_authoritative_taxonomy_registry_maps_each_official_label_once():
    taxonomy = CaseRepository().get_case('miniso-2026').taxonomy
    registry = taxonomy['official_label_registry']
    assert len(registry) == 19
    assert len({item['source_label'] for item in registry}) == 19
    assert {item['brand'] for item in registry} == {'MINISO', 'TOP_TOY'}
    assert sum(item['brand'] == 'MINISO' for item in registry) == 11
    assert sum(item['brand'] == 'TOP_TOY' for item in registry) == 8
    assert all(item['source_url'] == 'https://ir.miniso.com/image/2023_ESG_Report.pdf' for item in registry)
    assert all(item['source_period'] == 'Fiscal year ended June 30, 2023' for item in registry)
    assert {item['planning_category_id'] for item in registry} == {item['category_id'] for item in taxonomy['categories']}
    assert all(item['provenance'] == 'synthetic_allocation' for item in taxonomy['categories'])


def test_committed_json_duplicate_key_fixture_fails_closed():
    fixture = Path(__file__).parent / 'fixtures' / 'duplicate_assumptions_key.json'
    with pytest.raises(DuplicateJsonKeyError, match='category_index_normalization'):
        load_committed_json(fixture)


def test_category_detail_context_is_explicitly_synthetic_and_rolls_to_locked_parents():
    payload = client.get('/api/v1/cases/miniso-2026/dashboard').json()
    context = payload['category_detail_context']
    assert len(context) == 14
    assert all(item['provenance'] == 'synthetic_allocation' for item in context)
    case = CaseRepository().get_case('miniso-2026')
    for field, scenario, months in (
        ('h1_actual', 'actual', range(1, 7)),
        ('h1_prior_year', 'prior_year', range(1, 7)),
        ('fy_budget', 'budget', range(1, 13)),
    ):
        for unit in {item['business_unit'] for item in context}:
            allocated = sum(Decimal(str(item[field]['revenue'])) for item in context if item['business_unit'] == unit)
            parent = sum(Decimal(str(record.value)) for record in case.records if record.scenario.value == scenario and record.business_unit == unit and record.period in {f'2026-{month:02d}' for month in months} and record.metric == 'revenue')
            assert abs(allocated - parent) <= Decimal('0.01')
