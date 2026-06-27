#!/usr/bin/env python3
"""Build an HTML and CSV report from the Fast Downward benchmark outputs."""

from __future__ import annotations

import argparse
import csv
import html
import re
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path


FLOAT = r"([0-9]+(?:\.[0-9]+)?)"


@dataclass
class Result:
    problem: str
    configuration: str
    status: str
    failure_phase: str
    failure_reason: str
    translation_seconds: float | None
    search_seconds: float | None
    planner_seconds: float | None
    plan_length: int | None
    log_path: str
    plan_path: str

    @property
    def solved(self) -> bool:
        return self.status.startswith("solved")


def last_match(pattern: str, text: str, flags: int = 0) -> str | None:
    matches = re.findall(pattern, text, flags)
    if not matches:
        return None
    value = matches[-1]
    return value[0] if isinstance(value, tuple) else value


def plan_length(plan_path: Path, text: str) -> int | None:
    logged = last_match(r"Plan length:\s*(\d+)\s+step", text)
    if logged is not None:
        return int(logged)
    if not plan_path.exists():
        return None
    return sum(
        1
        for line in plan_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip().startswith("(")
    )


def failure_reason(text: str) -> str:
    lower = text.lower()
    if "time limit has been reached" in lower or "caught signal 24" in lower:
        return "time limit"
    if "memory limit" in lower and ("memoryerror" in lower or "std::bad_alloc" in lower):
        return "memory limit"
    if "unsolvable" in lower or "completely explored state space" in lower:
        return "unsolvable"
    code = last_match(r"(?:translate|search) exit code:\s*(-?\d+)", text)
    return f"exit code {code}" if code and code != "0" else "incomplete log"


def parse_result(log_path: Path, root: Path) -> Result:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    configuration = log_path.parent.name
    problem = log_path.name.removesuffix("_log.txt")
    plan_path = log_path.with_name(f"{problem}_plan")

    translation = last_match(r"Done!\s*\[[^\]]*?" + FLOAT + r"s wall-clock\]", text)
    search = last_match(r"^\[t=[^\]]+\]\s*Search time:\s*" + FLOAT + r"s", text, re.MULTILINE)
    planner = last_match(r"INFO\s+Planner time:\s*" + FLOAT + r"s", text)
    translate_code = last_match(r"translate exit code:\s*(-?\d+)", text)
    search_code = last_match(r"search exit code:\s*(-?\d+)", text)

    solution_found = "Solution found." in text
    solved = translate_code == "0" and search_code == "0" and solution_found

    if solved:
        status = "solved"
        phase = ""
        reason = ""
    elif translate_code is None or translate_code != "0":
        status = "failed"
        phase = "translation"
        reason = failure_reason(text)
    elif search_code is None or search_code != "0":
        status = "failed"
        phase = "search"
        reason = failure_reason(text)
    else:
        status = "failed"
        phase = "unknown"
        reason = failure_reason(text)

    return Result(
        problem=problem,
        configuration=configuration,
        status=status,
        failure_phase=phase,
        failure_reason=reason,
        translation_seconds=float(translation) if translation else None,
        search_seconds=float(search) if search else None,
        planner_seconds=float(planner) if planner else None,
        plan_length=plan_length(plan_path, text) if solved else None,
        log_path=log_path.relative_to(root).as_posix(),
        plan_path=plan_path.relative_to(root).as_posix() if solved and plan_path.exists() else "",
    )


def problem_key(name: str) -> tuple[int, int, str]:
    family_order = {"small": 0, "large": 1, "hard": 2}
    match = re.fullmatch(r"([^_]+)_(\d+)", name)
    if not match:
        return (99, 99, name)
    return (family_order.get(match.group(1), 98), int(match.group(2)), name)


def fmt_time(value: float | None) -> str:
    if value is None:
        return "-"
    if value < 0.01:
        return f"{value:.4f}s"
    if value < 10:
        return f"{value:.3f}s"
    return f"{value:.2f}s"


def link(path: str, label: str) -> str:
    return f'<a href="{html.escape(path, quote=True)}">{html.escape(label)}</a>' if path else ""


def result_cell(result: Result) -> str:
    if result.solved:
        timing = f"T {fmt_time(result.translation_seconds)} / S {fmt_time(result.search_seconds)}"
        length = f"L {result.plan_length}" if result.plan_length is not None else "L -"
        warning = '<span class="warning">incomplete log</span>' if "incomplete" in result.status else ""
        return f'<td class="solved"><strong>Solved</strong><small>{timing}<br>{length} {warning}</small></td>'
    phase = result.failure_phase.title() or "Unknown"
    translation = (
        f"<br>T {fmt_time(result.translation_seconds)}" if result.failure_phase == "search" else ""
    )
    return (
        f'<td class="failed"><strong>{html.escape(phase)} failed</strong>'
        f'<small>{html.escape(result.failure_reason)}{translation}</small></td>'
    )


def markdown_cell(result: Result | None) -> str:
    if result is None:
        return "No log"
    if result.solved:
        label = f"[Solved]({result.plan_path})" if result.plan_path else "Solved"
        length = result.plan_length if result.plan_length is not None else "-"
        return (
            f":green_circle: {label}<br>T {fmt_time(result.translation_seconds)}<br>"
            f"S {fmt_time(result.search_seconds)}<br>L {length}"
        )
    label = f"[{result.failure_phase.title()} failed]({result.log_path})"
    translation = (
        f"<br>T {fmt_time(result.translation_seconds)}"
        if result.failure_phase == "search"
        else ""
    )
    return f":red_circle: {label}<br>{result.failure_reason}{translation}"


def build_markdown(results: list[Result], output: Path) -> None:
    configurations = sorted({r.configuration for r in results})
    problems = sorted({r.problem for r in results}, key=problem_key)
    lookup = {(r.problem, r.configuration): r for r in results}

    lines = [
        "# Planner benchmark results",
        "",
        "Generated from `problem_outputs/`. T = translation wall-clock time, "
        "S = Fast Downward search time, and L = plan length.",
        "",
        f"**{len(problems)} problems | {len(configurations)} configurations | {len(results)} runs**",
        "",
        "## Configuration summary",
        "",
        "| Configuration | Solved | Mean search time | Translation failures | Search failures |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for config in configurations:
        selected = [r for r in results if r.configuration == config]
        solved = [r for r in selected if r.solved]
        search_times = [r.search_seconds for r in solved if r.search_seconds is not None]
        lines.append(
            f"| `{config}` | {len(solved)} / {len(selected)} | "
            f"{fmt_time(statistics.mean(search_times) if search_times else None)} | "
            f"{sum(r.failure_phase == 'translation' for r in selected)} | "
            f"{sum(r.failure_phase == 'search' for r in selected)} |"
        )

    for family in ("small", "large", "hard"):
        family_problems = [p for p in problems if p.startswith(f"{family}_")]
        if not family_problems:
            continue
        lines.extend(
            [
                "",
                f"## {family.title()} problems",
                "",
                "| Problem | " + " | ".join(f"`{config}`" for config in configurations) + " |",
                "| --- | " + " | ".join("---" for _ in configurations) + " |",
            ]
        )
        for problem in family_problems:
            cells = [markdown_cell(lookup.get((problem, config))) for config in configurations]
            lines.append(f"| **{problem}** | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "Times unavailable in a log are shown as `-`. Mean search time only includes "
            "successful runs.",
            "",
            "For filtering and a detailed run table, open `planner_results.html` locally.",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_html(results: list[Result], output: Path) -> None:
    configurations = sorted({r.configuration for r in results})
    problems = sorted({r.problem for r in results}, key=problem_key)
    lookup = {(r.problem, r.configuration): r for r in results}

    summary_rows = []
    for config in configurations:
        selected = [r for r in results if r.configuration == config]
        solved = [r for r in selected if r.solved]
        search_times = [r.search_seconds for r in solved if r.search_seconds is not None]
        summary_rows.append(
            "<tr>"
            f"<th>{html.escape(config)}</th>"
            f"<td>{len(solved)} / {len(selected)}</td>"
            f"<td>{fmt_time(statistics.mean(search_times) if search_times else None)}</td>"
            f"<td>{sum(r.failure_phase == 'translation' for r in selected)}</td>"
            f"<td>{sum(r.failure_phase == 'search' for r in selected)}</td>"
            "</tr>"
        )

    matrices = []
    for family in ("small", "large", "hard"):
        family_problems = [p for p in problems if p.startswith(f"{family}_")]
        if not family_problems:
            continue
        rows = []
        for problem in family_problems:
            cells = [f"<th>{html.escape(problem)}</th>"]
            for config in configurations:
                result = lookup.get((problem, config))
                cells.append(result_cell(result) if result else '<td class="missing">No log</td>')
            rows.append("<tr>" + "".join(cells) + "</tr>")
        headers = "".join(f"<th>{html.escape(c)}</th>" for c in configurations)
        matrices.append(
            f'<section><h2>{family.title()} problems</h2><div class="scroll"><table class="matrix">'
            f"<thead><tr><th>Problem</th>{headers}</tr></thead><tbody>{''.join(rows)}</tbody>"
            "</table></div></section>"
        )

    detail_rows = []
    for r in sorted(results, key=lambda item: (problem_key(item.problem), item.configuration)):
        outcome = "Solved" if r.solved else f"{r.failure_phase.title()} failed: {r.failure_reason}"
        detail_rows.append(
            f'<tr data-problem="{html.escape(r.problem)}" data-config="{html.escape(r.configuration)}" '
            f'data-status="{"solved" if r.solved else "failed"}">'
            f"<td>{html.escape(r.problem)}</td><td>{html.escape(r.configuration)}</td>"
            f'<td class="{"ok-text" if r.solved else "fail-text"}">{html.escape(outcome)}</td>'
            f"<td>{fmt_time(r.translation_seconds)}</td><td>{fmt_time(r.search_seconds)}</td>"
            f"<td>{r.plan_length if r.plan_length is not None else '-'}</td>"
            f"<td>{link(r.log_path, 'log')} {link(r.plan_path, 'plan')}</td></tr>"
        )

    config_options = "".join(f'<option value="{html.escape(c)}">{html.escape(c)}</option>' for c in configurations)
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Planner benchmark results</title>
<style>
:root {{ color-scheme: light; --ink:#17202a; --muted:#5d6d7e; --line:#d5d8dc; --ok:#e8f8f0; --bad:#fdecea; --accent:#2457a6; }}
* {{ box-sizing:border-box }} body {{ margin:0; color:var(--ink); font:14px/1.45 system-ui,sans-serif; background:#f7f8fa }}
main {{ max-width:1600px; margin:auto; padding:28px }} h1 {{ margin:0 0 6px; font-size:30px }} h2 {{ margin:30px 0 10px }}
p {{ color:var(--muted) }} table {{ border-collapse:collapse; width:100%; background:white }} th,td {{ border:1px solid var(--line); padding:7px 9px; text-align:left; vertical-align:top }}
thead th {{ position:sticky; top:0; z-index:1; background:#eef2f7 }} tbody th {{ white-space:nowrap; background:#f8f9fa }}
.scroll {{ overflow:auto; max-height:75vh; border:1px solid var(--line) }} .matrix {{ min-width:1500px }} .matrix td {{ min-width:120px }}
.matrix small {{ display:block; color:var(--muted); white-space:nowrap }} .solved {{ background:var(--ok) }} .failed {{ background:var(--bad) }} .missing {{ color:var(--muted) }}
.warning,.fail-text {{ color:#a93226 }} .ok-text {{ color:#18784a }} a {{ color:var(--accent) }}
.controls {{ display:flex; gap:10px; flex-wrap:wrap; margin:10px 0 }} input,select {{ padding:8px; border:1px solid #aeb6bf; border-radius:4px; background:white }}
.legend {{ display:flex; gap:18px; flex-wrap:wrap }} code {{ background:#eaecee; padding:1px 4px }}
@media (max-width:700px) {{ main {{ padding:15px }} }}
</style></head><body><main>
<h1>Planner benchmark results</h1>
<p>Generated from <code>problem_outputs/</code>. T = translation wall-clock time, S = Fast Downward search time, L = plan length.</p>
<div class="legend"><span><strong>{len(problems)}</strong> problems</span><span><strong>{len(configurations)}</strong> configurations</span><span><strong>{len(results)}</strong> runs</span></div>
<h2>Configuration summary</h2>
<table><thead><tr><th>Configuration</th><th>Solved</th><th>Mean search time</th><th>Translation failures</th><th>Search failures</th></tr></thead><tbody>{''.join(summary_rows)}</tbody></table>
{''.join(matrices)}
<section><h2>All runs</h2>
<div class="controls"><input id="problem" placeholder="Filter problem"><select id="configuration"><option value="">All configurations</option>{config_options}</select><select id="status"><option value="">All outcomes</option><option value="solved">Solved</option><option value="failed">Failed</option></select></div>
<div class="scroll"><table id="details"><thead><tr><th>Problem</th><th>Configuration</th><th>Outcome</th><th>Translation</th><th>Search</th><th>Plan length</th><th>Files</th></tr></thead><tbody>{''.join(detail_rows)}</tbody></table></div>
</section>
<p>Times unavailable in a log are shown as "-". Mean search time only includes successful runs.</p>
</main><script>
const inputs=[document.querySelector('#problem'),document.querySelector('#configuration'),document.querySelector('#status')];
function filterRows() {{ const [p,c,s]=inputs.map(x=>x.value.toLowerCase()); document.querySelectorAll('#details tbody tr').forEach(row=>{{ row.hidden=!(row.dataset.problem.includes(p)&&row.dataset.config.includes(c)&&row.dataset.status.includes(s)); }}); }}
inputs.forEach(input=>input.addEventListener('input',filterRows));
</script></body></html>"""
    output.write_text(document, encoding="utf-8")


def write_csv(results: list[Result], output: Path) -> None:
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(results[0])))
        writer.writeheader()
        writer.writerows(asdict(result) for result in results)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", type=Path, default=Path("problem_outputs"))
    parser.add_argument("--html", type=Path, default=Path("planner_results.html"))
    parser.add_argument("--markdown", type=Path, default=Path("planner_results.md"))
    parser.add_argument("--csv", type=Path, default=Path("planner_results.csv"))
    args = parser.parse_args()
    root = Path.cwd().resolve()
    outputs = args.outputs.resolve()
    logs = sorted(outputs.glob("*/*_log.txt"))
    if not logs:
        parser.error(f"no *_log.txt files found below {args.outputs}")
    results = [parse_result(path, root) for path in logs]
    build_html(results, args.html)
    build_markdown(results, args.markdown)
    write_csv(results, args.csv)
    print(f"Wrote {args.html}, {args.markdown}, and {args.csv} from {len(results)} logs.")


if __name__ == "__main__":
    main()
