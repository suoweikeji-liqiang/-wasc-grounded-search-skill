from skill.orchestrator.intent import classify_query


def test_classify_query_core_behaviors() -> None:
    policy = classify_query("人工智能监管条例最新要求")
    assert policy.route_label == "policy"

    academic = classify_query("RAG论文综述与引用趋势")
    assert academic.route_label == "academic"

    short = classify_query("AI政策")
    assert short.route_label == "mixed"
    assert short.reason_code == "short_query"
    assert short.primary_route in {"policy", "academic", "industry"}
    assert short.supplemental_route is None

    weak = classify_query("AI")
    assert weak.route_label == "mixed"
    assert weak.primary_route == "policy"
    assert weak.supplemental_route is None

    mixed = classify_query("自动驾驶政策对行业影响")
    assert mixed.route_label == "mixed"
    assert mixed.primary_route in {"policy", "industry", "academic"}
    assert mixed.supplemental_route is not None
