# 코드분석 — 코드 뼈대
코드 5개 · 원문 약 29,929토큰 → 이 뼈대 약 1,356토큰. 표기: `시작-끝줄 시그니처 » 내부 호출  — 설명`, ←n = 이 파일을 import하는 파일 수.

# 지난 분석 이후 달라진 파일 (이것만 다시 보고 analysis.json 의 해당 부분만 고친다)
- 수정: template/mindmap.html

# 진입점 후보
- skill_scripts/skeleton.py
- skill_scripts/codemap.py

# 프로젝트 명세
### README.md (앞부분)
# 코드맵 (codemap)
코드 폴더나 zip을 넣으면 전체 흐름을 **클릭형 마인드맵 HTML 한 장**으로 만든다.
- 박스 클릭 → 하위 기능과 핵심 코드
- 코드 클릭 → 설명 (다시 누르면 닫힘)
- 층수는 코드 깊이에 따라 달라진다
## 구성
```
SKILL.md                  Claude 가 따르는 작업 지침 (스킬로 설치해서 사용)
skill_scripts/
  codemap.py              실행 진입점 (scan / skeleton / read / build)
  scan.py                 0단계: 이름·크기만 보고 거르기
  skeleton.py             1단계: 뼈대 뽑기 + 2단계: 필요한 줄만 읽기
  build.py                3단계: analysis.json → HTML
template/mindmap.html     마인드맵 템플릿 (단독으로 열면 예시 데이터가 보인다)
codemap_out/self/         이 도구 자신을 분석한 예시 결과
```
## 쓰는 법
Claude 에게 폴더나 zip 을 주고 "코드맵 만들어줘"라고 하면 SKILL.md 의 절차대로 진행한다.
직접 돌려 볼 수도 있다 (Python 3.8+, 설치할 것 없음).
```bash
python3 skill_scripts/codemap.py scan ~/my-project --out codemap_out/my-project
python3 skill_scripts/codemap.py skeleton codemap_out/my-project
# → skeleton.md 를 읽고 analysis.json 을 작성 (Claude 가 하는 부분)
python3 skill_scripts/codemap.py build…

# 파일 (중요도 순)
## skill_scripts/skeleton.py · 766줄 · ←2 · ENTRY
  ext: __future__, ast, hashlib, json, os, re
  122-135 def read_text(path, max_bytes=1500000)
  138-140 def _short(s, n)
  143-144 def _indent(line)
  148-205 def py_symbols(text) » _short
  208-210 def _strip_noise(line)
  213-229 def brace_end(lines, i, max_look=4000) » _strip_noise
  232-242 def indent_end(lines, i) » _indent
  245-266 def _doc_above(lines, i) » _short
  269-328 def generic_symbols(lines, fam) » brace_end, indent_end, _short, _doc_above
  332-341 def find_imports(text, fam)
  344-389 class Resolver
    345-354 def __init__(self, paths)
    356-389 def resolve(self, imp, from_path)
  393-422 def analyze_file(root, f) » read_text, py_symbols, generic_symbols, find_imports
  425-437 def head_of(root, path, max_chars) » read_text, _short
  441-706 def build_skeleton(out_dir, budget=12000) » analyze_file, Resolver, resolve, _short, head_of
  710-765 def read_ranges(out_dir, specs, budget_lines=1500, max_range=150) » read_text  — `경로:시작-끝` 또는 `경로::심볼이름` 을 받아 줄 번호와 함께 출력한다.
## skill_scripts/codemap.py · 105줄 · ENTRY
  imports: build, scan, skeleton | ext: __future__, argparse, os, sys
  25-37 def cmd_scan(a) » scan, summary_text
  40-51 def cmd_skeleton(a) » build_skeleton
  54-55 def cmd_read(a) » read_ranges
  58-63 def cmd_build(a)
  66-101 def main(argv=None)
## skill_scripts/scan.py · 462줄 · ←2
  ext: __future__, fnmatch, json, os, re, zipfile
  127-129 def est_tokens(nbytes: int)  — 바이트 수로 토큰 수를 어림한다 (코드 기준 약 3.6바이트 = 1토큰).
  132-133 def _match_any(name: str, patterns)
  136-148 def dir_drop_reason(dirname: str, keep_tests: bool, keep_samples: bool)
  151-189 def classify_file(rel: str, size: int, keep_tests: bool) » _match_any  — (판정, 값) 을 돌려준다. 판정이 'keep' 이면 값은 (lang, role), 'drop' 이면 사유.
  193-207 class Dropped
    194-195 def __init__(self)
    197-202 def add(self, reason, example, size=0, is_dir=False)
    204-207 def to_list(self)
  210-215 def _user_rule(rel, include, exclude)
  218-243 def walk_dir(root, opts, dropped) » dir_drop_reason, _user_rule  — 폴더를 훑는다. 버릴 폴더는 아예 내려가지 않는다.
  246-273 def walk_zip(zf, opts, dropped) » dir_drop_reason, _user_rule  — zip 안의 이름 목록만 본다. 버릴 폴더 안의 파일은 사유만 기록한다.
  277-279 def split_tokens(stem: str)
  282-327 def find_groups(files, min_group=MIN_GROUP) » split_tokens
  330-340 def pick_reps(members, n)
  344-441 def scan(src, out_dir, keep_tests=False, keep_samples=False, collaps…) » Dropped, walk_zip, walk_dir, _user_rule, classify_file, est_tokens
  444-462 def summary_text(m)  — LLM 문맥에 들어가는 출력이므로 짧게: 파일 이름을 전부 나열하지 않는다.
## skill_scripts/build.py · 199줄 · ←1
  imports: scan, skeleton | ext: __future__, datetime, json, os, textwrap
  23-25 def _load(path)
  28-199 def build(out_dir, analysis_path=None, template_path=None, output=None) » _load, read_text
## template/mindmap.html · 682줄
