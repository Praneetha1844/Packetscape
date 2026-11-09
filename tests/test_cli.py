from __future__ import annotations

from pathlib import Path

import pytest

from packetscape.cli import main

SCENARIO = (
    "seed: 5\n"
    "duration: 3\n"
    "nodes: [a, b]\n"
    "links:\n"
    "  - {a: a, b: b, bandwidth_mbps: 10, delay_ms: 2}\n"
    "flows:\n"
    "  - {id: f, src: a, dst: b, kind: tcp, packets: 10}\n"
)


@pytest.fixture
def scenario(tmp_path: Path) -> Path:
    path = tmp_path / "demo.yaml"
    path.write_text(SCENARIO, encoding="utf-8")
    return path


def test_validate_accepts_a_good_file(scenario: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(scenario)]) == 0
    assert "OK" in capsys.readouterr().out


def test_run_prints_summary_and_writes_csv(
    scenario: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    assert main(["run", str(scenario), "--out", str(out)]) == 0
    assert "Jain fairness index" in capsys.readouterr().out
    assert (out / "flows.csv").read_text(encoding="utf-8").startswith("flow_id,kind")
    assert (out / "cwnd.csv").exists()


def test_seed_override_is_applied(scenario: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", str(scenario), "--seed", "99"]) == 0
    assert "seed=99" in capsys.readouterr().out


def test_missing_file_returns_error_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", str(tmp_path / "nope.yaml")]) == 2
    assert "error:" in capsys.readouterr().err


def test_plots_flag_requires_output_directory(
    scenario: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", str(scenario), "--plots"]) == 2
    assert "--out" in capsys.readouterr().err
