"""End-to-end tests on the eToro example: engine, Excel parity, CLI."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from openpyxl import load_workbook

from erkit.cases import Case
from erkit.cli import main
from erkit.config import load_config
from erkit.excel import export_workbook
from erkit.valuation import implied_discount_rate, per_share_value, value_company

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "etoro.yaml"


@pytest.fixture(scope="module")
def cfg():
    return load_config(EXAMPLE)


@pytest.fixture(scope="module")
def result(cfg):
    return value_company(cfg)


def test_etoro_is_case_2(result):
    assert result.case is Case.PROFITABLE
    assert result.weights == {"comps": 0.5, "dcf": 0.5}


def test_cost_of_capital(result):
    assert result.beta == pytest.approx(1.7236, abs=1e-4)
    assert result.wacc == pytest.approx(0.0494 + 1.7236 * 0.0428, abs=1e-6)


def test_scenarios_are_ordered(result):
    v = {s.scenario.name: s.per_share for s in result.scenarios}
    assert v["bear"] < v["base"] < v["bull"]


def test_robinhood_excluded_from_ev_ebitda(result):
    (ev_ebitda,) = [c for c in result.comps if c.stats.multiple == "ev_ebitda"]
    assert "HOOD" in ev_ebitda.stats.excluded
    assert "pe" in result.skipped_multiples  # only one peer reports P/E


def test_reverse_dcf_recovers_the_price(cfg):
    r = implied_discount_rate(cfg)
    assert r is not None
    assert per_share_value(cfg, cfg.forecast.base, r) == pytest.approx(cfg.company.price, abs=1e-3)


def test_blend_and_rating_consistent(result):
    expected = 0.5 * result.dcf_per_share + 0.5 * result.comps_per_share
    assert result.blended_per_share == pytest.approx(expected)
    assert result.rating in {"BUY", "HOLD", "SELL"}


def test_workbook_has_live_formulas(result, tmp_path):
    path = export_workbook(result, tmp_path / "etor.xlsx")
    ws = load_workbook(path)["DCF"]
    assert str(ws["C6"].value).startswith("=")  # revenue is a formula
    assert ws["B22"].value == "=B19+B21"  # EV
    assert ws["B28"].value == "=B27/shares"


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice not installed")
def test_excel_recalculates_to_python_value(result, tmp_path):
    src = export_workbook(result, tmp_path / "etor.xlsx")
    outdir = tmp_path / "recalc"
    subprocess.run(
        ["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(outdir), str(src)],
        check=True,
        capture_output=True,
        timeout=180,
    )
    ws = load_workbook(outdir / "etor.xlsx", data_only=True)["DCF"]
    assert ws["B22"].value == pytest.approx(result.base.dcf.enterprise_value, rel=1e-9)
    assert ws["B28"].value == pytest.approx(result.base.per_share, rel=1e-9)


def test_cli_writes_all_outputs(tmp_path, capsys):
    assert main(["value", str(EXAMPLE), "--out", str(tmp_path)]) == 0
    for name in ("etor_valuation.xlsx", "etor_football_field.png", "etor_summary.md", "etor_valuation.json"):
        assert (tmp_path / name).exists()
    data = json.loads((tmp_path / "etor_valuation.json").read_text())
    assert data["case"] == "case_2_profitable"
    assert "BUY" in capsys.readouterr().out or data["rating"] in {"HOLD", "SELL"}


def test_high_growth_template_uses_case_1():
    tmpl = EXAMPLE.parent / "template_high_growth.yaml"
    r = value_company(load_config(tmpl))
    assert r.case is Case.HIGH_GROWTH
    assert r.weights == {"comps": 0.6, "dcf": 0.4}
    # margin path converged before the terminal year
    assert r.base.scenario.ebit_margin[-1] == pytest.approx(0.18)
    assert r.base.scenario.ebit_margin[-2] == pytest.approx(0.18)
