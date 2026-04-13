"""Immutable route constants and source-family mapping for Phase 1."""

from typing import Final

ConcreteRoute = str

ROUTE_PRECEDENCE: Final[tuple[ConcreteRoute, ConcreteRoute, ConcreteRoute]] = (
    "policy",
    "academic",
    "industry",
)

SHORT_QUERY_CHAR_THRESHOLD: Final[int] = 12
SHORT_QUERY_TOKEN_THRESHOLD: Final[int] = 3
LOW_SIGNAL_SCORE_THRESHOLD: Final[int] = 2

EXPLICIT_CROSS_DOMAIN_MARKERS: Final[tuple[str, ...]] = (
    "\u5f71\u54cd",
    "\u6548\u5e94",
    "\u4e0e",
    "\u6bd4\u8f83",
    "\u5bf9\u6bd4",
    "\u4ea4\u53c9",
    "\u7ed3\u5408",
    "\u8054\u52a8",
    "\u5bf9\u884c\u4e1a",
    "\u653f\u7b56\u5bf9\u884c\u4e1a",
    "\u5bf9\u7814\u7a76",
    "\u7814\u7a76\u4e0e\u76d1\u7ba1",
    "\u4ea7\u4e1a\u843d\u5730",
    "vs",
)

POLICY_MARKERS: Final[tuple[str, ...]] = (
    "\u653f\u7b56",
    "\u6cd5\u89c4",
    "\u6761\u4f8b",
    "\u901a\u77e5",
    "\u6807\u51c6",
    "\u76d1\u7ba1",
    "\u529e\u6cd5",
    "\u89c4\u5b9a",
    "\u6cd5\u6848",
    "\u89c4\u5219",
    "\u4fee\u8ba2",
    "\u4fee\u6b63",
    "\u53d8\u5316",
    "\u8c03\u6574",
    "\u8c41\u514d",
    "\u6761\u6b3e",
    "\u751f\u6548",
    "\u5b9e\u65bd",
    "\u51fa\u5883",
    "\u8ba4\u8bc1",
)

ACADEMIC_MARKERS: Final[tuple[str, ...]] = (
    "\u8bba\u6587",
    "\u7814\u7a76",
    "\u7efc\u8ff0",
    "\u5b9e\u9a8c",
    "\u4f5c\u8005",
    "\u5f15\u7528",
    "\u8bc4\u6d4b",
    "\u57fa\u51c6",
    "\u8c03\u7814",
    "arxiv",
    "doi",
    "survey",
    "review",
    "benchmark",
)

INDUSTRY_MARKERS: Final[tuple[str, ...]] = (
    "\u516c\u53f8",
    "\u4f01\u4e1a",
    "\u5e02\u573a",
    "\u884c\u4e1a",
    "\u65b9\u6848",
    "\u4ea7\u54c1",
    "\u7ade\u4e89",
    "\u8425\u6536",
    "\u4ea7\u4e1a",
    "\u9500\u91cf",
    "\u51fa\u8d27",
    "\u4efd\u989d",
    "\u9884\u6d4b",
    "\u4f9b\u5e94\u94fe",
    "\u843d\u5730",
    "\u670d\u52a1\u5668",
    "gpu",
    "\u82af\u7247",
)

ROUTE_SOURCE_FAMILIES: Final[dict[ConcreteRoute, tuple[str, ...]]] = {
    "policy": (
        "official_government",
        "regulator",
        "standards_body",
        "official_interpretation",
    ),
    "academic": (
        "academic_metadata",
        "paper_repository",
        "citation_index",
    ),
    "industry": (
        "company_official",
        "industry_association",
        "trusted_news",
        "general_web",
    ),
}
