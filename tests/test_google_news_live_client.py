"""Regressions for Google News live article URL resolution."""

from __future__ import annotations

import asyncio


def test_resolve_google_news_article_url_decodes_new_style_article_ids(monkeypatch) -> None:
    from skill.retrieval.live.clients import google_news

    async def _fake_fetch_text_limited(*, url: str, **_: object) -> str:
        assert url == "https://news.google.com/rss/articles/example-article-id"
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
