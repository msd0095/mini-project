# -*- coding: utf-8 -*-
"""
Day1 본체
- 역할: 웹 검색 / 주가 / 기업개요(추출+요약)를 병렬로 수행하고 결과를 정규 스키마로 병합
"""

from __future__ import annotations
from dataclasses import asdict
from typing import Optional, Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.adk.models.lite_llm import LiteLlm
# from kt_aivle.sub_agents.common.schemas import Day1Plan
# from kt_aivle.sub_agents.day1.impl.merge import merge_day1_payload
# # 외부 I/O
# from kt_aivle.sub_agents.day1.impl.tavily_client import search_tavily, extract_url
# from kt_aivle.sub_agents.day1.impl.finance_client import get_quotes
# from kt_aivle.sub_agents.day1.impl.web_search import (
#     looks_like_ticker,
#     search_company_profile,
#     extract_and_summarize_profile,
# )


from student.common.schemas import Day1Plan
from student.day1.impl.merge import merge_day1_payload
# 외부 I/O
from student.day1.impl.tavily_client import search_tavily, extract_url
from student.day1.impl.finance_client import get_quotes
from student.day1.impl.web_search import (
    looks_like_ticker,
    search_company_profile,
    extract_and_summarize_profile,
)

DEFAULT_WEB_TOPK = 6
MAX_WORKERS = 4
DEFAULT_TIMEOUT = 20

# ------------------------------------------------------------------------------
# TODO[DAY1-I-01] 요약용 경량 LLM 준비
#  - 목적: 기업 개요 본문을 Extract 후 간결 요약
#  - LiteLlm(model="openai/gpt-4o-mini") 형태로 _SUM에 할당
# ------------------------------------------------------------------------------
_SUM: Optional[LiteLlm] = None


def _summarize(text: str) -> str:
    """
    입력 텍스트를 LLM으로 3~5문장 수준으로 요약합니다.
    실패 시 빈 문자열("")을 반환해 상위 로직이 안전하게 진행되도록 합니다.
    """
    # ----------------------------------------------------------------------------
    # TODO[DAY1-I-02] 구현 지침
    #  - _SUM이 None이면 "" 반환(요약 생략)
    #  - _SUM.invoke({...}) 혹은 단순 텍스트 인자 형태로 호출 가능한 래퍼라면
    #    응답 객체에서 본문 텍스트를 추출하여 반환
    #  - 예외 발생 시 빈 문자열 반환
    # ----------------------------------------------------------------------------

    if _SUM is None:
        return ""

    try:
        # 입력이 너무 길 경우 LLM 요청 전 일부 잘라냄 (토큰 초과 방지용)
        if len(text) > 4000:
            text = text[:4000] + "..."

        prompt = f"다음 본문을 3~5문장으로 간결히 요약하세요:\n{text}"

        # invoke() 호출 시 dict 인자 또는 문자열 인자 모두 지원
        try:
            response = _SUM.invoke(prompt)
        except TypeError:
            response = _SUM.invoke({"prompt": prompt})

        # 다양한 응답 형태에 안전하게 대응
        if isinstance(response, str):
            return response.strip()

        if isinstance(response, dict):
            # 가능한 키 후보들 순차 탐색
            for key in ("output", "text", "content"):
                if key in response:
                    return str(response[key]).strip()

            # 혹시 응답 객체 안에 choices 형태라면
            if "choices" in response and isinstance(response["choices"], list):
                content = (
                    response["choices"][0]
                    .get("message", {})
                    .get("content", "")
                )
                return str(content).strip()

        # 예상 밖 형태면 문자열 변환
        return str(response).strip()

    except Exception as e:
        # 로그 찍거나 디버깅용으로는 e 출력 가능 (운영 시는 생략)
        return ""


class Day1Agent:
    def __init__(self, tavily_api_key: Optional[str], web_topk: int = DEFAULT_WEB_TOPK, request_timeout: int = DEFAULT_TIMEOUT):
        """
        필드 저장만 담당합니다.
        - tavily_api_key: Tavily API 키(없으면 웹 호출 실패 가능)
        - web_topk: 기본 검색 결과 수
        - request_timeout: 각 HTTP 호출 타임아웃(초)
        - e.g., agent = Day1Agent("TAVILY_KEY_123", web_topk=6, request_timeout=20)
        """
        # ----------------------------------------------------------------------------
        # TODO[DAY1-I-03] 필드 저장
        self.tavily_api_key = tavily_api_key
        self.web_topk = web_topk
        self.request_timeout = request_timeout
        # ----------------------------------------------------------------------------
        # raise NotImplementedError("TODO[DAY1-I-03]: __init__ 필드 초기화")

    def handle(self, query: str, plan: Day1Plan) -> Dict[str, Any]:
        """
        병렬 파이프라인:
          1) results 스켈레톤 만들기
             results = {"type":"web_results","query":query,"analysis":asdict(plan),"items":[],
                        "tickers":[], "errors":[], "company_profile":"", "profile_sources":[]}
          2) ThreadPoolExecutor(max_workers=MAX_WORKERS)에서 작업 제출:
             - plan.do_web: search_tavily(검색어, 키, top_k=self.web_topk, timeout=...)
             - plan.do_stocks: get_quotes(plan.tickers)
             - (기업개요) looks_like_ticker(query) 또는 plan에 tickers가 있을 때:
                 · search_company_profile(query, api_key, topk=2) → URL 상위 1~2개
                 · extract_and_summarize_profile(urls, api_key, summarizer=_summarize)
          3) as_completed로 결과 수집. 실패 시 results["errors"]에 '작업명:에러' 저장.
          4) merge_day1_payload(results) 호출해 최종 표준 스키마 dict 반환.
        """
        # ----------------------------------------------------------------------------
        # TODO[DAY1-I-04] 구현 지침(권장 구조)
        #  - results 초기화 (위 키 포함)
        #  - futures 딕셔너리: future -> "web"/"stock"/"profile" 등 라벨링
        #  - 병렬 제출 조건 체크(plan.do_web, plan.do_stocks, 기업개요 조건)
        #  - 완료 수집:
        #      kind == "web"    → results["items"] = data
        #      kind == "stock"  → results["tickers"] = data
        #      kind == "profile"→ results["company_profile"] = text; results["profile_sources"] = urls(옵션)
        #  - 예외: results["errors"].append(f"{kind}: {type(e).__name__}: {e}")
        #  - return merge_day1_payload(results)
        # ----------------------------------------------------------------------------

        results: Dict[str, Any] = {
            "type": "web_results",
            "query": query,
            "analysis": asdict(plan),
            "items": [],
            "tickers": [],
            "errors": [],
            "company_profile": "",
            "profile_sources": [],
        }

        # key: Future, value: 작업 종류 문자열
        futures: Dict[Any, str] = {}

        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # 1) 웹 검색
                if getattr(plan, "do_web", False):
                    f_web = executor.submit(
                        search_tavily,
                        query,
                        self.tavily_api_key,
                        top_k=self.web_topk,
                        timeout=self.request_timeout,
                    )
                    futures[f_web] = "web"

                # 2) 주가 조회 (tickers가 있을 때만)
                if getattr(plan, "do_stocks", False) and getattr(plan, "tickers", None):
                    f_stock = executor.submit(
                        get_quotes,
                        plan.tickers,
                    )
                    futures[f_stock] = "stock"

                # 3) 기업 개요 (티커처럼 보이거나, plan.tickers가 존재할 때)
                need_profile = (
                    looks_like_ticker(query)
                    or bool(getattr(plan, "tickers", []))
                )

                if need_profile:
                    def profile_task():
                        # (1) 기업 프로필용 URL 검색
                        urls = search_company_profile(
                            query,
                            self.tavily_api_key,
                            topk=2,
                        )

                        if not urls:
                            return "", []

                        # (2) URL 기반 본문 추출 + 요약
                        profile_text = extract_and_summarize_profile(
                            urls,
                            self.tavily_api_key,
                            summarizer=_summarize,
                        )

                        # 예외적인 타입 방어
                        if not isinstance(profile_text, str):
                            if profile_text is None:
                                profile_text = ""
                            else:
                                profile_text = str(profile_text)

                        return profile_text, urls

                    f_profile = executor.submit(profile_task)
                    futures[f_profile] = "profile"

                # 4) 완료된 future들 결과 수집
                for future in as_completed(futures):
                    kind = futures[future]
                    try:
                        data = future.result()
                    except Exception as e:
                        results["errors"].append(
                            f"{kind}: {type(e).__name__}: {e}"
                        )
                        continue

                    if kind == "web":
                        # None 방어
                        results["items"] = data if data is not None else []

                    elif kind == "stock":
                        # None 방어
                        results["tickers"] = data if data is not None else []

                    elif kind == "profile":
                        # (text, urls) 튜플 기대
                        if not data:
                            text, urls = "", []
                        else:
                            text, urls = data
                        results["company_profile"] = text or ""
                        results["profile_sources"] = urls or []

        except Exception as e:
            # executor 생성/submit 레벨의 예외도 기록
            results["errors"].append(f"executor: {type(e).__name__}: {e}")

        # 최종 병합
        return merge_day1_payload(results)
 