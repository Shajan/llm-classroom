import os
from pathlib import Path


def test_repo_layout():
    base = Path(__file__).parent
    assert (base / 'agent.py').exists()
    assert (base / 'fetchers' / 'sec.py').exists()
    assert (base / 'processing' / 'financials.py').exists()
    assert (base / 'valuation' / 'models.py').exists()
