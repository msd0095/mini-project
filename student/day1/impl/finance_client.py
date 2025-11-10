# -*- coding: utf-8 -*-
"""
yfinance 가격 조회
- 목표: 티커 리스트에 대해 현재가/통화를 가져와 표준 형태로 반환

주의:
- Ticker.fast_info는 per-call timeout을 받지 않습니다. 아래 timeout 인자는 yfinance의
  fast_info 경로에는 적용되지 않으며, 서명 호환/향후 확장용으로만 유지합니다.
"""

from typing import List, Dict, Any
import re
import numbers


def _normalize_symbol(s: str) -> str:
    """
    6자리 숫자면 한국거래소(.KS) 보정.
      '005930' → '005930.KS'
      'AAPL'   → 'AAPL' (대문자/트림)
    """
    if s is None:
        return ""
    s = s.strip()
    if re.fullmatch(r"\d{6}", s):
        return f"{s}.KS"
    # 영문 티커는 대문자 통일
    return s.upper()


def get_quotes(symbols: List[str], timeout: int = 20) -> List[Dict[str, Any]]:
    """
    yfinance로 심볼별 시세를 조회해 리스트로 반환합니다.
    반환 예:
      [{"symbol":"AAPL","price":123.45,"currency":"USD"},
       {"symbol":"005930.KS","price":...,"currency":"KRW"}]
    실패시 해당 심볼은 {"symbol":sym, "error":"..."} 형태로 표기.

    참고:
    - Ticker.fast_info는 개별 요청 타임아웃 인자를 받지 않습니다.
    """
    out: List[Dict[str, Any]] = []

    # 입력 전처리: 빈 값/공백 필터
    clean_syms = []
    for s in symbols or []:
        ns = _normalize_symbol(s)
        if ns:
            clean_syms.append(ns)
        else:
            out.append({"symbol": str(s), "error": "invalid symbol"})
    if not clean_syms:
        return out

    try:
        from yfinance import Ticker  # 함수 내부 임포트(실행 환경에 yfinance 없을 수 있음)
    except Exception as e:
        for s in clean_syms:
            out.append({
                "symbol": s,
                "error": f"ImportError: {type(e).__name__}: {e}"
            })
        return out

    for sym in clean_syms:
        try:
            t = Ticker(sym)

            fi = getattr(t, "fast_info", None)

            price = None
            currency = None

            # dict-like 우선
            if isinstance(fi, dict):
                price = fi.get("last_price")
                currency = fi.get("currency")
            else:
                # 일부 버전에서 객체 속성처럼 보일 수 있음
                price = getattr(fi, "last_price", None)
                currency = getattr(fi, "currency", None)

            ok_price = isinstance(price, numbers.Real)
            ok_ccy = isinstance(currency, str) and bool(currency)

            if ok_price and ok_ccy:
                out.append({
                    "symbol": sym,
                    "price": float(price),
                    "currency": currency
                })
                continue

            # 정보 부족 시, 간단한 원인 표기
            missing = []
            if not ok_price:
                missing.append("price")
            if not ok_ccy:
                missing.append("currency")

            out.append({
                "symbol": sym,
                "error": f"missing fields: {', '.join(missing)}"
            })

        except Exception as e:
            out.append({"symbol": sym, "error": f"{type(e).__name__}: {e}"})

    return out