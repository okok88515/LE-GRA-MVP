from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "p3_6g_temporal_learner"
OUT_DIR = ROOT / "analysis_method_metrics"


METHOD_ORDER = [
    "No grouping",
    "CQI k-means",
    "Resource-cost k-means",
    "Multi-feature k-means",
    "Offline teacher",
    "LE-GRA MVP",
]

METHOD_COLORS = {
    "No grouping": "#7c6f64",
    "CQI k-means": "#c6542b",
    "Resource-cost k-means": "#2f6f5e",
    "Multi-feature k-means": "#3f7cac",
    "Offline teacher": "#b88a1b",
    "LE-GRA MVP": "#7a4db3",
}


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def parse_float_rows(rows: list[dict[str, str]], fields: list[str]) -> list[dict[str, float | str]]:
    parsed: list[dict[str, float | str]] = []
    for row in rows:
        parsed_row: dict[str, float | str] = {"method": row["method"]}
        for field in fields:
            parsed_row[field] = float(row[field])
        parsed.append(parsed_row)
    return parsed


def average_diag(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    metrics = ["pairwise_accuracy", "ari", "nmi"]
    grouped: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        method = row["method"]
        grouped.setdefault(method, {metric: [] for metric in metrics})
        for metric in metrics:
            grouped[method][metric].append(float(row[metric]))
    return {
        method: {metric: mean(values[metric]) for metric in metrics}
        for method, values in grouped.items()
    }


def fmt(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def svg_bar_chart(
    title: str,
    subtitle: str,
    labels: list[str],
    values: list[float],
    colors: list[str],
    *,
    width: int = 980,
    height: int = 420,
    y_label: str = "",
    value_digits: int = 4,
) -> str:
    pad_left = 72
    pad_right = 28
    pad_top = 62
    pad_bottom = 90
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom
    max_val = max(values) if values else 1.0
    if max_val <= 0:
        max_val = 1.0
    upper = max_val * 1.12
    grid_steps = 5
    bar_gap = 18
    slot_w = chart_w / max(len(values), 1)
    bar_w = max(24, slot_w - bar_gap)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fffaf2" rx="24"/>',
        f'<text x="{pad_left}" y="30" font-size="24" font-family="Segoe UI, Noto Sans TC, sans-serif" fill="#13212c" font-weight="700">{html.escape(title)}</text>',
        f'<text x="{pad_left}" y="52" font-size="13" font-family="Segoe UI, Noto Sans TC, sans-serif" fill="#59656f">{html.escape(subtitle)}</text>',
    ]

    for step in range(grid_steps + 1):
        ratio = step / grid_steps
        y = pad_top + chart_h - ratio * chart_h
        tick = upper * ratio
        parts.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" stroke="#d9d2c6" stroke-width="1"/>')
        parts.append(
            f'<text x="{pad_left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12" '
            f'font-family="Consolas, monospace" fill="#59656f">{fmt(tick, value_digits if upper < 10 else 2)}</text>'
        )

    parts.append(f'<line x1="{pad_left}" y1="{pad_top + chart_h}" x2="{width - pad_right}" y2="{pad_top + chart_h}" stroke="#6d6257" stroke-width="1.2"/>')

    if y_label:
        parts.append(
            f'<text x="20" y="{pad_top + chart_h / 2:.1f}" transform="rotate(-90 20 {pad_top + chart_h / 2:.1f})" '
            f'font-size="13" font-family="Segoe UI, Noto Sans TC, sans-serif" fill="#59656f">{html.escape(y_label)}</text>'
        )

    for idx, (label, value, color) in enumerate(zip(labels, values, colors)):
        x = pad_left + idx * slot_w + (slot_w - bar_w) / 2
        bar_h = 0.0 if upper == 0 else value / upper * chart_h
        y = pad_top + chart_h - bar_h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" rx="8"/>')
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-size="12" '
            f'font-family="Consolas, monospace" fill="#13212c">{fmt(value, value_digits)}</text>'
        )
        label_x = x + bar_w / 2
        label_y = pad_top + chart_h + 18
        parts.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="end" transform="rotate(-28 {label_x:.1f} {label_y:.1f})" '
            f'font-size="12" font-family="Segoe UI, Noto Sans TC, sans-serif" fill="#2b3944">{html.escape(label)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    main_rows = load_csv(SOURCE_DIR / "main_comparison.csv")
    diag_rows = load_csv(SOURCE_DIR / "teacher_imitation_diagnostics.csv")

    numeric_fields = [
        "utility",
        "adr_kbps",
        "rb_utilization",
        "avg_switching",
        "fairness",
        "average_quality",
        "avg_groups",
    ]
    parsed_main = parse_float_rows(main_rows, numeric_fields)
    parsed_main.sort(key=lambda row: METHOD_ORDER.index(str(row["method"])))

    diag_avg = average_diag(diag_rows)

    labels = [str(row["method"]) for row in parsed_main]
    colors = [METHOD_COLORS[label] for label in labels]

    utility_svg = svg_bar_chart(
        "Utility Comparison",
        "Source: p3_6g_temporal_learner/main_comparison.csv",
        labels,
        [float(row["utility"]) for row in parsed_main],
        colors,
        y_label="utility",
        value_digits=4,
    )
    adr_svg = svg_bar_chart(
        "Average Delivered Rate (kbps)",
        "Higher is better when service remains stable.",
        labels,
        [float(row["adr_kbps"]) for row in parsed_main],
        colors,
        y_label="kbps",
        value_digits=1,
    )
    util_svg = svg_bar_chart(
        "RB Utilization",
        "How much of the available RB budget was actually used.",
        labels,
        [float(row["rb_utilization"]) for row in parsed_main],
        colors,
        y_label="ratio",
        value_digits=4,
    )
    switch_svg = svg_bar_chart(
        "Average Switching",
        "Lower is better because quality switching is penalized.",
        labels,
        [float(row["avg_switching"]) for row in parsed_main],
        colors,
        y_label="ratio",
        value_digits=4,
    )
    fairness_svg = svg_bar_chart(
        "Fairness",
        "Closer to 1 means more even service across users.",
        labels,
        [float(row["fairness"]) for row in parsed_main],
        colors,
        y_label="score",
        value_digits=4,
    )
    quality_svg = svg_bar_chart(
        "Average Quality Level",
        "Average selected quality index after allocation.",
        labels,
        [float(row["average_quality"]) for row in parsed_main],
        colors,
        y_label="quality index",
        value_digits=4,
    )

    diag_methods = [method for method in ["Multi-feature k-means", "LE-GRA MVP"] if method in diag_avg]
    diag_labels = diag_methods
    diag_colors = [METHOD_COLORS[label] for label in diag_labels]
    pairwise_svg = svg_bar_chart(
        "Teacher Imitation: Pairwise Accuracy",
        "Average over test scenarios in teacher_imitation_diagnostics.csv",
        diag_labels,
        [diag_avg[method]["pairwise_accuracy"] for method in diag_labels],
        diag_colors,
        y_label="score",
        value_digits=4,
    )
    ari_svg = svg_bar_chart(
        "Teacher Imitation: ARI",
        "Adjusted Rand Index against offline teacher partitions.",
        diag_labels,
        [diag_avg[method]["ari"] for method in diag_labels],
        diag_colors,
        y_label="score",
        value_digits=4,
    )
    nmi_svg = svg_bar_chart(
        "Teacher Imitation: NMI",
        "Normalized Mutual Information against offline teacher partitions.",
        diag_labels,
        [diag_avg[method]["nmi"] for method in diag_labels],
        diag_colors,
        y_label="score",
        value_digits=4,
    )

    write_text(OUT_DIR / "utility_comparison.svg", utility_svg)
    write_text(OUT_DIR / "adr_comparison.svg", adr_svg)
    write_text(OUT_DIR / "rb_utilization_comparison.svg", util_svg)
    write_text(OUT_DIR / "avg_switching_comparison.svg", switch_svg)
    write_text(OUT_DIR / "fairness_comparison.svg", fairness_svg)
    write_text(OUT_DIR / "average_quality_comparison.svg", quality_svg)
    write_text(OUT_DIR / "pairwise_accuracy_comparison.svg", pairwise_svg)
    write_text(OUT_DIR / "ari_comparison.svg", ari_svg)
    write_text(OUT_DIR / "nmi_comparison.svg", nmi_svg)

    no_grouping = next(row for row in parsed_main if row["method"] == "No grouping")
    teacher = next(row for row in parsed_main if row["method"] == "Offline teacher")
    cqi = next(row for row in parsed_main if row["method"] == "CQI k-means")
    resource = next(row for row in parsed_main if row["method"] == "Resource-cost k-means")
    multi = next(row for row in parsed_main if row["method"] == "Multi-feature k-means")
    legra = next(row for row in parsed_main if row["method"] == "LE-GRA MVP")

    summary = {
        "source_dir": str(SOURCE_DIR),
        "utility_gap_vs_no_grouping": float(teacher["utility"]) - float(no_grouping["utility"]),
        "adr_gap_vs_no_grouping": float(teacher["adr_kbps"]) - float(no_grouping["adr_kbps"]),
        "teacher_like_methods": [
            method for method in labels if abs(float(next(row for row in parsed_main if row["method"] == method)["utility"]) - float(teacher["utility"])) < 1e-12
        ],
        "diag_average": diag_avg,
        "dataset": main_rows[0]["dataset"],
        "feature_mode": main_rows[0]["feature_mode"],
        "rb_budget_ratio": float(main_rows[0]["rb_budget_ratio"]),
    }
    write_text(OUT_DIR / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2))

    table_rows = "\n".join(
        (
            "<tr>"
            f"<td>{html.escape(str(row['method']))}</td>"
            f"<td>{fmt(float(row['utility']))}</td>"
            f"<td>{fmt(float(row['adr_kbps']), 1)}</td>"
            f"<td>{fmt(float(row['rb_utilization']))}</td>"
            f"<td>{fmt(float(row['avg_switching']))}</td>"
            f"<td>{fmt(float(row['fairness']))}</td>"
            f"<td>{fmt(float(row['average_quality']))}</td>"
            f"<td>{fmt(float(row['avg_groups']))}</td>"
            "</tr>"
        )
        for row in parsed_main
    )

    diag_rows_html = "\n".join(
        (
            "<tr>"
            f"<td>{html.escape(method)}</td>"
            f"<td>{fmt(diag_avg[method]['pairwise_accuracy'])}</td>"
            f"<td>{fmt(diag_avg[method]['ari'])}</td>"
            f"<td>{fmt(diag_avg[method]['nmi'])}</td>"
            "</tr>"
        )
        for method in diag_methods
    )

    html_report = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Method Metrics Report</title>
  <style>
    :root {{
      --paper: #f7f1e6;
      --card: rgba(255, 252, 246, 0.88);
      --ink: #16242d;
      --muted: #5a6872;
      --line: rgba(22, 36, 45, 0.12);
      --accent: #c6542b;
      --shadow: 0 22px 54px rgba(22, 36, 45, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(198, 84, 43, 0.14), transparent 30%),
        linear-gradient(180deg, #faf5ec 0%, #efe5d5 100%);
    }}
    .page {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 56px;
    }}
    .hero, .card {{
      background: var(--card);
      border: 1px solid rgba(255,255,255,0.65);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .hero {{
      padding: 28px;
      margin-bottom: 22px;
    }}
    .hero h1, .card h2 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      letter-spacing: -0.03em;
    }}
    .hero h1 {{ font-size: 2.7rem; }}
    .hero p, .card p, .card li, td, th {{
      line-height: 1.8;
      color: #24404d;
    }}
    .grid {{
      display: grid;
      gap: 18px;
    }}
    .grid.two {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .card {{
      padding: 24px;
    }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.82rem;
      font-weight: 700;
      margin-bottom: 10px;
    }}
    img {{
      width: 100%;
      border: 1px solid var(--line);
      background: #fff;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      font-size: 0.95rem;
    }}
    th {{
      color: var(--muted);
      font-weight: 700;
    }}
    ul {{
      margin: 0;
      padding-left: 20px;
    }}
    @media (max-width: 960px) {{
      .grid.two {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">Metrics Visualization</div>
      <h1>目前方法 Metrics 圖表與分析</h1>
      <p>
        資料來源是 <code>p3_6g_temporal_learner/main_comparison.csv</code> 與
        <code>p3_6g_temporal_learner/teacher_imitation_diagnostics.csv</code>。
        這是一個 focused temporal regime，設定為 <code>feature_mode=history_cost_quality</code>、
        <code>rb_budget_ratio=0.32</code>、<code>max_groups=3</code>。
      </p>
    </section>

    <section class="card">
      <div class="eyebrow">總結</div>
      <h2>先看最重要的三句話</h2>
      <ul>
        <li>目前這個 regime 裡，<strong>除了 No grouping 之外，其它五個方法全部打平</strong>，包含 CQI、resource-cost、multi-feature、offline teacher 與 LE-GRA。</li>
        <li>相對於 No grouping，這五個方法都把 utility 從 <strong>{fmt(float(no_grouping["utility"]))}</strong> 提升到 <strong>{fmt(float(teacher["utility"]))}</strong>，提升幅度是 <strong>{fmt(summary["utility_gap_vs_no_grouping"])}</strong>。</li>
        <li>在 teacher imitation 指標上，<strong>Multi-feature k-means 與 LE-GRA 平均 pairwise / ARI / NMI 全部都是 1.0</strong>，代表在這個 slice 上兩者都完整重建了 teacher 的群組結構。</li>
      </ul>
    </section>

    <section class="grid two">
      <article class="card">
        <div class="eyebrow">Allocation</div>
        <h2>Utility</h2>
        <img src="utility_comparison.svg" alt="Utility comparison chart">
      </article>
      <article class="card">
        <div class="eyebrow">Allocation</div>
        <h2>ADR</h2>
        <img src="adr_comparison.svg" alt="ADR comparison chart">
      </article>
      <article class="card">
        <div class="eyebrow">Allocation</div>
        <h2>RB Utilization</h2>
        <img src="rb_utilization_comparison.svg" alt="RB utilization comparison chart">
      </article>
      <article class="card">
        <div class="eyebrow">Allocation</div>
        <h2>Average Switching</h2>
        <img src="avg_switching_comparison.svg" alt="Average switching comparison chart">
      </article>
      <article class="card">
        <div class="eyebrow">Allocation</div>
        <h2>Fairness</h2>
        <img src="fairness_comparison.svg" alt="Fairness comparison chart">
      </article>
      <article class="card">
        <div class="eyebrow">Allocation</div>
        <h2>Average Quality</h2>
        <img src="average_quality_comparison.svg" alt="Average quality comparison chart">
      </article>
    </section>

    <section class="grid two" style="margin-top: 18px;">
      <article class="card">
        <div class="eyebrow">Teacher Imitation</div>
        <h2>Pairwise Accuracy</h2>
        <img src="pairwise_accuracy_comparison.svg" alt="Pairwise accuracy comparison chart">
      </article>
      <article class="card">
        <div class="eyebrow">Teacher Imitation</div>
        <h2>ARI</h2>
        <img src="ari_comparison.svg" alt="ARI comparison chart">
      </article>
      <article class="card">
        <div class="eyebrow">Teacher Imitation</div>
        <h2>NMI</h2>
        <img src="nmi_comparison.svg" alt="NMI comparison chart">
      </article>
      <article class="card">
        <div class="eyebrow">解讀</div>
        <h2>圖表代表什麼</h2>
        <ul>
          <li><strong>Utility / ADR / Average Quality</strong>：代表最終 multicast allocation 的效益。</li>
          <li><strong>RB Utilization</strong>：代表方法是否真的把可用 RB 預算用起來。</li>
          <li><strong>Average Switching</strong>：越低越好，因為切換太多會被 utility 懲罰。</li>
          <li><strong>Fairness</strong>：越接近 1 代表服務越平均。</li>
          <li><strong>Pairwise / ARI / NMI</strong>：代表方法在群組結構上有多接近 offline teacher。</li>
        </ul>
      </article>
    </section>

    <section class="card" style="margin-top: 18px;">
      <div class="eyebrow">分析</div>
      <h2>這組結果的核心 insight</h2>
      <ul>
        <li><strong>No grouping 明顯較差</strong>：它的 utility、ADR、average quality、RB utilization 都明顯落後，代表這個 temporal regime 確實需要分群，不能把所有人硬綁一起。</li>
        <li><strong>其餘五個方法完全重合</strong>：這表示在這個 focused slice 裡，真正困難的不是「要不要分群」，而是「只要你找到那個 teacher split，誰都能贏」。</li>
        <li><strong>CQI 已經足夠</strong>：因為 CQI k-means、resource-cost、multi-feature、teacher、LE-GRA 全部同分，代表這個 slice 的可分結構已經強到 CQI 也能看見，feature richness 沒有被真正考驗到。</li>
        <li><strong>LE-GRA 在這裡證明的是可學到，不是明顯超越</strong>：teacher imitation 指標 1.0 很漂亮，但 multi-feature k-means 也是 1.0，所以這個結果比較支持「LE-GRA 能學到 teacher」，而不是「LE-GRA 超越 hand-crafted feature baseline」。</li>
        <li><strong>resource-cost / multi-feature 的價值沒有被否定，只是這個 regime 不夠 hard</strong>：當一個 slice 太乾淨、太容易 split 時， richer feature 的優勢自然不會被拉大。</li>
      </ul>
    </section>

    <section class="card" style="margin-top: 18px;">
      <div class="eyebrow">表格</div>
      <h2>主要數值總表</h2>
      <table>
        <thead>
          <tr>
            <th>Method</th>
            <th>Utility</th>
            <th>ADR (kbps)</th>
            <th>RB Utilization</th>
            <th>Avg Switching</th>
            <th>Fairness</th>
            <th>Average Quality</th>
            <th>Avg Groups</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </section>

    <section class="card" style="margin-top: 18px;">
      <div class="eyebrow">Teacher Imitation</div>
      <h2>群組結構模仿指標平均值</h2>
      <table>
        <thead>
          <tr>
            <th>Method</th>
            <th>Pairwise Accuracy</th>
            <th>ARI</th>
            <th>NMI</th>
          </tr>
        </thead>
        <tbody>
          {diag_rows_html}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""

    write_text(OUT_DIR / "method_metrics_report_zh.html", html_report)
    print(str(OUT_DIR / "method_metrics_report_zh.html"))


if __name__ == "__main__":
    main()
