#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""코드맵 — 코드베이스를 클릭형 마인드맵 HTML로.

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
    r = skel_mod.build_skeleton(a.dir, budget=a.budget)
    ratio = (100.0 * r["skeleton_tokens"] / r["raw_tokens"]) if r["raw_tokens"] else 0
    print("[skeleton] 파일 %d개 · 원문 약 %s토큰 → 뼈대 약 %s토큰 (%.0f%%)" % (
        r["files"], format(r["raw_tokens"], ","), format(r["skeleton_tokens"], ","), ratio))
    print("  상세 %d개 · 요약만 %d개 · 이름만 %d개 · 로컬 판정 제외 %d개" % (
        r["full"], r["brief"], r["names"], r["skipped"]))
    ch = r["changes"]
    if ch is not None:
        n = len(ch["changed"]) + len(ch["added"]) + len(ch["removed"])
        print("  지난 분석 대비 달라진 파일: %d개%s" % (n, "" if n else " (analysis.json 재사용 가능)"))
    print("→ %s  (이 파일만 읽으면 된다)" % r["path"])


def cmd_read(a):
    print(skel_mod.read_ranges(a.dir, a.specs, budget_lines=a.budget_lines))


def cmd_build(a):
    r = build_mod.build(a.dir, analysis_path=a.analysis, template_path=a.template, output=a.output)
    print("[build] 박스 %d개 · 코드 조각 %d개(%d줄) · 깊이 %d층 · %sKB%s" % (
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

    s = sub.add_parser("skeleton", help="뼈대(skeleton.md)를 만든다")
    s.add_argument("dir", help="scan 이 만든 작업 폴더")
    s.add_argument("--budget", type=int, default=12000, help="뼈대 토큰 예산 (기본 12000)")
    s.set_defaults(fn=cmd_skeleton)

    s = sub.add_parser("read", help="필요한 줄 범위만 읽는다")
    s.add_argument("dir")
    s.add_argument("specs", nargs="+", help="경로:시작-끝 또는 경로::심볼이름")
    s.add_argument("--budget-lines", type=int, default=1500)
    s.set_defaults(fn=cmd_read)

    s = sub.add_parser("build", help="analysis.json 을 HTML로 만든다")
    s.add_argument("dir")
    s.add_argument("--analysis", help="기본: <dir>/analysis.json")
    s.add_argument("--template", help="기본: ../template/mindmap.html")
    s.add_argument("--output", help="기본: <dir>/<이름>-codemap.html")
    s.set_defaults(fn=cmd_build)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
