# -*- coding: utf-8 -*-
"""
Day2 인덱싱 엔트리포인트
- 목표: 코퍼스 생성 → 임베딩 → FAISS 저장 + docs.jsonl 저장
"""

import os, argparse, numpy as np
from typing import List

from student.day2.impl.ingest import build_corpus, save_docs_jsonl
from student.day2.impl.embeddings import Embeddings
from student.day2.impl.store import FaissStore  # 제공됨


def build_index(paths: List[str], index_dir: str, model: str | None = None, batch_size: int = 128):
    """
    절차:
      1) corpus = build_corpus(paths)
         - [{"id":..., "text":..., "meta":{...}}, ...]
      2) texts = [item["text"] for item in corpus]
      3) emb = Embeddings(model=model, batch_size=batch_size)
         vecs = emb.encode(texts)  # (N, D) L2 정규화된 np.ndarray
      4) index_path = os.path.join(index_dir, "faiss.index")
         docs_path  = os.path.join(index_dir, "docs.jsonl")
      5) store = FaissStore(dim=vecs.shape[1], index_path=index_path, docs_path=docs_path)
         store.add(vecs, corpus); store.save()
      6) save_docs_jsonl(corpus, docs_path)
    """
    # 1) 코퍼스 생성
    corpus = build_corpus(paths)  # [{"id":..., "text":..., "meta":{...}}, ...]
    if not corpus:
        raise ValueError("build_corpus 결과가 비어 있습니다. 유효한 입력 경로를 확인하세요.")

    # 2) 텍스트 추출
    texts = [item.get("text", "") for item in corpus]
    if not any(texts):
        raise ValueError("코퍼스에서 텍스트를 찾지 못했습니다.")

    # 3) 임베딩 계산
    emb = Embeddings(model=model, batch_size=batch_size)
    vecs = emb.encode(texts)  # (N, D) numpy.ndarray (L2 정규화 가정)
    if not isinstance(vecs, np.ndarray) or vecs.ndim != 2:
        raise ValueError("임베딩 결과가 2차원 numpy 배열이 아닙니다.")
    if vecs.shape[0] != len(corpus):
        raise ValueError("임베딩 벡터 수와 문서 수가 일치하지 않습니다.")

    # ✅ 메모리/호환성 최적화: float32로 캐스팅
    if vecs.dtype != np.float32:
        vecs = vecs.astype(np.float32, copy=False)

    # 4) 경로 준비
    os.makedirs(index_dir, exist_ok=True)
    index_path = os.path.join(index_dir, "faiss.index")
    docs_path = os.path.join(index_dir, "docs.jsonl")

    # 5) 인덱스 저장
    store = FaissStore(dim=vecs.shape[1], index_path=index_path, docs_path=docs_path)
    store.add(vecs, corpus)
    store.save()

    # 6) 문서 메타 저장(jsonl)
    save_docs_jsonl(corpus, docs_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", nargs="+", required=True)
    ap.add_argument("--index_dir", default="indices/day2")
    ap.add_argument("--model", default=None)
    ap.add_argument("--batch_size", type=int, default=128)
    args = ap.parse_args()

    os.makedirs(args.index_dir, exist_ok=True)
    build_index(args.paths, args.index_dir, args.model, args.batch_size)
 