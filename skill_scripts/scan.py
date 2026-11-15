#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""0단계 · 이름만 보고 걸러내기.

파일의 '경로와 크기'만 보고 분석 대상을 고른다. 이 단계에서는 어떤 파일도
열지 않는다. (zip 입력이면 걸러진 파일은 압축 해제조차 하지 않는다.)

결과는 manifest.json 한 개:
  files   : 분석 대상 (내용을 볼 파일)
  groups  : 반복 묶음 (대표 몇 개만 보고 나머지는 이름만 남김)
  dropped : 제외한 것들 (사유별 개수와 예시)
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import zipfile
from collections import Counter, defaultdict

# ── 폴더 이름만으로 통째로 버리는 것들 ────────────────────────────────
DIR_RULES = {
    "의존성·외부 라이브러리 폴더": {
        "node_modules", "bower_components", "vendor", "Pods", "Carthage",
        "site-packages", ".venv", "venv", "virtualenv", "__pypackages__",
        "third_party", "third-party", "thirdparty", "external", ".bundle",
    },
    "빌드 산출물·캐시 폴더": {
        "dist", "build", "out", "target", "obj", ".next", ".nuxt", ".output",
        ".svelte-kit", ".vercel", ".angular", "DerivedData", ".dart_tool",
        ".turbo", ".parcel-cache", "coverage", "htmlcov", ".nyc_output",
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
        ".cache", ".eggs", "storybook-static", ".gradle", ".terraform",
        "tmp", "temp", "logs", ".ipynb_checkpoints", "codemap_out",
    },
    "버전관리·IDE·CI 폴더": {
        ".git", ".svn", ".hg", ".idea", ".vscode", ".vs", ".fleet",
        ".github", ".gitlab", ".circleci", ".husky", ".devcontainer",
    },
    "자동 생성·마이그레이션 폴더 (반복)": {
        "migrations", "generated", "__generated__", "autogen", "gen",
        "stubs", "typings", "@types", "seeds", "seeders",
    },
    "문서 폴더": {"docs", "doc", "documentation", "wiki"},
}
TEST_DIRS = {
    "test", "tests", "__tests__", "spec", "specs", "e2e", "cypress",
    "playwright", "fixtures", "__fixtures__", "mocks", "__mocks__",
    "__snapshots__", "testdata", "test-data", "stories",
}
SAMPLE_DIRS = {"examples", "example", "samples", "sample", "demo", "demos",
               "benchmarks", "bench"}

# ── 확장자 ─────────────────────────────────────────────────────────────
CODE_EXT = {
    ".py": "python", ".js": "js", ".jsx": "jsx", ".mjs": "js", ".cjs": "js",
    ".ts": "ts", ".tsx": "tsx", ".vue": "vue", ".svelte": "svelte",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".scala": "scala",
    ".swift": "swift", ".m": "objc", ".mm": "objc", ".go": "go",
    ".rs": "rust", ".rb": "ruby", ".php": "php", ".cs": "cs",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".dart": "dart", ".lua": "lua", ".r": "r", ".sh": "sh", ".bash": "sh",
    ".zsh": "sh", ".sql": "sql", ".html": "html", ".htm": "html",
}
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
    ".psd", ".ai", ".sketch", ".fig", ".heic", ".avif",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".mov", ".avi", ".wav", ".ogg", ".webm", ".flac", ".m4a",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".7z", ".rar", ".jar", ".war",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".hwp",
    ".exe", ".dll", ".so", ".dylib", ".a", ".o", ".class", ".pyc", ".pyo",
    ".wasm", ".bin", ".dat", ".db", ".sqlite", ".sqlite3", ".parquet",
    ".pkl", ".pickle", ".npy", ".npz", ".h5", ".onnx", ".pt", ".pth",
    ".ckpt", ".safetensors", ".apk", ".ipa", ".dmg", ".iso", ".keystore",
}
DOC_EXT = {".md", ".mdx", ".rst", ".txt", ".adoc", ".tex"}
STYLE_EXT = {".css", ".scss", ".sass", ".less", ".styl"}
DATA_EXT = {
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".csv", ".tsv", ".env", ".properties", ".plist", ".lock",
    ".log", ".map", ".snap", ".ipynb", ".geojson", ".po", ".pot", ".arb",
    ".xcconfig", ".pbxproj", ".storyboard", ".xib", ".gradle", ".iml",
}
LOCK_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "poetry.lock", "pipfile.lock", "cargo.lock", "gemfile.lock",
    "composer.lock", "go.sum", "pubspec.lock", "podfile.lock", "uv.lock",
    "flake.lock", "packages.lock.json",
}
# 내용을 앞부분만 살짝 읽을 가치가 있는 '프로젝트 명세' 파일
MANIFEST_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "setup.cfg",
    "cargo.toml", "go.mod", "pubspec.yaml", "pom.xml", "build.gradle",
    "build.gradle.kts", "gemfile", "composer.json", "dockerfile",
    "docker-compose.yml", "docker-compose.yaml", "makefile", "procfile",
}

GENERATED_PATTERNS = [
    "*.g.dart", "*.freezed.dart", "*.gr.dart", "*.mocks.dart",
    "*_pb2.py", "*_pb2_grpc.py", "*.pb.go", "*.pb.cc", "*.pb.h",
    "*.generated.*", "*.gen.*", "*_generated.*", "*_gen.go",
    "*.designer.cs", "*.g.cs", "*.d.ts", "*.d.mts", "r.java",
    "buildconfig.java", "*.min.js", "*.min.css", "*.bundle.js",
    "*.chunk.js", "*.js.map", "*.css.map", "*-min.js",
]
TEST_PATTERNS = [
    "test_*.py", "*_test.py", "conftest.py", "*_test.go", "*.test.*",
    "*.spec.*", "*_spec.rb", "*test.java", "*tests.java", "*test.kt",
    "*tests.cs", "*tests.swift", "*_test.dart", "*.stories.*", "*.story.*",
]
TOOLING_PATTERNS = [
    "*.config.js", "*.config.ts", "*.config.mjs", "*.config.cjs",
    "gulpfile.*", "gruntfile.*", "webpack.*.js", "rollup.*.js",
    "setup.py", "babel.config.*", "jest.setup.*",
    "vite-env.d.ts", "next-env.d.ts", "reportwebvitals.*", "setuptests.*",
]

MAX_CODE_BYTES = 1_000_000      # 이보다 큰 '코드' 파일은 생성물로 보고 제외
MAX_SQL_BYTES = 150_000
BIG_PROJECT_TOKENS = 120_000    # 이 이상이면 '큰 프로젝트' → 반복 묶음을 접는다
BIG_PROJECT_FILES = 120
MIN_GROUP = 5                   # 같은 패턴이 이만큼 모이면 반복 묶음


def est_tokens(nbytes: int) -> int:
    """바이트 수로 토큰 수를 어림한다 (코드 기준 약 3.6바이트 = 1토큰)."""
    return int(nbytes / 3.6) + 1


def _match_any(name: str, patterns) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def dir_drop_reason(dirname: str, keep_tests: bool, keep_samples: bool):
    low = dirname.lower()
    for reason, names in DIR_RULES.items():
        if dirname in names or low in names:
            return reason
    if dirname.endswith(".egg-info") or dirname.endswith(".xcassets") \
            or dirname.endswith(".xcodeproj") or dirname.endswith(".xcworkspace"):
        return "빌드 산출물·캐시 폴더"
    if not keep_tests and low in TEST_DIRS:
        return "테스트 코드"
    if not keep_samples and low in SAMPLE_DIRS:
        return "예제·샘플 폴더"
    return None


def classify_file(rel: str, size: int, keep_tests: bool):
    """(판정, 값) 을 돌려준다. 판정이 'keep' 이면 값은 (lang, role), 'drop' 이면 사유."""
    name = os.path.basename(rel)
    low = name.lower()
    ext = os.path.splitext(low)[1]
    depth = rel.count("/")

    if low in LOCK_NAMES:
        return "drop", "잠금 파일·소스맵·압축본"
    if low in MANIFEST_NAMES and depth <= 2:
        return "keep", ("manifest", "manifest")
    if low.startswith("readme") and depth == 0:
        return "keep", ("readme", "readme")
    if name.startswith("."):
        return "drop", "숨김 설정 파일"
    if ext in BINARY_EXT:
        return "drop", "이미지·폰트·미디어·바이너리"
    if _match_any(low, GENERATED_PATTERNS):
        if ".min." in low or low.endswith(".map") or "bundle" in low or "chunk" in low:
            return "drop", "잠금 파일·소스맵·압축본"
        return "drop", "자동 생성 코드"
    if not keep_tests and _match_any(low, TEST_PATTERNS):
        return "drop", "테스트 코드"
    if _match_any(low, TOOLING_PATTERNS):
        return "drop", "빌드·도구 설정"
    if ext in CODE_EXT:
        if size == 0:
            return "drop", "빈 파일"
        if size > MAX_CODE_BYTES or (ext == ".sql" and size > MAX_SQL_BYTES):
            return "drop", "너무 큰 단일 파일 (생성물·데이터로 추정)"
        return "keep", (CODE_EXT[ext], "code")
    if ext in DOC_EXT or low in ("license", "licence", "changelog", "authors",
                                 "contributing", "notice", "copying"):
        return "drop", "문서"
    if ext in STYLE_EXT:
        return "drop", "스타일시트"
    if ext in DATA_EXT:
        return "drop", "데이터·설정 파일"
    return "drop", "기타 (코드 아님)"


# ── 파일 목록 얻기 ─────────────────────────────────────────────────────
class Dropped:
    def __init__(self):
        self.by = defaultdict(lambda: {"files": 0, "dirs": 0, "bytes": 0, "examples": []})

    def add(self, reason, example, size=0, is_dir=False):
        d = self.by[reason]
        d["dirs" if is_dir else "files"] += 1
        d["bytes"] += size
        if len(d["examples"]) < 8 and example not in d["examples"]:
            d["examples"].append(example)

    def to_list(self):
        out = [dict(reason=k, **v) for k, v in self.by.items()]
        out.sort(key=lambda r: -(r["files"] + r["dirs"]))
        return out


def _user_rule(rel, include, exclude):
    if include and any(fnmatch.fnmatch(rel, g) for g in include):
        return "keep"
    if exclude and any(fnmatch.fnmatch(rel, g) for g in exclude):
        return "drop"
    return None


def walk_dir(root, opts, dropped):
    """폴더를 훑는다. 버릴 폴더는 아예 내려가지 않는다."""
    seen = 0
    for cur, dirs, files in os.walk(root, topdown=True, followlinks=False):
        relcur = os.path.relpath(cur, root).replace(os.sep, "/")
        relcur = "" if relcur == "." else relcur + "/"
        keep_dirs = []
        for d in sorted(dirs):
            reason = dir_drop_reason(d, opts["keep_tests"], opts["keep_samples"])
            if reason is None and os.path.exists(os.path.join(cur, d, "pyvenv.cfg")):
                reason = "의존성·외부 라이브러리 폴더"
            if reason and _user_rule(relcur + d + "/", opts["include"], None) != "keep":
                dropped.add(reason, relcur + d + "/", is_dir=True)
            else:
                keep_dirs.append(d)
        dirs[:] = keep_dirs
        for f in sorted(files):
            full = os.path.join(cur, f)
            if os.path.islink(full):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            seen += 1
            yield relcur + f, size


def walk_zip(zf, opts, dropped):
    """zip 안의 이름 목록만 본다. 버릴 폴더 안의 파일은 사유만 기록한다."""
    infos = [i for i in zf.infolist() if not i.is_dir()]
    names = [i.filename for i in infos]
    venv_dirs = {n[: -len("pyvenv.cfg")] for n in names if n.endswith("/pyvenv.cfg")}
    # 최상위 폴더 하나로 감싸져 있으면 벗겨낸다
    tops = {n.split("/", 1)[0] for n in names if "/" in n}
    strip = ""
    if len(tops) == 1 and all("/" in n for n in names):
        strip = next(iter(tops)) + "/"
    for info in infos:
        raw = info.filename
        if raw.startswith("/") or ".." in raw.split("/") or raw.startswith("__MACOSX/"):
            continue
        rel = raw[len(strip):] if strip and raw.startswith(strip) else raw
        parts = rel.split("/")
        reason, upto = None, ""
        for i, part in enumerate(parts[:-1]):
            upto = "/".join(parts[: i + 1]) + "/"
            reason = dir_drop_reason(part, opts["keep_tests"], opts["keep_samples"])
            if reason is None and (strip + upto) in venv_dirs:
                reason = "의존성·외부 라이브러리 폴더"
            if reason:
                break
        if reason and _user_rule(rel, opts["include"], None) != "keep":
            dropped.add(reason, upto, info.file_size)
            continue
        yield rel, info.file_size, info


# ── 반복 묶음 찾기 (이름만 사용) ───────────────────────────────────────
def split_tokens(stem: str):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", stem)
    return [t.lower() for t in re.split(r"[\s_\-.]+", s) if t]


def find_groups(files, min_group=MIN_GROUP):
    by_dir = defaultdict(list)
    for f in files:
        if f["role"] != "code":
            continue
        d, name = os.path.split(f["path"])
        by_dir[(d, os.path.splitext(name)[1].lower())].append(f)

    groups = []
    for (d, ext), fs in sorted(by_dir.items()):
        if len(fs) < 4:
            continue
        remaining = list(fs)

        def stem(f):
            return os.path.splitext(os.path.basename(f["path"]))[0]

        numbered = [f for f in remaining
                    if re.match(r"^[vV]?\d+([_\-.]|$)", stem(f)) or re.search(r"\d{2,}$", stem(f))]
        if len(numbered) >= 4:
            groups.append({"dir": d, "pattern": "번호 시리즈 *%s" % ext,
                           "members": numbered, "always": True})
            remaining = [f for f in remaining if f not in numbered]

        for which in ("suffix", "prefix"):
            if len(remaining) < min_group:
                break
            cnt = Counter()
            for f in remaining:
                toks = split_tokens(stem(f))
                if len(toks) >= 2:
                    cnt[toks[-1] if which == "suffix" else toks[0]] += 1
            for tok, c in cnt.most_common():
                if c < min_group:
                    break
                members = []
                for f in remaining:
                    toks = split_tokens(stem(f))
                    if len(toks) >= 2 and (toks[-1] if which == "suffix" else toks[0]) == tok:
                        members.append(f)
                if len(members) < min_group:
                    continue
                pat = ("*%s%s" % (tok, ext)) if which == "suffix" else ("%s*%s" % (tok, ext))
                groups.append({"dir": d, "pattern": pat, "members": members, "always": False})
                remaining = [f for f in remaining if f not in members]
    return groups


def pick_reps(members, n):
    by_size = sorted(members, key=lambda f: -f["size"])
    picks = [by_size[0]]
    if n >= 2 and len(by_size) > 2:
        picks.append(by_size[len(by_size) // 2])
    for f in by_size[1:]:
        if len(picks) >= n:
            break
        if f not in picks:
            picks.append(f)
    return picks[:n]


# ── 본체 ───────────────────────────────────────────────────────────────
def scan(src, out_dir, keep_tests=False, keep_samples=False, collapse="auto",
         reps=2, include=None, exclude=None):
    src = os.path.abspath(os.path.expanduser(src))
    opts = {"keep_tests": keep_tests, "keep_samples": keep_samples,
            "include": include or [], "exclude": exclude or []}
    dropped = Dropped()
    files, zinfos = [], {}
    is_zip = os.path.isfile(src) and zipfile.is_zipfile(src)
    if not is_zip and not os.path.isdir(src):
        raise SystemExit("입력은 폴더이거나 zip 파일이어야 합니다: %s" % src)
    name = os.path.splitext(os.path.basename(src.rstrip("/")))[0] or "project"

    zf = zipfile.ZipFile(src) if is_zip else None
    entries = walk_zip(zf, opts, dropped) if is_zip else walk_dir(src, opts, dropped)
    seen = 0
    for entry in entries:
        rel, size = entry[0], entry[1]
        seen += 1
        rule = _user_rule(rel, opts["include"], opts["exclude"])
        if rule == "drop":
            dropped.add("사용자 지정 제외", rel, size)
            continue
        verdict, val = classify_file(rel, size, keep_tests)
        if verdict == "drop" and rule == "keep":
            ext = os.path.splitext(rel)[1].lower()
            verdict, val = "keep", (CODE_EXT.get(ext, "text"), "code")
        if verdict == "drop":
            dropped.add(val, rel, size)
            continue
        files.append({"path": rel, "size": size, "lang": val[0], "role": val[1]})
        if is_zip:
            zinfos[rel] = entry[2]

    code = [f for f in files if f["role"] == "code"]
    raw_tokens = sum(est_tokens(f["size"]) for f in code)
    big = raw_tokens > BIG_PROJECT_TOKENS or len(code) > BIG_PROJECT_FILES

    # 반복 묶음: 번호 시리즈는 항상, 그 외는 큰 프로젝트일 때만 접는다
    groups_out = []
    for i, g in enumerate(find_groups(files)):
        do_collapse = collapse == "always" or (collapse == "auto" and (g["always"] or big))
        rep_files = pick_reps(g["members"], reps)
        rep_paths = [f["path"] for f in rep_files]
        others = [f for f in g["members"] if f["path"] not in rep_paths]
        gid = "g%d" % (i + 1)
        if do_collapse:
            for f in others:
                files.remove(f)
                dropped.add("반복 패턴 (대표만 분석)", f["path"], f["size"])
            for f in rep_files:
                f["group"] = gid
        groups_out.append({
            "id": gid, "dir": g["dir"], "pattern": g["pattern"],
            "count": len(g["members"]), "collapsed": do_collapse,
            "reps": rep_paths,
            "others": [os.path.basename(f["path"]) for f in others],
        })

    # zip 이면 살아남은 파일만 푼다
    os.makedirs(out_dir, exist_ok=True)
    root = src
    if is_zip:
        root = os.path.join(out_dir, "src")
        total = 0
        for f in files:
            info = zinfos[f["path"]]
            total += info.file_size
            if total > 300_000_000:
                raise SystemExit("압축 해제 용량이 300MB를 넘어 중단합니다.")
            dest = os.path.join(root, f["path"])
            if not os.path.abspath(dest).startswith(os.path.abspath(root) + os.sep):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(info) as fi, open(dest, "wb") as fo:
                fo.write(fi.read())
        zf.close()

    code = [f for f in files if f["role"] == "code"]
    drop_list = dropped.to_list()
    n_dropped = sum(d["files"] for d in drop_list)
    manifest = {
        "name": name, "root": root, "source": "zip" if is_zip else "dir",
        "big": big,
        "totals": {
            "seen": seen,
            "kept": len(files), "code": len(code),
            "dropped_files": n_dropped,
            "dropped_dirs": sum(d["dirs"] for d in drop_list),
            "est_tokens_before_collapse": raw_tokens,
            "est_tokens_raw": sum(est_tokens(f["size"]) for f in code),
        },
        "files": sorted(files, key=lambda f: f["path"]),
        "groups": groups_out,
        "dropped": drop_list,
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=1)
    return manifest


def summary_text(m) -> str:
    """LLM 문맥에 들어가는 출력이므로 짧게: 파일 이름을 전부 나열하지 않는다."""
    t = m["totals"]
    lines = [
        "[scan] %s — 분석 대상 %d개 (코드 %d개, 원문 약 %s토큰)%s" % (
            m["name"], t["kept"], t["code"], format(t["est_tokens_raw"], ","),
            " · 큰 프로젝트로 판단" if m["big"] else ""),
        "제외: 파일 %d개 + 폴더 %d개 (내용을 열지 않음)" % (t["dropped_files"], t["dropped_dirs"]),
    ]
    for d in m["dropped"]:
        n = ("파일 %d" % d["files"] if d["files"] else "") + \
            (" 폴더 %d" % d["dirs"] if d["dirs"] else "")
        lines.append("  - %s: %s  예) %s" % (d["reason"], n.strip(), ", ".join(d["examples"][:3])))
    for g in m["groups"]:
        state = "대표 %d개만 분석" % len(g["reps"]) if g["collapsed"] else "전부 분석 (묶음 표시만)"
        lines.append("  * 반복 묶음 %s/%s ×%d → %s" % (g["dir"] or ".", g["pattern"], g["count"], state))
    if t["code"] == 0:
        lines.append("!! 코드 파일이 하나도 남지 않았습니다. --keep-tests / --keep-samples / --include 를 검토하세요.")
    return "\n".join(lines)
