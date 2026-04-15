from __future__ import annotations


def test_build_industry_snippet_prefers_fact_dense_page_excerpt_over_generic_candidate() -> None:
    from skill.retrieval.live.parsers.industry import build_industry_snippet

    snippet = build_industry_snippet(
        query="advanced packaging capacity outlook 2026",
        candidate_snippet="General outlook for advanced packaging capacity in 2026.",
        page_text=(
            "This update reviews the advanced packaging ecosystem, vendor positioning, and the "
            "broader outlook for advanced packaging capacity in 2026 across major supply chains.\n\n"
            "SEMI said advanced packaging capacity reached 385,000 wafers per month in 2026, "
            "up 18% year over year, while CoWoS capacity share rose to 62%."
        ),
        max_chars=220,
    )

    assert "385,000 wafers per month" in snippet
    assert "18% year over year" in snippet
    assert "62%" in snippet


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
