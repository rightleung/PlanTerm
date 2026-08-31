from pathlib import Path

import pytest

from src.repositories.case_repository import CaseRepository


@pytest.fixture()
def case():
    return CaseRepository(Path(__file__).parents[1] / "data" / "cases").get_case("miniso-2026")

