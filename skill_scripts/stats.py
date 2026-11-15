#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실험용 · 한 번의 분석에서 토큰이 어디에 쓰였는지 단계별로 잰다.

  stats.py <작업폴더>                 한 번의 실행을 측정
  stats.py <기준 폴더> <비교 폴더>     두 실행을 나란히 비교 (증감 %)

LLM이 '읽은 것'(입력)과 '쓴 것'(출력)을 작업 폴더에 남은 파일에서 역산한다.
  입력 = SKILL.md + skeleton.md + read 로 꺼낸 줄
  출력 = map.txt 또는 analysis.json (구조 / 글 로 나눠서)

지침은 처음 잴 때 작업 폴더에 SKILL.snapshot.md 로 복사해 둔다. 나중에 SKILL.md 를
고쳐도 예전 실행의 수치가 바뀌지 않게 하기 위해서다.

토큰 수는 글자 수에서 어림한 값이다 (아래 est_tokens). 절대값은 실제와 다를 수
있지만, 같은 프로젝트로 두 방식을 비교하는 용도로는 충분하다. 실제 값은 분석을
새 세션에서 돌린 뒤 그 세션의 컨텍스트 사용량으로 확인한다.
"""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mapfmt  # noqa: E402

OUT_WEIGHT = 5.0   # 출력 토큰 단가 ÷ 입력 토큰 단가 (대략)
PROSE_KEYS = ("title", "summary", "explain", "text", "label")


def hangul(s):
    return sum(1 for ch in s if "가" <= ch <= "힣")


def est_tokens(chars, n_hangul):
    """어림: 한글 1자 ≈ 1토큰, 그 외(영문·기호·공백) 3.5자 ≈ 1토큰."""
    return int(n_hangul * 1.0 + (chars - n_hangul) / 3.5) + 1


def _read(path):
    try:
        with open(path, encoding="utf-8") as fp:
            return fp.read()
    except OSError:
        return None


def _prose(obj):
    """analysis.json 에서 사람이 읽는 글(제목·요약·설명)만 모은다."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in PROSE_KEYS and isinstance(v, str):
                out.append(v)
            else:
                out.extend(_prose(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_prose(v))
    return out


def _count(nodes):
    boxes = codes = points = 0
    for n in nodes or []:
        boxes += 1
        for c in n.get("code") or []:
            codes += 1
            points += len(c.get("points") or [])
        b, c2, p = _count(n.get("children"))
        boxes, codes, points = boxes + b, codes + c2, points + p
    return boxes, codes, points


def coverage(out_dir, ref_dir=None):
    """지도가 코드의 얼마를 다뤘는지: 조각이 걸친 파일·함수의 수. (함수 목록은 ref_dir 의 뼈대 기준)"""
    import glob
    import re
    htmls = glob.glob(os.path.join(out_dir, "*-codemap.html"))
    sk = json.loads(_read(os.path.join(ref_dir or out_dir, "skeleton.json")) or "{}").get("files")
    if not htmls or not sk:
        return None
    m = re.search(r'<script id="codemap-data" type="application/json">(.*?)</script>', _read(htmls[0]), re.S)
    if not m:
        return None
    spans = {}

    def walk(n):
        for c in n.get("code") or []:
            spans.setdefault(c["file"], []).append((c["start"], c["end"]))
        for ch in n.get("children") or []:
            walk(ch)
    for n in json.loads(m.group(1))["nodes"]:
        walk(n)
    funcs = hit = 0
    for path, info in sk.items():
        for sy in info["syms"]:
            if sy["kind"] in ("func", "method") and sy["end"] - sy["start"] >= 3:
                funcs += 1
                if any(a <= sy["end"] and b >= sy["start"] for a, b in spans.get(path, [])):
                    hit += 1
    return {"files": len([p for p in sk if p in spans]), "files_total": len(sk),
            "funcs": hit, "funcs_total": funcs,
            "lines": sum(b - a + 1 for v in spans.values() for a, b in v)}


def collect(out_dir, skill_md=None, ref_dir=None):
    man = json.loads(_read(os.path.join(out_dir, "manifest.json")) or "{}")
    snap = os.path.join(out_dir, "SKILL.snapshot.md")
    if not os.path.exists(snap):
        shutil.copyfile(skill_md or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "SKILL.md"), snap)
    skill_md = snap
    rows = {}

    def part(name, text):
        if text is None:
            rows[name] = None
            return
        rows[name] = {"chars": len(text), "tokens": est_tokens(len(text), hangul(text))}

    part("지침(SKILL.md)", _read(skill_md))
    part("뼈대(skeleton.md)", _read(os.path.join(out_dir, "skeleton.md")))
    log = json.loads(_read(os.path.join(out_dir, "read_log.json")) or "{}")
    if "chars" in log:
        rows["읽은 코드(read)"] = {"chars": log["chars"],
                                 "tokens": est_tokens(log["chars"], log.get("hangul", 0)),
                                 "lines": log.get("lines", 0), "calls": log.get("calls", 0)}
    else:
        rows["읽은 코드(read)"] = None

    fmt = "map.txt"
    raw = _read(os.path.join(out_dir, "map.txt"))
    boxes = codes = points = 0
    if raw is not None:
        an = mapfmt.parse(raw)[0]
    else:
        fmt = "analysis.json"
        raw = _read(os.path.join(out_dir, "analysis.json"))
        try:
            an = json.loads(raw) if raw is not None else {}
        except ValueError:
            an = {}
    if raw is not None:
        prose = "".join(_prose(an))
        struct_chars = len(raw) - len(prose)
        struct_hangul = hangul(raw) - hangul(prose)
        rows["분석 결과 · 글"] = {"chars": len(prose), "tokens": est_tokens(len(prose), hangul(prose))}
        rows["분석 결과 · 구조"] = {"chars": struct_chars, "tokens": est_tokens(struct_chars, struct_hangul)}
        boxes, codes, points = _count(an.get("nodes"))
    else:
        rows["분석 결과 · 글"] = rows["분석 결과 · 구조"] = None

    def tok(name):
        return rows[name]["tokens"] if rows.get(name) else 0

    t_in = tok("지침(SKILL.md)") + tok("뼈대(skeleton.md)") + tok("읽은 코드(read)")
    t_out = tok("분석 결과 · 글") + tok("분석 결과 · 구조")
    return {
        "dir": out_dir, "name": man.get("name", os.path.basename(out_dir.rstrip("/"))),
        "raw_tokens": (man.get("totals") or {}).get("est_tokens_raw", 0),
        "rows": rows, "in": t_in, "out": t_out, "cost": int(t_in + OUT_WEIGHT * t_out),
        "boxes": boxes, "codes": codes, "points": points, "format": fmt if raw is not None else None,
        "struct_per_item": round(tok("분석 결과 · 구조") / float(max(boxes + codes + points, 1)), 1),
        "plan": (json.loads(_read(os.path.join(out_dir, "skeleton.json")) or "{}")).get("plan"),
        "coverage": coverage(out_dir, ref_dir),
        "missing": [k for k, v in rows.items() if v is None],
    }


ORDER = ["지침(SKILL.md)", "뼈대(skeleton.md)", "읽은 코드(read)", "분석 결과 · 글", "분석 결과 · 구조"]


def _fmt(n):
    return format(int(n), ",")


def show(s):
    print("[%s] %s · 원문 약 %s토큰 · 박스 %d · 코드 조각 %d · 줄 설명 %d" % (
        s["dir"], s["format"] or "분석 결과 없음", _fmt(s["raw_tokens"]), s["boxes"], s["codes"], s["points"]))
    print("  %-22s %9s %9s" % ("항목", "글자", "토큰(어림)"))
    for k in ORDER:
        r = s["rows"].get(k)
        tag = "입력" if ORDER.index(k) < 3 else "출력"
        if r is None:
            print("  %-22s %9s %9s" % ("%s %s" % (tag, k), "-", "(기록 없음)"))
        else:
            extra = "  (%d줄, %d회 호출)" % (r["lines"], r["calls"]) if "lines" in r else ""
            print("  %-22s %9s %9s%s" % ("%s %s" % (tag, k), _fmt(r["chars"]), _fmt(r["tokens"]), extra))
    print("  입력 합계 %s · 출력 합계 %s · 비용 지수 %s  (= 입력 + %g × 출력) · 항목당 구조 %.1f토큰" % (
        _fmt(s["in"]), _fmt(s["out"]), _fmt(s["cost"]), OUT_WEIGHT, s["struct_per_item"]))


def show_plan(s):
    p = s.get("plan")
    if not p:
        print("  예산: 없음 (상한 없이 실행)")
        return
    r = s["rows"].get("읽은 코드(read)") or {}
    print("  예산(%s): 코드 조각 %d/%d개 · 읽기 %s/%d줄" % (
        p["label"], s["codes"], p["snippets"], r.get("lines", "-"), p["read_lines"]))


def show_cov(s):
    c = s.get("coverage")
    if c:
        r = s["rows"].get("읽은 코드(read)") or {}
        used = " · 읽은 줄 중 실린 비율 %d%%" % (100 * c["lines"] / r["lines"]) if r.get("lines") else ""
        print("  다룬 범위: 파일 %d/%d · 함수 %d/%d (%d%%) · 실린 코드 %d줄%s" % (
            c["files"], c["files_total"], c["funcs"], c["funcs_total"],
            100 * c["funcs"] / max(c["funcs_total"], 1), c["lines"], used))


def compare(a, b):
    def pct(x, y):
        return "%+.0f%%" % (100.0 * (y - x) / x) if x else "-"
    print("\n[비교] %s → %s" % (a["dir"], b["dir"]))
    print("  %-22s %9s %9s %7s" % ("항목(토큰 어림)", "기준", "비교", "증감"))
    for k in ORDER:
        x = a["rows"][k]["tokens"] if a["rows"].get(k) else 0
        y = b["rows"][k]["tokens"] if b["rows"].get(k) else 0
        print("  %-22s %9s %9s %7s" % (k, _fmt(x), _fmt(y), pct(x, y)))
    for label, key in (("입력 합계", "in"), ("출력 합계", "out"), ("비용 지수", "cost")):
        print("  %-22s %9s %9s %7s" % (label, _fmt(a[key]), _fmt(b[key]), pct(a[key], b[key])))
    print("  %-22s %9s %9s %7s" % ("항목당 구조 토큰", a["struct_per_item"], b["struct_per_item"],
                                  pct(a["struct_per_item"], b["struct_per_item"])))
    print("  %-22s %9s %9s" % ("박스 / 코드 조각", "%d / %d" % (a["boxes"], a["codes"]),
                              "%d / %d" % (b["boxes"], b["codes"])))
    if (a["boxes"], a["codes"]) != (b["boxes"], b["codes"]):
        print("  ※ 지도 크기가 다르다. 토큰이 줄었어도 내용이 빠진 것일 수 있으니 결과 HTML을 직접 비교할 것.")


def main(argv):
    ref = None
    if "--ref" in argv:                     # 다룬 범위를 셀 때 기준으로 삼을 뼈대가 있는 폴더
        i = argv.index("--ref")
        ref = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if not argv or len(argv) > 2:
        raise SystemExit(__doc__)
    stats = [collect(d, ref_dir=ref) for d in argv]
    for s in stats:
        show(s)
        show_plan(s)
        show_cov(s)
        with open(os.path.join(s["dir"], "stats.json"), "w", encoding="utf-8") as fp:
            json.dump(s, fp, ensure_ascii=False, indent=1)
    if len(stats) == 2:
        compare(stats[0], stats[1])


if __name__ == "__main__":
    main(sys.argv[1:])
