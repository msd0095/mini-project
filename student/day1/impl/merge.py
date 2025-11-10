# -*- coding: utf-8 -*-
"""
Day1 결과 정규화
- 다양한 원시 결과(results dict)를 "표준 스키마"로 정리
"""

from typing import Dict, Any, List


def _top_results(items: List[Dict[str, Any]], k: int = 5) -> List[Dict[str, Any]]:
    """
    검색 결과에서 상위 k개만 반환 (None/빈 리스트 안전 처리)
    - items가 None이면 [] 반환
    - k가 0 이하이면 [] 반환
    """
    # ----------------------------------------------------------------------------
    # TODO[DAY1-M-01] 구현 지침
    #  - if not items: return []
    #  - return items[: max(0, k)]
    # ----------------------------------------------------------------------------

    if not items:
      return []
    # k가 음수이거나 비정상이면 0으로 처리
    try:
        k = int(k)
    except Exception:
        k = 0
    return items[: max(0, k)]



def merge_day1_payload(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    입력(results) 예:
      {
        "type":"web_results",
        "query":"AAPL 주가와 기업 정보",
        "analysis": {... Day1Plan asdict ...},
        "items":[{title,url,snippet,...}, ...],
        "tickers":[{symbol,price,currency}|{symbol,error}, ...],
        "company_profile":"요약 텍스트",
        "profile_sources":[url1,url2,...],
        "errors":[...]
      }

    출력(정규화) 예:
      {
        "type":"day1",
        "query": "...",
        "web_top":[... 상위 N개 ...],
        "prices":[...],
        "company_profile":"...",
        "profile_sources":[...],
        "errors":[...]
      }
    """
    # ----------------------------------------------------------------------------
    # TODO[DAY1-M-02] 구현 지침
    #  - web_top = _top_results(results.get("items"), k=5)
    #  - prices  = results.get("tickers", [])
    #  - company_profile = results.get("company_profile") or ""
    #  - profile_sources = results.get("profile_sources") or []
    #  - errors = results.get("errors") or []
    #  - query  = results.get("query", "")
    #  - return {...} 형태로 표준 스키마 dict 생성
    # ----------------------------------------------------------------------------

    results = results or {} #results가 None이더라도 빈 dict로 null 안전 처리

    web_top = _top_results(results.get("items"), k=5) #상위 5건만 뽑아 후속 처리 부담 감소.
    prices = results.get("tickers") or [] #키 없음/값이 None 모두 []로 보정
    company_profile = results.get("company_profile") or "" #문자열 기본값
    profile_sources = results.get("profile_sources") or [] #리스트 기본값
    errors = results.get("errors") or [] #리스트 기본값
    query = results.get("query") or "" #문자열 기본값

    return {
        "type": "day1",
        "query": query,
        "web_top": web_top,
        "prices": prices,
        "company_profile": company_profile,
        "profile_sources": profile_sources,
        "errors": errors,
    }
    # 위 값을 모아 표준 스키마 사전으로 반환