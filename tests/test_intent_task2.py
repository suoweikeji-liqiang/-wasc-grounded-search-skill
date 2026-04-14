from skill.orchestrator.intent import classify_query
from skill.orchestrator.query_traits import derive_query_traits


def test_classify_query_core_behaviors() -> None:
    policy = classify_query(
        "\u4eba\u5de5\u667a\u80fd\u76d1\u7ba1\u6761\u4f8b\u6700\u65b0\u8981\u6c42"
    )
    assert policy.route_label == "policy"

    academic = classify_query("RAG\u8bba\u6587\u7efc\u8ff0\u4e0e\u5f15\u7528\u8d8b\u52bf")
    assert academic.route_label == "academic"

    short = classify_query("AI\u653f\u7b56")
    assert short.route_label == "mixed"
    assert short.reason_code == "short_query"
    assert short.primary_route in {"policy", "academic", "industry"}
    assert short.supplemental_route is None

    weak = classify_query("AI")
    assert weak.route_label == "mixed"
    assert weak.primary_route == "policy"
    assert weak.supplemental_route is None

    mixed = classify_query(
        "\u81ea\u52a8\u9a7e\u9a76\u653f\u7b56\u5bf9\u884c\u4e1a\u5f71\u54cd"
    )
    assert mixed.route_label == "mixed"
    assert mixed.primary_route in {"policy", "industry", "academic"}
    assert mixed.supplemental_route is not None


def test_classify_query_competition_style_chinese_and_bilingual_cases() -> None:
    policy_change = classify_query(
        "\u0032\u0030\u0032\u0035\u5e74\u4e2a\u4eba\u4fe1\u606f\u51fa\u5883\u8ba4\u8bc1\u529e\u6cd5\u4fee\u8ba2\u4e86\u54ea\u4e9b\u6761\u6b3e"
    )
    assert policy_change.route_label == "policy"
    assert policy_change.primary_route == "policy"
    assert policy_change.supplemental_route is None

    industry_trend = classify_query(
        "\u0032\u0030\u0032\u0036\u5e74AI\u670d\u52a1\u5668GPU\u5e02\u573a\u4efd\u989d\u9884\u6d4b"
    )
    assert industry_trend.route_label == "industry"
    assert industry_trend.primary_route == "industry"
    assert industry_trend.supplemental_route is None

    industry_phone = classify_query(
        "\u4e2d\u56fd\u667a\u80fd\u624b\u673a\u0032\u0030\u0032\u0036\u5e74\u51fa\u8d27\u91cf\u8d8b\u52bf"
    )
    assert industry_phone.route_label == "industry"
    assert industry_phone.primary_route == "industry"
    assert industry_phone.supplemental_route is None

    academic_lookup = classify_query("LLM agent planning \u6700\u65b0\u7814\u7a76")
    assert academic_lookup.route_label == "academic"
    assert academic_lookup.primary_route == "academic"
    assert academic_lookup.supplemental_route is None

    mixed_impact = classify_query(
        "AI Act \u5bf9\u5f00\u6e90\u6a21\u578b\u548c\u4ea7\u4e1a\u843d\u5730\u5f71\u54cd"
    )
    assert mixed_impact.route_label == "mixed"
    assert mixed_impact.primary_route == "policy"
    assert mixed_impact.supplemental_route == "industry"


def test_derive_query_traits_detects_competition_style_signals() -> None:
    policy_traits = derive_query_traits(
        "\u0032\u0030\u0032\u0035\u5e74\u6570\u636e\u51fa\u5883\u5b89\u5168\u8bc4\u4f30\u529e\u6cd5\u6709\u54ea\u4e9b\u53d8\u5316"
    )
    assert policy_traits.has_year is True
    assert policy_traits.is_policy_change is True
    assert policy_traits.has_version_intent is True
    assert policy_traits.has_effective_date_intent is False

    industry_traits = derive_query_traits(
        "\u4e2d\u56fd\u667a\u80fd\u624b\u673a\u0032\u0030\u0032\u0036\u5e74\u51fa\u8d27\u91cf\u8d8b\u52bf"
    )
    assert industry_traits.has_year is True
    assert industry_traits.has_trend_intent is True

    mixed_traits = derive_query_traits(
        "AI Act \u5bf9\u5f00\u6e90\u6a21\u578b\u548c\u4ea7\u4e1a\u843d\u5730\u5f71\u54cd"
    )
    assert mixed_traits.is_cross_domain_impact is True

    date_traits = derive_query_traits(
        "\u6570\u636e\u51fa\u5883\u5b89\u5168\u8bc4\u4f30\u529e\u6cd5\u751f\u6548\u65f6\u95f4"
    )
    assert date_traits.has_effective_date_intent is True


def test_ascii_marker_boundary_matching_avoids_false_policy_hits() -> None:
    result = classify_query("react server benchmark")

    assert result.scores["policy"] == 0
    assert result.route_label == "mixed"
    assert result.primary_route in {"academic", "industry"}


def test_derive_query_traits_avoids_false_effective_date_and_tracks_vs_cross_domain() -> None:
    non_date_traits = derive_query_traits("cost-effective gpu deployment")
    assert non_date_traits.has_effective_date_intent is False

    for query in (
        "policy vs industry tradeoff",
        "\u653f\u7b56\u4e0e\u884c\u4e1a",
        "paper\u4e0epolicy",
        "law\u4e0epaper",
        "order\u4e0ebenchmark",
        "\u8bba\u6587\u4e0e\u653f\u7b56\u6bd4\u8f83",
        "\u653f\u7b56\u4e0e\u884c\u4e1a\u7ed3\u5408",
        "\u76d1\u7ba1\u4ea4\u53c9\u7814\u7a76",
    ):
        mixed_traits = derive_query_traits(query)
        assert mixed_traits.is_cross_domain_impact is True


def test_classify_query_hidden_like_english_single_domain_queries_stay_concrete() -> None:
    policy = classify_query(
        "NIS2 Directive transposition deadline adopt publish national measures official text"
    )
    assert policy.route_label == "policy"
    assert policy.primary_route == "policy"
    assert policy.supplemental_route is None

    academic = classify_query(
        "2025 retrieval-augmented generation citation grounding evaluation dataset factuality attribution"
    )
    assert academic.route_label == "academic"
    assert academic.primary_route == "academic"
    assert academic.supplemental_route is None

    industry = classify_query("TSMC 2025 capex guidance range official earnings materials")
    assert industry.route_label == "industry"
    assert industry.primary_route == "industry"
    assert industry.supplemental_route is None

    standards = classify_query(
        "RFC 9700 OAuth 2.1 legacy authorization flows grant types removed discouraged sections"
    )
    assert standards.route_label == "industry"
    assert standards.primary_route == "industry"
    assert standards.supplemental_route is None
