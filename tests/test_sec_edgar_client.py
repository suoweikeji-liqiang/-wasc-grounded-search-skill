from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _clear_sec_edgar_caches() -> None:
    from skill.retrieval.live.clients import sec_edgar

    sec_edgar._CACHE._entries.clear()
    sec_edgar._SUBMISSIONS_CACHE._entries.clear()
    if hasattr(sec_edgar, "_COMPANY_TICKERS_CACHE"):
        sec_edgar._COMPANY_TICKERS_CACHE._entries.clear()


def test_search_sec_company_submissions_prefers_report_period_year_match(
    monkeypatch,
) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients import sec_edgar

    async def _fake_fetch_json(**kwargs: object) -> object:
        assert kwargs["url"] == "https://data.sec.gov/submissions/CIK0000012927.json"
        return {
            "name": "BOEING CO",
            "filings": {
                "recent": {
                    "form": ["10-K", "10-K"],
                    "accessionNumber": [
                        "0000012927-25-000015",
                        "0001628280-26-004357",
                    ],
                    "primaryDocument": [
                        "ba-20241231.htm",
                        "ba-20251231.htm",
                    ],
                    "filingDate": [
                        "2025-02-03",
                        "2026-01-30",
                    ],
                    "reportDate": [
                        "2024-12-31",
                        "2025-12-31",
                    ],
                }
            },
        }

    monkeypatch.setattr(http_client, "fetch_json", _fake_fetch_json)

    records = asyncio.run(
        sec_edgar.search_sec_company_submissions(
            query="Boeing 2025 Form 10-K backlog definition order cancellation policy regression-ordering",
            max_results=2,
        )
    )

    assert len(records) == 2
    assert records[0]["url"].endswith("/ba-20251231.htm")
    assert records[1]["url"].endswith("/ba-20241231.htm")


def test_has_company_submission_target_uses_sec_ticker_directory_for_fresh_companies(
    monkeypatch,
) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients import sec_edgar

    observed_urls: list[str] = []

    async def _fake_fetch_json(**kwargs: object) -> object:
        observed_urls.append(str(kwargs["url"]))
        assert kwargs["url"] == "https://www.sec.gov/files/company_tickers.json"
        return {
            "0": {
                "cik_str": 1403161,
                "ticker": "V",
                "title": "VISA INC.",
            },
            "1": {
                "cik_str": 1318605,
                "ticker": "TSLA",
                "title": "Tesla, Inc.",
            },
            "2": {
                "cik_str": 100517,
                "ticker": "UAL",
                "title": "United Airlines Holdings, Inc.",
            },
            "3": {
                "cik_str": 2488,
                "ticker": "AMD",
                "title": "ADVANCED MICRO DEVICES INC",
            },
        }

    monkeypatch.setattr(http_client, "fetch_json", _fake_fetch_json)

    assert (
        asyncio.run(
            sec_edgar.has_company_submission_target(
                "Visa 2025 Form 10-K payments volume processed transactions definitions"
            )
        )
        is True
    )
    assert (
        asyncio.run(
            sec_edgar.has_company_submission_target(
                "Tesla 2025 Form 10-K energy generation and storage revenue recognition"
            )
        )
        is True
    )
    assert (
        asyncio.run(
            sec_edgar.has_company_submission_target(
                "United Airlines 2025 annual report CASM-ex fuel definition"
            )
        )
        is True
    )
    assert (
        asyncio.run(
            sec_edgar.has_company_submission_target(
                "AMD 2025 Form 10-K inventory valuation foundry supply risk factors"
            )
        )
        is True
    )
    assert observed_urls == ["https://www.sec.gov/files/company_tickers.json"]


def test_search_sec_company_submissions_uses_ticker_directory_match_for_unlisted_company(
    monkeypatch,
) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients import sec_edgar

    async def _fake_fetch_json(**kwargs: object) -> object:
        url = str(kwargs["url"])
        if url == "https://www.sec.gov/files/company_tickers.json":
            return {
                "0": {
                    "cik_str": 1403161,
                    "ticker": "V",
                    "title": "VISA INC.",
                }
            }
        if url == "https://data.sec.gov/submissions/CIK0001403161.json":
            return {
                "name": "VISA INC.",
                "filings": {
                    "recent": {
                        "form": ["10-K", "10-Q"],
                        "accessionNumber": [
                            "0001403161-25-000070",
                            "0001403161-25-000051",
                        ],
                        "primaryDocument": [
                            "v-20240930.htm",
                            "v-20240630.htm",
                        ],
                        "filingDate": [
                            "2025-11-14",
                            "2025-08-02",
                        ],
                        "reportDate": [
                            "2025-09-30",
                            "2025-06-30",
                        ],
                    }
                },
            }
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(http_client, "fetch_json", _fake_fetch_json)

    records = asyncio.run(
        sec_edgar.search_sec_company_submissions(
            query="Visa 2025 Form 10-K payments volume processed transactions definitions",
            max_results=2,
        )
    )

    assert len(records) == 1
    assert records[0]["title"] == "VISA INC. Form 10-K filing"
    assert records[0]["url"].endswith("/v-20240930.htm")
