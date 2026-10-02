import unittest
from datetime import date
from types import SimpleNamespace

import agent

PROFILE = {
    "nickname": "코디2026", "age": 28, "move_in_date": date(2026, 9, 20), "home_district": None,
    "previous_residence_years": 2, "employed_in_changwon": True,
}


class FakeAnthropic:
    """미리 정한 응답을 순서대로 돌려주는 가짜 Anthropic 클라이언트."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def tool_use(name, args, tool_id="t1"):
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name=name, input=args, id=tool_id)], stop_reason="tool_use")


def text(value):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=value)], stop_reason="end_turn")


class FakeOpenAI:
    def __init__(self, responses):
        self.responses = list(responses)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return self.responses.pop(0)


def oa_tool(name, arguments):
    call = SimpleNamespace(id="c1", function=SimpleNamespace(name=name, arguments=arguments))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call]))])


def oa_text(value):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=value, tool_calls=None))])


class ToolTests(unittest.TestCase):
    def test_policy_search_returns_verified_fields_without_planning_notes(self):
        result = agent.search_policies("월세")
        self.assertGreaterEqual(result["count"], 2)
        dumped = str(result)
        self.assertNotIn("[서비스 기획 아이디어]", dumped)
        self.assertTrue(all(p["링크"].startswith("https://") for p in result["policies"]))

    def test_activity_search_filters_indoor_and_district(self):
        result = agent.search_activities("카페", district="성산구", indoor_only=True)
        self.assertTrue(all(a["구"] == "성산구" and a["실내·실외"] == "실내" for a in result["activities"]))
        self.assertIn("특정 업체 홍보 아님", result["note"])

    def test_dialect_lookup_found_and_missing(self):
        self.assertTrue(agent.lookup_dialect("'욕봤데이'")["found"])
        self.assertFalse(agent.lookup_dialect("전혀없는말")["found"])

    def test_complaint_levels_and_situation(self):
        self.assertIn("112", agent.find_complaint_channel("긴급")["연락처"])
        situation = agent.get_my_situation(PROFILE)
        self.assertEqual(situation["기업노동자 전입지원금 판정"]["신청 가능 예정일"], "2027-03-20")
        self.assertNotIn("닉네임", str(situation))


class SafetyAndRuleTests(unittest.TestCase):
    def test_emergency_and_crisis_skip_llm(self):
        client = FakeAnthropic([])
        result = agent.run_agent("집에 불이 났어요", PROFILE, provider="anthropic", client=client)
        self.assertEqual(result.mode, "emergency")
        self.assertEqual(client.calls, [])
        crisis = agent.run_agent("요즘 죽고 싶어요", PROFILE, provider="anthropic", client=client)
        self.assertEqual(crisis.mode, "crisis")
        self.assertIn("109", crisis.answer)

    def test_rule_fallback_without_key_handles_out_of_scope(self):
        result = agent.run_agent("주식 추천해 줘", PROFILE)
        self.assertEqual(result.mode, "rule")
        self.assertIn("1899-1111", result.answer)
        dialect = agent.run_agent("'단디 해래이' 무슨 뜻?", PROFILE)
        self.assertIn("문헌 기준 뜻", dialect.answer)

    def test_verify_rejects_unknown_phone_and_url(self):
        ok, unknown = agent.verify_answer("055-123-4567로 전화하거나 https://fake.example.com 보세요", [{}])
        self.assertFalse(ok)
        self.assertEqual(len(unknown), 2)
        self.assertTrue(agent.verify_answer("창원시 콜센터 1899-1111, 긴급 119", [{}])[0])


class LLMLoopTests(unittest.TestCase):
    def test_anthropic_tool_loop_answers_from_tool_and_logs(self):
        client = FakeAnthropic([
            tool_use("get_my_situation", {}),
            text("기업노동자 전입지원금은 조건부 해당 가능이에요. 2027-03-20 이후 신청할 수 있어요."),
        ])
        result = agent.run_agent("내가 받을 수 있는 지원 알려줘", PROFILE, provider="anthropic", client=client)
        self.assertEqual(result.mode, "llm")
        self.assertTrue(result.verified)
        self.assertIn("2027-03-20", result.answer)
        self.assertTrue(any(s["단계"] == "도구 호출" and "get_my_situation" in s["내용"] for s in result.steps))
        self.assertEqual(client.calls[0]["model"], "claude-haiku-4-5-20251001")
        sent = str(client.calls[1]["messages"])
        self.assertNotIn("코디2026", sent)  # 닉네임은 AI로 보내지 않음
        self.assertIn(("창원청년정보플랫폼 청년지원 서비스", agent.YOUTH_PLATFORM_URL), result.links)

    def test_unverified_contact_triggers_rewrite_then_rule_fallback(self):
        client = FakeAnthropic([
            tool_use("search_policies", {"keyword": "월세"}),
            text("월세는 055-999-0000으로 문의하세요."),
            tool_use("search_policies", {"keyword": "월세"}),
            text("월세는 055-999-0000으로 문의하세요."),
        ])
        result = agent.run_agent("월세 지원 있어?", PROFILE, provider="anthropic", client=client)
        self.assertEqual(result.mode, "rule")
        self.assertNotIn("055-999-0000", result.answer)
        self.assertTrue(any("규칙 기반" in s["내용"] for s in result.steps))

    def test_api_error_falls_back_to_rules(self):
        class Broken:
            messages = SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("401")))
        result = agent.run_agent("월세 지원 있어?", PROFILE, provider="anthropic", client=Broken())
        self.assertEqual(result.mode, "rule")
        self.assertTrue(any(s["단계"] == "AI 연결 오류" for s in result.steps))

    def test_openai_tool_loop(self):
        client = FakeOpenAI([oa_tool("lookup_dialect", '{"expression": "욕봤데이"}'), oa_text("문헌 기준 뜻으로 '수고했다'예요.")])
        result = agent.run_agent("욕봤데이 뜻?", PROFILE, provider="openai", client=client)
        self.assertEqual(result.mode, "llm")
        self.assertIn("수고했다", result.answer)


if __name__ == "__main__":
    unittest.main()
