#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""3단계 · analysis.json + 템플릿 → 한 개짜리 HTML.

LLM이 쓴 analysis.json 에는 코드 원문이 없다. `file` 과 `lines` (또는 `symbol`)
참조만 있고, 실제 코드는 이 스크립트가 디스크에서 꺼내 끼워 넣는다.
(출력 토큰이 가장 비싸므로, LLM이 코드를 다시 타이핑하지 않게 하는 것이 핵심.)
"""
from __future__ import annotations

import datetime
import json
import os
import textwrap

import mapfmt
from scan import CODE_EXT
from skeleton import find_symbol, read_text

MAX_SNIPPET = 80      # 코드 조각 하나의 최대 줄 수
WARN_SNIPPET = 45


def _load(path):
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def build(out_dir, analysis_path=None, template_path=None, output=None):
    man = _load(os.path.join(out_dir, "manifest.json"))
    root = os.path.abspath(man["root"])
    errors, warns = [], []
    if analysis_path is None:   # map.txt(간결 표기)가 있으면 그것을, 없으면 analysis.json 을 쓴다
        map_path = os.path.join(out_dir, "map.txt")
        analysis_path = map_path if os.path.exists(map_path) else os.path.join(out_dir, "analysis.json")
    if not os.path.exists(analysis_path):
        raise SystemExit("분석 결과가 없습니다: %s (map.txt 또는 analysis.json)" % analysis_path)
    if analysis_path.endswith(".json"):
        try:
            an = _load(analysis_path)
        except ValueError as e:
            raise SystemExit("analysis.json 이 올바른 JSON이 아닙니다: %s" % e)
    else:
        with open(analysis_path, encoding="utf-8") as fp:
            an, errors = mapfmt.parse(fp.read())
    sk, plan = {}, {}
    sk_path = os.path.join(out_dir, "skeleton.json")
    if os.path.exists(sk_path):
        whole = _load(sk_path)
        sk, plan = whole["files"], whole.get("plan") or {}

    ids, used_files = set(), set()
    cache = {}
    stats = {"nodes": 0, "code": 0, "lines": 0, "depth": 0}

    def file_lines(path):
        if path not in cache:
            full = os.path.abspath(os.path.join(root, path))
            if not full.startswith(root + os.sep) or not os.path.isfile(full):
                cache[path] = None
            else:
                text = read_text(full)
                cache[path] = text.splitlines() if text is not None else None
        return cache[path]

    def do_code(c, where, default_file):
        path = c.get("file") or default_file
        label = "%s > 코드 '%s'" % (where, c.get("title", "?"))
        if not path:
            errors.append("%s: file 이 없음" % label)
            return None
        lines = file_lines(path)
        if lines is None:
            errors.append("%s: 파일을 찾을 수 없음 → %s" % (label, path))
            return None
        if c.get("symbol") and not c.get("lines"):
            hits = find_symbol(sk.get(path, {}).get("syms", []), c["symbol"])
            if not hits:
                errors.append("%s: 심볼 '%s' 을(를) %s 에서 찾지 못함" % (label, c["symbol"], path))
                return None
            a, b = hits[0]["start"], hits[0]["end"]
        else:
            rng = c.get("lines")
            if not (isinstance(rng, list) and len(rng) == 2 and all(isinstance(x, int) for x in rng)):
                errors.append("%s: lines 는 [시작, 끝] 정수 두 개여야 함" % label)
                return None
            a, b = rng
        if not (1 <= a <= b <= len(lines)):
            errors.append("%s: 줄 범위 %s-%s 가 파일 길이(%d줄)를 벗어남" % (label, a, b, len(lines)))
            return None
        n = b - a + 1
        if n > MAX_SNIPPET:
            errors.append("%s: %d줄은 너무 김 (최대 %d줄). 핵심 부분만 고르거나 조각을 나눌 것" % (label, n, MAX_SNIPPET))
            return None
        if n > WARN_SNIPPET:
            warns.append("%s: %d줄 — 더 좁힐 수 있는지 검토" % (label, n))
        if not str(c.get("explain", "")).strip():
            warns.append("%s: explain 이 비어 있음" % label)
        src = textwrap.dedent("\n".join(l.expandtabs(4).rstrip() for l in lines[a - 1:b]))
        points = []
        for p in c.get("points") or []:
            pr = p.get("lines")
            if isinstance(pr, int):
                pr = [pr, pr]
            if not (isinstance(pr, list) and len(pr) == 2) or not str(p.get("text", "")).strip():
                warns.append("%s: points 항목 형식 오류 (무시됨)" % label)
                continue
            pa, pb = max(a, pr[0]), min(b, pr[1])
            if pa > pb:
                warns.append("%s: point %s 가 코드 범위 밖 (무시됨)" % (label, pr))
                continue
            points.append({"a": pa, "b": pb, "text": p["text"]})
        used_files.add(path)
        stats["code"] += 1
        stats["lines"] += n
        ext = os.path.splitext(path)[1].lower()
        return {"title": c.get("title") or os.path.basename(path), "file": path,
                "start": a, "end": b, "lang": CODE_EXT.get(ext, ext.lstrip(".")),
                "source": src, "explain": c.get("explain", ""), "points": points}

    auto = [0]

    def do_node(n, where, depth, inherited_file):
        title = str(n.get("title", "")).strip()
        here = "%s > %s" % (where, title or "?") if where else (title or "?")
        if not title:
            errors.append("%s: title 이 없음" % here)
        nid = n.get("id")
        if not nid:
            auto[0] += 1
            nid = "_n%d" % auto[0]
        if nid in ids:
            errors.append("%s: id '%s' 중복" % (here, nid))
        ids.add(nid)
        stats["nodes"] += 1
        stats["depth"] = max(stats["depth"], depth)
        f = n.get("file") or inherited_file
        out = {"id": nid, "title": title, "summary": n.get("summary", "")}
        if n.get("file"):
            out["file"] = n["file"]
            if file_lines(n["file"]) is None:
                warns.append("%s: file '%s' 을(를) 찾을 수 없음" % (here, n["file"]))
            else:
                used_files.add(n["file"])
        if n.get("flow"):
            out["flow"] = True
        kids = [do_node(c, here, depth + 1, f) for c in n.get("children") or []]
        codes = [c for c in (do_code(c, here, f) for c in n.get("code") or []) if c]
        if kids:
            out["children"] = kids
        if codes:
            out["code"] = codes
        return out

    nodes = [do_node(n, "", 1, None) for n in an.get("nodes") or []]
    if not nodes:
        errors.append("nodes 가 비어 있음 (최상위 흐름 단계가 최소 1개 필요)")
    links = []
    for l in an.get("links") or []:
        if l.get("from") in ids and l.get("to") in ids:
            links.append({"from": l["from"], "to": l["to"], "label": l.get("label", "")})
        else:
            errors.append("links: '%s' → '%s' 중 존재하지 않는 id" % (l.get("from"), l.get("to")))

    if plan and stats["code"] > plan["snippets"]:
        warns.append("코드 조각 %d개 — 이번 분석 예산(%d개)을 넘었다. 덜 중요한 조각을 뺄 것"
                     % (stats["code"], plan["snippets"]))
    for w in warns:
        print("경고  " + w)
    if errors:
        for e in errors:
            print("오류  " + e)
        raise SystemExit("\n오류 %d건 — %s 을(를) 고친 뒤 다시 build 하세요." % (
            len(errors), os.path.basename(analysis_path)))

    t = man["totals"]
    data = {
        "title": an.get("title") or man["name"],
        "summary": an.get("summary", ""),
        "generated": datetime.date.today().isoformat(),
        "ordered": an.get("ordered", True),
        "scope": {
            "analyzed": t["code"], "in_map": len(used_files),
            "dropped_files": t["dropped_files"], "dropped_dirs": t["dropped_dirs"],
            "dropped": [{"reason": d["reason"], "files": d["files"], "dirs": d["dirs"],
                         "examples": d["examples"][:6]} for d in man["dropped"]],
            "groups": [{"pattern": (g["dir"] + "/" if g["dir"] else "") + g["pattern"],
                        "count": g["count"], "collapsed": g["collapsed"],
                        "reps": g["reps"]} for g in man["groups"]],
        },
        "nodes": nodes, "links": links,
    }

    template_path = template_path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "template", "mindmap.html")
    with open(template_path, encoding="utf-8") as fp:
        html = fp.read()
    if "__CODEMAP_DATA__" not in html:
        raise SystemExit("템플릿에 __CODEMAP_DATA__ 자리표시자가 없습니다.")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = html.replace("__CODEMAP_DATA__", payload, 1)
    html = html.replace("<title>코드맵</title>", "<title>%s · 코드맵</title>" % (
        data["title"].replace("&", "&amp;").replace("<", "&lt;")), 1)

    output = output or os.path.join(out_dir, "%s-codemap.html" % man["name"])
    with open(output, "w", encoding="utf-8") as fp:
        fp.write(html)
    return {"output": output, "nodes": stats["nodes"], "code": stats["code"],
            "lines": stats["lines"], "depth": stats["depth"], "warnings": len(warns),
            "kb": round(len(html.encode("utf-8")) / 1024, 1)}
