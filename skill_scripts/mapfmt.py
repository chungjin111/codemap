#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""map.txt — 분석 결과를 적는 간결 표기.

JSON(analysis.json)과 같은 내용을 훨씬 적은 글자로 적는다. LLM의 출력 토큰은
입력보다 몇 배 비싼데, JSON은 따옴표·괄호·키 이름·id·들여쓰기가 절반 가까이를
차지한다. 이 표기는 그 구조 부분을 기호 몇 개로 줄인다.

    # 프로젝트 제목
    프로젝트 요약.

    ## 박스 제목 @파일경로
    박스 요약.
    -> 다른 박스 제목 : 연결 라벨
    ### 하위 박스 제목
    요약.
    ~ 코드 제목 @함수이름
    설명 문장들.
    12-15: 이 줄들에 대한 설명
    18: 한 줄 설명

- `#` 개수가 깊이다 (`#` 프로젝트, `##` 최상위 박스, `###` 그 하위 …). 들여쓰기는 무시한다.
- `@` 뒤는 참조다. 박스 줄에서는 파일 경로, 코드 줄에서는
  `@함수이름` · `@클래스.메서드` · `@12-30` · `@경로:12-30` · `@경로::함수이름` 중 하나.
  코드 줄에 파일이 없으면 가장 가까운 상위 박스의 파일을 쓴다.
- id 는 쓰지 않는다. 연결(`->`)은 상대 박스의 제목으로 가리킨다.
- `!unordered` : 최상위 박스에 순서가 없음.  `!flow` : 이 박스의 하위에 순서가 있음.
- 일반 문장이 `#`, `~`, `->`, `!`, `숫자:` 로 시작해야 하면 맨 앞에 `\\` 를 붙인다.
"""
from __future__ import annotations

import re

HEAD_RE = re.compile(r"^(#{1,8})\s+(.*)$")
CODE_RE = re.compile(r"^~\s+(.*)$")
LINK_RE = re.compile(r"^->\s*(.+?)(?:\s+:\s+(.*))?$")
POINT_RE = re.compile(r"^(\d+)(?:\s*[-–]\s*(\d+))?\s*[:：]\s+(.*)$")
REF_RE = re.compile(r"^(.*\S)\s+@(\S.*)$")
ESC_RE = re.compile(r"^(#{1,8}\s|~\s|->|!|\\|\d+(?:\s*[-–]\s*\d+)?\s*[:：]\s)")


def _split_ref(s):
    m = REF_RE.match(s)
    return (m.group(1).strip(), m.group(2).strip()) if m else (s.strip(), None)


def _code_ref(ref, code):
    if "::" in ref:
        f, sym = ref.split("::", 1)
        code["file"], code["symbol"] = f, sym
        return
    m = re.match(r"^(?:(.+):)?(\d+)(?:-(\d+))?$", ref)
    if m:
        if m.group(1):
            code["file"] = m.group(1)
        a = int(m.group(2))
        code["lines"] = [a, int(m.group(3) or a)]
    else:
        code["symbol"] = ref


def parse(text):
    """map.txt 본문 → (analysis dict, 오류 목록). dict 는 analysis.json 과 같은 모양이다."""
    an = {"title": "", "summary": "", "nodes": [], "links": []}
    errors, links_raw, order = [], [], []
    stack = []                       # [(level, node)]
    node = code = None
    target = an                      # 일반 문장이 붙을 곳: an / node / code / point(dict)
    key = "summary"
    blank = False

    def add_text(s):
        cur = target.get(key, "")
        target[key] = s if not cur else cur + ("\n\n" if blank else " ") + s

    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            blank = True
            continue
        if line.startswith("\\"):
            add_text(line[1:])
            blank = False
            continue
        m = HEAD_RE.match(line)
        if m:
            level = len(m.group(1))
            title, ref = _split_ref(m.group(2))
            if level == 1:
                if an["title"] or an["nodes"]:
                    errors.append("%d줄: `#` 한 개짜리 제목은 맨 위에 한 번만 쓴다" % no)
                an["title"] = m.group(2).strip()
                node = code = None
                target, key = an, "summary"
            else:
                while stack and stack[-1][0] >= level:
                    stack.pop()
                if level > (stack[-1][0] + 1 if stack else 2):
                    errors.append("%d줄: '%s' — 깊이를 건너뛰었다 (`#` 를 하나씩만 늘릴 것)" % (no, title))
                node = {"title": title, "summary": ""}
                if ref:
                    node["file"] = ref
                if stack:
                    stack[-1][1].setdefault("children", []).append(node)
                else:
                    an["nodes"].append(node)
                stack.append((level, node))
                order.append(node)
                code = None
                target, key = node, "summary"
        elif line == "!unordered":
            an["ordered"] = False
        elif line == "!flow":
            if node is None:
                errors.append("%d줄: `!flow` 앞에 박스가 없다" % no)
            else:
                node["flow"] = True
        elif CODE_RE.match(line):
            title, ref = _split_ref(CODE_RE.match(line).group(1))
            if node is None:
                errors.append("%d줄: 코드 '%s' 앞에 박스(`##`)가 없다" % (no, title))
                blank = False
                continue
            code = {"title": title, "explain": "", "points": []}
            if ref:
                _code_ref(ref, code)
            else:
                errors.append("%d줄: 코드 '%s' 에 참조(@함수이름 또는 @시작-끝)가 없다" % (no, title))
            node.setdefault("code", []).append(code)
            target, key = code, "explain"
        elif LINK_RE.match(line):
            m = LINK_RE.match(line)
            if node is None:
                errors.append("%d줄: `->` 앞에 박스가 없다" % no)
            else:
                links_raw.append((node, m.group(1).strip(), (m.group(2) or "").strip(), no))
        elif code is not None and POINT_RE.match(line):
            m = POINT_RE.match(line)
            a = int(m.group(1))
            pt = {"lines": [a, int(m.group(2) or a)], "text": m.group(3).strip()}
            code["points"].append(pt)
            target, key = pt, "text"
        else:
            add_text(line)
        blank = False

    for i, n in enumerate(order, 1):
        n["id"] = "n%d" % i
    by_title = {}
    for n in order:
        by_title.setdefault(n["title"], []).append(n)
    for src, title, label, no in links_raw:
        hits = by_title.get(title, [])
        if len(hits) != 1:
            errors.append("%d줄: `-> %s` — 그 제목의 박스가 %s" % (
                no, title, "없다" if not hits else "여러 개다 (제목을 구별되게 쓸 것)"))
            continue
        an["links"].append({"from": src["id"], "to": hits[0]["id"], "label": label})
    if not an["title"]:
        errors.append("맨 위에 `# 프로젝트 제목` 이 없다")
    return an, errors


def _esc(line):
    return "\\" + line if ESC_RE.match(line) else line


def _paras(s):
    out = []
    for i, p in enumerate(str(s or "").split("\n\n")):
        p = " ".join(p.split())
        if not p:
            continue
        if out:
            out.append("")
        out.append(_esc(p))
    return out


def dump(an):
    """analysis dict → map.txt 본문 (기존 analysis.json 을 옮길 때 쓴다)."""
    titles = {}

    def index(nodes):
        for n in nodes or []:
            if n.get("id"):
                titles[n["id"]] = n["title"]
            index(n.get("children"))
    index(an.get("nodes"))
    links = {}
    for l in an.get("links") or []:
        links.setdefault(l["from"], []).append(l)

    out = ["# " + an.get("title", "")]
    out.extend(_paras(an.get("summary")))
    if an.get("ordered") is False:
        out.append("!unordered")

    def emit(n, level, inherited):
        out.append("")
        out.append("#" * level + " " + n["title"] + (" @" + n["file"] if n.get("file") else ""))
        out.extend(_paras(n.get("summary")))
        if n.get("flow"):
            out.append("!flow")
        for l in links.get(n.get("id"), []):
            out.append("-> %s%s" % (titles.get(l["to"], l["to"]), " : " + l["label"] if l.get("label") else ""))
        f = n.get("file") or inherited
        for c in n.get("code") or []:
            other = c.get("file") if c.get("file") and c.get("file") != f else None
            if c.get("symbol") and not c.get("lines"):
                ref = (other + "::" if other else "") + c["symbol"]
            else:
                a, b = c["lines"]
                ref = (other + ":" if other else "") + ("%d-%d" % (a, b) if a != b else str(a))
            out.append("~ %s @%s" % (c.get("title", ""), ref))
            out.extend(_paras(c.get("explain")))
            for p in c.get("points") or []:
                pr = p["lines"] if isinstance(p["lines"], list) else [p["lines"], p["lines"]]
                span = "%d-%d" % tuple(pr) if pr[0] != pr[1] else str(pr[0])
                out.append("%s: %s" % (span, " ".join(str(p["text"]).split())))
        for ch in n.get("children") or []:
            emit(ch, level + 1, f)

    for n in an.get("nodes") or []:
        emit(n, 2, None)
    return "\n".join(out) + "\n"


if __name__ == "__main__":      # analysis.json → map.txt 변환:  mapfmt.py analysis.json > map.txt
    import json
    import sys
    with open(sys.argv[1], encoding="utf-8") as fp:
        sys.stdout.write(dump(json.load(fp)))
