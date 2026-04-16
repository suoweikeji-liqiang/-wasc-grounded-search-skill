"""Regressions for Google News live article URL resolution."""

from __future__ import annotations

import asyncio


def test_resolve_google_news_article_url_decodes_new_style_article_ids(monkeypatch) -> None:
    from skill.retrieval.live.clients import google_news

    async def _fake_fetch_text_limited(*, url: str, **_: object) -> str:
        assert url == "https://news.google.com/articles/example-article-id"
        return """
        <html>
          <body>
            <c-wiz>
              <div data-n-a-sg="signed-token" data-n-a-ts="1776265522"></div>
            </c-wiz>
          </body>
        </html>
        """

    async def _fake_post_text(*, url: str, data: str, **_: object) -> str:
        assert url.startswith("https://news.google.com/_/DotsSplashUi/data/batchexecute")
        assert "example-article-id" in data
        return ')]}\'\n\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://example.com/original-article\\",null,null,1]",null,null,null,"generic"]]'

    monkeypatch.setattr(google_news.http_client, "fetch_text_limited", _fake_fetch_text_limited)
    monkeypatch.setattr(google_news.http_client, "post_text", _fake_post_text, raising=False)

    resolved = asyncio.run(
        google_news.resolve_google_news_article_url(
            "https://news.google.com/rss/articles/example-article-id"
        )
    )

    assert resolved == "https://example.com/original-article"


def test_resolve_google_news_article_url_falls_back_to_articles_page_when_rss_page_has_no_decoder_inputs(
    monkeypatch,
) -> None:
    from skill.retrieval.live.clients import google_news

    observed_urls: list[str] = []

    async def _fake_fetch_text_limited(*, url: str, **_: object) -> str:
        observed_urls.append(url)
        if url == "https://news.google.com/rss/articles/example-article-id":
            return "<html><body><div>No decoder inputs here.</div></body></html>"
        assert url == "https://news.google.com/articles/example-article-id"
        return """
        <html>
          <body>
            <c-wiz>
              <div data-n-a-sg="signed-token" data-n-a-ts="1776265522"></div>
            </c-wiz>
          </body>
        </html>
        """

    async def _fake_post_text(*, data: str, **_: object) -> str:
        assert "example-article-id" in data
        return ')]}\'\n\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://example.com/original-article\\",null,null,1]",null,null,null,"generic"]]'

    monkeypatch.setattr(google_news.http_client, "fetch_text_limited", _fake_fetch_text_limited)
    monkeypatch.setattr(google_news.http_client, "post_text", _fake_post_text, raising=False)

    resolved = asyncio.run(
        google_news.resolve_google_news_article_url(
            "https://news.google.com/articles/example-article-id"
        )
    )

    assert observed_urls == [
        "https://news.google.com/rss/articles/example-article-id",
        "https://news.google.com/articles/example-article-id",
    ]
    assert resolved == "https://example.com/original-article"


def test_resolve_google_news_article_url_extracts_decoder_inputs_from_single_quoted_html_attributes(
    monkeypatch,
) -> None:
    from skill.retrieval.live.clients import google_news

    async def _fake_fetch_text_limited(*, url: str, **_: object) -> str:
        assert url == "https://news.google.com/articles/example-article-id"
        return """
        <html>
          <body>
            <c-wiz>
              <div jscontroller='X' data-n-a-sg='signed-token' data-n-a-ts='1776265522'></div>
            </c-wiz>
          </body>
        </html>
        """

    async def _fake_post_text(*, data: str, **_: object) -> str:
        assert "example-article-id" in data
        return ')]}\'\n\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://example.com/original-article\\",null,null,1]",null,null,null,"generic"]]'

    monkeypatch.setattr(google_news.http_client, "fetch_text_limited", _fake_fetch_text_limited)
    monkeypatch.setattr(google_news.http_client, "post_text", _fake_post_text, raising=False)

    resolved = asyncio.run(
        google_news.resolve_google_news_article_url(
            "https://news.google.com/rss/articles/example-article-id"
        )
    )

    assert resolved == "https://example.com/original-article"


def test_resolve_google_news_article_url_posts_with_browser_like_referer_header(
    monkeypatch,
) -> None:
    from skill.retrieval.live.clients import google_news

    async def _fake_fetch_text_limited(*, url: str, **_: object) -> str:
        assert url == "https://news.google.com/articles/example-article-id"
        return """
        <html>
          <body>
            <c-wiz>
              <div data-n-a-sg="signed-token" data-n-a-ts="1776265522"></div>
            </c-wiz>
          </body>
        </html>
        """

    async def _fake_post_text(*, headers: dict[str, str], data: str, **_: object) -> str:
        assert "example-article-id" in data
        assert headers["Referer"] == "https://www.google.com/"
        assert "Referrer" not in headers
        return ')]}\'\n\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://example.com/original-article\\",null,null,1]",null,null,null,"generic"]]'

    monkeypatch.setattr(google_news.http_client, "fetch_text_limited", _fake_fetch_text_limited)
    monkeypatch.setattr(google_news.http_client, "post_text", _fake_post_text, raising=False)

    resolved = asyncio.run(
        google_news.resolve_google_news_article_url(
            "https://news.google.com/articles/example-article-id"
        )
    )

    assert resolved == "https://example.com/original-article"


def test_resolve_google_news_article_url_prefers_rss_article_page_and_reads_late_decoder_inputs(
    monkeypatch,
) -> None:
    from skill.retrieval.live.clients import google_news

    observed_fetches: list[tuple[str, int]] = []

    async def _fake_fetch_text_limited(
        *,
        url: str,
        max_chars: int,
        **_: object,
    ) -> str:
        observed_fetches.append((url, max_chars))
        assert url == "https://news.google.com/rss/articles/example-article-id"
        assert max_chars >= 600_000
        return (
            "<html><body>"
            + ("x" * 220_000)
            + '<div data-n-a-sg="signed-token" data-n-a-ts="1776265522"></div>'
            + "</body></html>"
        )

    async def _fake_post_text(*, data: str, **_: object) -> str:
        assert "example-article-id" in data
        return ')]}\'\n\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://example.com/original-article\\",null,null,1]",null,null,null,"generic"]]'

    monkeypatch.setattr(google_news.http_client, "fetch_text_limited", _fake_fetch_text_limited)
    monkeypatch.setattr(google_news.http_client, "post_text", _fake_post_text, raising=False)

    resolved = asyncio.run(
        google_news.resolve_google_news_article_url(
            "https://news.google.com/articles/example-article-id"
        )
    )

    assert observed_fetches == [
        ("https://news.google.com/rss/articles/example-article-id", 650_000),
    ]
    assert resolved == "https://example.com/original-article"
