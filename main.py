from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from buy_or_wait.engine import FinancialEngine
from buy_or_wait.loaders import Dataset, repo_root_from_code
from buy_or_wait.validator import validate_output_file


def main() -> int:
    root = repo_root_from_code()
    ds = Dataset(root)
    engine = FinancialEngine(ds)
    recs = engine.run_requests(ds.requests)
    rows = [engine.output_row(r) for r in recs]
    output_path = root / "output.csv"
    engine.write_output(rows, output_path)
    errors = validate_output_file(output_path, ds.requests)
    eval_dir = root / "evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)
    usage = eval_dir / "usage_report.md"
    usage.write_text(
        "# Usage Report\n\n"
        "Final full-dataset run used deterministic local Python logic only.\n\n"
        "| provider | model | calls | input tokens | output tokens | total tokens | estimated cost |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n"
        "| none | none | 0 | 0 | 0 | 0 | 0 |\n\n"
        f"Requests processed: {len(ds.requests)}\n\n"
        "Average tokens/request: 0\n\n"
        "Estimated average cost/request: 0\n",
        encoding="utf-8",
    )
    report = {
        "processed": len(rows),
        "validation_errors": errors,
        "output": str(output_path),
    }
    (eval_dir / "validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (eval_dir / "validation_report.md").write_text(
        "# Validation Report\n\n"
        f"Processed: {len(rows)}\n\n"
        f"Validation failures: {len(errors)}\n\n"
        + ("\n".join(f"- {e}" for e in errors) if errors else "No schema validation failures.\n"),
        encoding="utf-8",
    )
    if errors:
        for err in errors:
            print(f"VALIDATION: {err}")
        return 1
    print(f"Wrote {output_path} with {len(rows)} rows")
    print(f"Wrote {usage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
