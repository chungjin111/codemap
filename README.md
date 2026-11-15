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
examples/                 이 도구 자신을 분석한 예시 (codemap-self.html 을 열어 보면 된다)
```

## 설치

Claude 스킬 폴더에 통째로 넣는다.

```bash
git clone https://github.com/chungjin111/codemap.git ~/.claude/skills/codemap
```

## 쓰는 법

Claude 에게 폴더나 zip 을 주고 "코드맵 만들어줘"라고 하면 SKILL.md 의 절차대로 진행한다.
직접 돌려 볼 수도 있다 (Python 3.8+, 설치할 것 없음).

```bash
python3 skill_scripts/codemap.py scan ~/my-project --out codemap_out/my-project
python3 skill_scripts/codemap.py skeleton codemap_out/my-project
# → skeleton.md 를 읽고 analysis.json 을 작성 (Claude 가 하는 부분)
python3 skill_scripts/codemap.py build codemap_out/my-project
```

## scan 옵션

| 옵션 | 뜻 |
|---|---|
| `--keep-tests` | 테스트 코드도 분석 |
| `--keep-samples` | examples / demo 폴더도 분석 |
| `--collapse auto\|always\|never` | 반복 묶음 접기. 기본 `auto` = 번호 시리즈는 항상, 그 외는 큰 프로젝트일 때만 |
| `--reps N` | 반복 묶음에서 남길 대표 파일 수 (기본 2) |
| `--include 'glob'` / `--exclude 'glob'` | 규칙보다 우선하는 강제 포함·제외 |

무엇을 제외했는지는 결과 HTML 오른쪽 위 "파일 N개 분석 · M건 제외" 버튼에서 볼 수 있다.

## 라이선스

MIT
