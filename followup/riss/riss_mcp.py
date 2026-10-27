# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=2.3,<3"]
# ///
"""RISS 검색 API를 클로드 코드·코덱스에 연결하는 MCP 서버 (후속자료, 2026-10-27).

키는 둘 중 하나로 줍니다.
  1) 이 파일과 같은 폴더의 riss_key.txt 에 키 한 줄
  2) 환경 변수 RISS_API_KEY

키가 되는지 먼저 확인:   uv run riss_mcp.py --test 직업교육
클로드 코드에 연결:      claude mcp add riss --scope user -- uv run C:\\tools\\riss\\riss_mcp.py
코덱스에 연결:           codex mcp add riss -- uv run C:\\tools\\riss\\riss_mcp.py

RISS 검색 API 결과는 BY-NC-ND 조건입니다(출처 표시, 영리 이용·2차 저작물 금지).
"""
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

API_URL = "https://www.riss.kr/openApi"
KEY_FILE = Path(__file__).with_name("riss_key.txt")

# 자료 종류 → RISS type 값. 공개강의(K)·CALIS는 키 승인 범위에 따라 '인증 오류'가 나서 뺐습니다.
KINDS = {"학위논문": "T", "국내학술논문": "A", "해외학술논문": "O", "단행본": "U", "연구보고서": "F", "학술지": "S"}
FIELDS = {"전체": "keyword", "제목": "title", "저자": "author", "주제어": "subject",
          "발행처": "publisher", "초록": "abstract", "목차": "toc"}
SORTS = {"관련도": None, "최신순": ("Y", "D"), "오래된순": ("Y", "A"), "제목순": ("T", "A")}
LABELS = {"type": "유형", "title": "제목", "author": "저자", "publisher": "발행처", "pubdate": "발행연도",
          "stitle": "학술지", "vol": "권", "no": "호", "reg": "등재", "mtype": "자료유형",
          "abstract": "초록있음", "toc": "목차있음", "image": "원문있음", "issn": "ISSN"}
TYPE_NAMES = {"T": "학위논문", "A": "국내학술논문", "O": "해외학술논문", "U": "단행본",
              "F": "연구보고서", "G": "연구보고서", "E": "연구보고서", "S": "학술지", "K": "공개강의"}


def read_key():
    key = os.environ.get("RISS_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8-sig").strip()
    if not key:
        raise RuntimeError(f"RISS API 키가 없습니다. {KEY_FILE} 에 키를 한 줄로 넣거나 환경 변수 RISS_API_KEY를 설정하세요.")
    return key


def search(query, kind="국내학술논문", field="전체", start_year=None, end_year=None,
           count=20, page=1, sort="관련도"):
    if kind not in KINDS:
        raise ValueError(f"kind는 {', '.join(KINDS)} 중 하나여야 합니다.")
    if field not in FIELDS:
        raise ValueError(f"field는 {', '.join(FIELDS)} 중 하나여야 합니다.")
    if sort not in SORTS:
        raise ValueError(f"sort는 {', '.join(SORTS)} 중 하나여야 합니다.")
    count = max(1, min(int(count), 100))          # RISS는 한 번에 100건까지
    page = max(1, int(page))
    params = {"key": read_key(), "version": "1.0", "type": KINDS[kind], FIELDS[field]: query,
              "rowcount": count, "rsnum": (page - 1) * count + 1}
    # RISS는 시작·끝 연도 중 하나만 주면 0건을 돌려줘서, 빈 쪽을 채워 둘 다 보냅니다.
    if start_year or end_year:
        params["spubdate"] = int(start_year or 1900)
        params["epubdate"] = int(end_year or date.today().year)
    if SORTS[sort]:
        params["sort"], params["asc"] = SORTS[sort]
    # 한글 검색어는 반드시 UTF-8로 인코딩해서 보냅니다(urlencode가 해 줌).
    with urllib.request.urlopen(API_URL + "?" + urllib.parse.urlencode(params), timeout=30) as r:
        root = ET.fromstring(r.read())
    head = root.find("head")
    error, message = head.findtext("Error", "0"), head.findtext("ErrorMessage", "")
    if error not in ("0", ""):
        hint = " (키가 틀렸거나, 이 자료 종류는 키 승인 범위 밖입니다)" if error == "004" else ""
        raise RuntimeError(f"RISS 오류 {error}: {message}{hint}")
    items = []
    for m in root.findall("metadata"):
        item = {}
        for child in m:
            tag = child.tag.removeprefix("riss.")
            text = (child.text or "").strip()
            if tag == "url":
                item["링크"] = text
            elif tag == "type":
                item["유형"] = TYPE_NAMES.get(text, text)
            elif tag == "charge":
                item["원문요금"] = {"1": "무료", "0": "유료"}.get(text, text)
            elif tag in LABELS and text:
                item[LABELS[tag]] = text
        items.append(item)
    return {"검색어": query, "자료종류": kind, "전체건수": int(head.findtext("totalcount", "0")),
            "페이지": page, "이번결과": len(items), "결과": items,
            "출처": "RISS 학술연구정보서비스(KERIS) 검색 API"}


def main():
    from mcp.server import MCPServer

    server = MCPServer("riss", instructions="RISS(학술연구정보서비스)에서 국내외 학술논문·학위논문·연구보고서·단행본·학술지를 검색합니다. "
                                            "결과는 서지 정보와 링크이며 초록 본문은 오지 않습니다.")

    @server.tool()
    def riss_search(query: str, kind: str = "국내학술논문", field: str = "전체",
                    start_year: int | None = None, end_year: int | None = None,
                    count: int = 20, page: int = 1, sort: str = "관련도") -> dict:
        """RISS에서 문헌을 검색합니다.

        query: 검색어 (예: "직업교육", "생성형 AI 교육")
        kind: 학위논문 | 국내학술논문 | 해외학술논문 | 단행본 | 연구보고서 | 학술지
        field: 전체 | 제목 | 저자 | 주제어 | 발행처 | 초록 | 목차 (어디에서 찾을지)
        start_year, end_year: 발행연도 범위 (예: 2020, 2026)
        count: 한 번에 받을 건수 (1~100), page: 몇 번째 묶음인지 (1부터)
        sort: 관련도 | 최신순 | 오래된순 | 제목순
        """
        return search(query, kind, field, start_year, end_year, count, page, sort)

    server.run()  # stdio


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) >= 2 and sys.argv[1] == "--test":
        q = " ".join(sys.argv[2:]) or "직업교육"
        res = search(q, count=3, sort="최신순")
        print(f"키 확인 성공: '{q}' 국내학술논문 {res['전체건수']:,}건 중 최신 3건")
        for i, it in enumerate(res["결과"], 1):
            print(f"  {i}. {it.get('발행연도', '')} | {it.get('학술지', '')} | {it.get('제목', '')[:40]}")
    else:
        main()
