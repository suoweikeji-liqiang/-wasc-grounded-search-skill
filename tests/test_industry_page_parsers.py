from __future__ import annotations


def test_extract_query_aligned_page_excerpt_prefers_focus_terms_missing_from_metadata() -> None:
    from skill.retrieval.live.parsers.industry import extract_query_aligned_page_excerpt

    html = """
    <html>
      <head><title>Ford 2025 Annual Report</title></head>
      <body>
        <div>Official SEC filing 10-K filed 2026-02-11 report period 2025-12-31</div>
        <div>Ford+ is our growth plan for vehicles, software, and services.</div>
        <div>
          We accrue the estimated cost of both base warranty coverages and field
          service actions at the time a vehicle is sold, and we reevaluate the
          adequacy of our accruals on a regular basis.
        </div>
      </body>
    </html>
    """

    excerpt = extract_query_aligned_page_excerpt(
        html=html,
        query="Ford 2025 Form 10-K warranty accrual accounting policy changes",
        title="FORD MOTOR CO Form 10-K filing",
        candidate_snippet="Official SEC filing 10-K filed 2026-02-11 report period 2025-12-31",
        max_chars=220,
    )

    assert "warranty" in excerpt.lower()
    assert "accrual" in excerpt.lower()
    assert "ford+" not in excerpt.lower()
