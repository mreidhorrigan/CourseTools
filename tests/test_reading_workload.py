import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("workload",ROOT/"scripts/audit_reading_workload.py")
MOD=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)

def test_workload_config_covers_thirteen_weeks_and_pages():
    config=MOD.load_jsonc(ROOT/"course/reading-workload.config.jsonc")
    assert set(config["weeks"])=={str(n) for n in range(1,14)}
    results=MOD.calculate(config)
    assert all((ROOT/r["page"]).exists() for r in results.values())
    assert all(r["words"] >= 0 and r["total_minutes"] > 0 for r in results.values())
    assert all(r["total_minutes"] == 450 for r in results.values())
    assert all(sum(r["allocation"].values()) == r["other_minutes"] for r in results.values())

def test_generated_workload_blocks_are_current():
    config=MOD.load_jsonc(ROOT/"course/reading-workload.config.jsonc")
    assert MOD.update(config,MOD.calculate(config),check=True)==[]
    for result in MOD.calculate(config).values():
        source=(ROOT/result["page"]).read_text(encoding="utf-8")
        assert source.count('class="weekly-workload"') == 1
