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


class TransitTests(unittest.TestCase):
    def test_bus_question_moves_outskirts_to_car_list(self):
        result = agent.search_activities("야경", by_transit=True)
        names = [a["이름"] for a in result["activities"]]
        self.assertFalse(any("귀산" in n or "저도" in n for n in names))
        self.assertTrue(any("저도" in a["이름"] for a in result["car_recommended"]))
        answer = agent.run_agent("이번 주말 버스로 갈 만한 야경 명소 추천해 줘", PROFILE).answer
        self.assertIn("차로 가면 좋은 곳", answer)
        with_car = agent.search_activities("야경", by_transit=False)
        self.assertTrue(any("저도" in a["이름"] for a in with_car["activities"]))


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

    def test_codyssey_base_url_sends_anthropic_messages_format(self):
        import json as _json
        import anthropic
        try:
            import httpx2 as httpx
        except ImportError:  # 다른 SDK 버전
            import httpx
        seen = {}

        def handler(request):
            body = _json.loads(request.content)
            seen.update(url=str(request.url), key=request.headers.get("x-api-key"),
                        version=request.headers.get("anthropic-version"), body=body)
            return httpx.Response(200, json={"id": "m", "type": "message", "role": "assistant", "model": body["model"],
                                             "content": [{"type": "text", "text": "안녕하세요"}], "stop_reason": "end_turn",
                                             "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}})

        client = anthropic.Anthropic(api_key="vk-test", base_url="https://copa.codyssey.kr",
                                     http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        result = agent.run_agent("안녕하세요", PROFILE, provider="anthropic", client=client, model="claude-sonnet-4")
        self.assertEqual(result.mode, "llm")
        self.assertEqual(seen["url"], "https://copa.codyssey.kr/v1/messages")
        self.assertEqual(seen["key"], "vk-test")
        self.assertEqual(seen["version"], "2023-06-01")
        self.assertEqual(seen["body"]["model"], "claude-sonnet-4")
        self.assertIn("max_tokens", seen["body"])
        self.assertIn("system", seen["body"])

    def test_openai_tool_loop(self):
        client = FakeOpenAI([oa_tool("lookup_dialect", '{"expression": "욕봤데이"}'), oa_text("문헌 기준 뜻으로 '수고했다'예요.")])
        result = agent.run_agent("욕봤데이 뜻?", PROFILE, provider="openai", client=client)
        self.assertEqual(result.mode, "llm")
        self.assertIn("수고했다", result.answer)


if __name__ == "__main__":
    unittest.main()
