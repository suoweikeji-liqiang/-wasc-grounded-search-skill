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
    "影响",
    "对比",
    "比较",
    "vs",
    "与",
    "交叉",
    "结合",
    "政策对行业",
    "研究与监管",
)

POLICY_MARKERS: Final[tuple[str, ...]] = (
    "政策",
    "法规",
    "条例",
    "通知",
    "标准",
    "监管",
    "办法",
)

ACADEMIC_MARKERS: Final[tuple[str, ...]] = (
    "论文",
    "研究",
    "综述",
    "实验",
    "作者",
    "引用",
    "arxiv",
    "doi",
)

INDUSTRY_MARKERS: Final[tuple[str, ...]] = (
    "公司",
    "企业",
    "市场",
    "行业",
    "方案",
    "产品",
    "竞争",
    "营收",
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
