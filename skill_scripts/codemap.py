#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""코드맵 — 코드베이스를 클릭형 마인드맵 HTML로.

  codemap.py prepare <폴더|zip> [--out DIR]  0+1단계를 한 번에 (뼈대를 바로 출력)
  codemap.py scan <폴더|zip> [--out DIR]     0단계: 이름만 보고 거르기
  codemap.py skeleton <DIR>                  1단계: 뼈대 뽑기 (LLM이 읽을 요약)
  codemap.py read <DIR> 경로:10-40 ...       2단계: 필요한 줄만 꺼내 읽기
  codemap.py build <DIR>                     3단계: analysis.json → HTML

표준 라이브러리만 사용한다 (Python 3.8+).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build as build_mod      # noqa: E402
import scan as scan_mod        # noqa: E402
import skeleton as skel_mod    # noqa: E402


def cmd_scan(a):
    name = os.path.splitext(os.path.basename(os.path.abspath(a.src).rstrip("/")))[0]
    out = a.out or os.path.join(os.getcwd(), "codemap_out", name)
    kw = dict(keep_tests=a.keep_tests, keep_samples=a.keep_samples, collapse=a.collapse,
              reps=a.reps, include=a.include, exclude=a.exclude)
    m = scan_mod.scan(a.src, out, **kw)
    if m["totals"]["code"] == 0 and not (a.keep_tests and a.keep_samples):
        print("[scan] 코드가 하나도 남지 않아 테스트·예제 폴더를 포함해 다시 고릅니다.")
        kw.update(keep_tests=True, keep_samples=True)
        m = scan_mod.scan(a.src, out, **kw)
    print(scan_mod.summary_text(m))
    print("→ %s" % os.path.join(out, "manifest.json"))
    print("다음: codemap.py skeleton %s" % out)


def cmd_skeleton(a):
    r = skel_mod.build_skeleton(a.dir, budget=a.budget, depth=a.depth)
    ratio = (100.0 * r["skeleton_tokens"] / r["raw_tokens"]) if r["raw_tokens"] else 0
    print("[skeleton] 파일 %d개 · 원문 약 %s토큰 → 뼈대 약 %s토큰 (%.0f%%)" % (
        r["files"], format(r["raw_tokens"], ","), format(r["skeleton_tokens"], ","), ratio))
    print("  상세 %d개 · 요약만 %d개 · 이름만 %d개 · 로컬 판정 제외 %d개" % (
        r["full"], r["brief"], r["names"], r["skipped"]))
    ch = r["changes"]
    if ch is not None:
        n = len(ch["changed"]) + len(ch["added"]) + len(ch["removed"])
        print("  지난 분석 대비 달라진 파일: %d개%s" % (n, "" if n else " (analysis.json 재사용 가능)"))
    print("  이번 분석 예산(%s): 코드 조각 %d개 이하 · 읽기 %d줄 이하" % (
        r["plan"]["label"], r["plan"]["snippets"], r["plan"]["read_lines"]))
    print("→ %s  (이 파일만 읽으면 된다)" % r["path"])


INLINE_LIMIT = 24000    # 이보다 긴 뼈대는 화면에 찍지 않고 파일로만 둔다 (도구 출력 한도)


def cmd_prepare(a):
    """scan + skeleton 을 한 번에 하고 뼈대를 바로 출력한다. (도구 호출 3번 → 1번)"""
    name = os.path.splitext(os.path.basename(os.path.abspath(a.src).rstrip("/")))[0]
    out = a.out or os.path.join(os.getcwd(), "codemap_out", name)
    kw = dict(keep_tests=a.keep_tests, keep_samples=a.keep_samples, collapse=a.collapse,
              reps=a.reps, include=a.include, exclude=a.exclude)
    m = scan_mod.scan(a.src, out, **kw)
    if m["totals"]["code"] == 0 and not (a.keep_tests and a.keep_samples):
        kw.update(keep_tests=True, keep_samples=True)
        m = scan_mod.scan(a.src, out, **kw)
    print(scan_mod.summary_text(m))
    r = skel_mod.build_skeleton(out, budget=a.budget, depth=a.depth)
    print("작업 폴더: %s\n" % out)
    with open(r["path"], encoding="utf-8") as fp:
        text = fp.read()
    if len(text) <= INLINE_LIMIT:
        print(text)
    else:
        print("뼈대가 길어 여기 찍지 않았다. 이 파일을 읽을 것 → %s" % r["path"])


def cmd_read(a):
    print(skel_mod.read_ranges(a.dir, a.specs, budget_lines=a.budget_lines))


def cmd_build(a):
    if a.map == "-":            # 표준 입력으로 받은 지도를 map.txt 로 저장하고 바로 빌드 (쓰기 + 빌드를 한 번에)
        text = sys.stdin.read()
        if not text.strip():
            raise SystemExit("표준 입력이 비어 있습니다. `build <DIR> --map - <<'MAP'` 뒤에 지도를 적으세요.")
        with open(os.path.join(a.dir, "map.txt"), "w", encoding="utf-8") as fp:
            fp.write(text if text.endswith("\n") else text + "\n")
    elif a.map:
        a.analysis = a.map
    r = build_mod.build(a.dir, analysis_path=a.analysis, template_path=a.template, output=a.output)
    print("[build] 박스 %d개 · 코드 조각 %d개(%d줄) · 박스 깊이 %d층 · %sKB%s" % (
        r["nodes"], r["code"], r["lines"], r["depth"], r["kb"],
        " · 경고 %d건" % r["warnings"] if r["warnings"] else ""))
    print("→ %s" % r["output"])


def main(argv=None):
    p = argparse.ArgumentParser(prog="codemap", description="코드베이스 → 마인드맵 HTML")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="이름만 보고 분석 대상을 고른다")
    s.add_argument("src", help="프로젝트 폴더 또는 zip 파일")
    s.add_argument("--out", help="작업 폴더 (기본: ./codemap_out/<이름>)")
    s.add_argument("--keep-tests", action="store_true", help="테스트 코드도 포함")
    s.add_argument("--keep-samples", action="store_true", help="examples/demo 폴더도 포함")
    s.add_argument("--collapse", choices=["auto", "always", "never"], default="auto",
                   help="반복 묶음 접기: auto=큰 프로젝트·번호 시리즈만 (기본)")
    s.add_argument("--reps", type=int, default=2, help="반복 묶음에서 남길 대표 파일 수")
    s.add_argument("--include", action="append", help="무조건 포함할 glob (여러 번 가능)")
    s.add_argument("--exclude", action="append", help="무조건 제외할 glob (여러 번 가능)")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("prepare", help="scan + skeleton 을 한 번에 하고 뼈대를 출력한다")
    s.add_argument("src", help="프로젝트 폴더 또는 zip 파일")
    s.add_argument("--out", help="작업 폴더 (기본: ./codemap_out/<이름>)")
    s.add_argument("--depth", choices=["quick", "normal", "deep"], default="normal")
    s.add_argument("--budget", type=int, default=12000)
    s.add_argument("--keep-tests", action="store_true")
    s.add_argument("--keep-samples", action="store_true")
    s.add_argument("--collapse", choices=["auto", "always", "never"], default="auto")
    s.add_argument("--reps", type=int, default=2)
    s.add_argument("--include", action="append")
    s.add_argument("--exclude", action="append")
    s.set_defaults(fn=cmd_prepare)

    s = sub.add_parser("skeleton", help="뼈대(skeleton.md)를 만든다")
    s.add_argument("dir", help="scan 이 만든 작업 폴더")
    s.add_argument("--budget", type=int, default=12000, help="뼈대 토큰 예산 (기본 12000)")
    s.add_argument("--depth", choices=["quick", "normal", "deep"], default="normal",
                   help="분석 깊이: quick=빠르게(절반), normal=보통, deep=자세히(두 배)")
    s.set_defaults(fn=cmd_skeleton)

    s = sub.add_parser("read", help="필요한 줄 범위만 읽는다")
    s.add_argument("dir")
    s.add_argument("specs", nargs="+", help="경로:시작-끝 또는 경로::심볼이름")
    s.add_argument("--budget-lines", type=int, default=None,
                   help="읽기 줄 수 상한 (기본: skeleton 이 정한 이번 분석 예산)")
    s.set_defaults(fn=cmd_read)

    s = sub.add_parser("build", help="map.txt(또는 analysis.json)를 HTML로 만든다")
    s.add_argument("dir")
    s.add_argument("--analysis", help="기본: <dir>/map.txt, 없으면 <dir>/analysis.json")
    s.add_argument("--map", help="지도 파일 경로. `-` 면 표준 입력을 <dir>/map.txt 로 저장한 뒤 빌드")
    s.add_argument("--template", help="기본: ../template/mindmap.html")
    s.add_argument("--output", help="기본: <dir>/<이름>-codemap.html")
    s.set_defaults(fn=cmd_build)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
