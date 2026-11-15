# 코드맵 (codemap)

코드 폴더나 zip을 넣으면 전체 흐름을 **클릭형 마인드맵 HTML 한 장**으로 만든다.

- 박스 클릭 → 하위 기능과 핵심 코드
- 코드 클릭 → 설명 (다시 누르면 닫힘)
- 줄 번호 클릭 → 그 줄의 파일 경로와 줄 번호 (`경로:줄` 을 복사해 에디터에서 바로 찾아갈 수 있다)
- 층수는 코드 깊이에 따라 달라진다

## 구성

```
SKILL.md                  Claude 가 따르는 작업 지침 (스킬로 설치해서 사용)
skill_scripts/
  codemap.py              실행 진입점 (prepare / read / build, 그리고 scan / skeleton)
  scan.py                 이름·크기만 보고 거르기
  skeleton.py             뼈대 뽑기, 분석 예산 계산, 필요한 줄만 읽기
  build.py                지도(map.txt) → HTML
  mapfmt.py               map.txt 표기 읽기·쓰기 (예전 analysis.json 도 계속 지원)
  stats.py                실험용: 한 번의 분석에서 토큰이 어디에 쓰였는지 측정·비교
template/mindmap.html     마인드맵 템플릿 (단독으로 열면 예시 데이터가 보인다)
examples/                 이 도구의 초기 버전을 분석한 예시 (codemap-self.html 과 그 원본 map.txt)
```

## 설치

Claude 스킬 폴더에 통째로 넣는다.

```bash
git clone https://github.com/chungjin111/codemap.git ~/.claude/skills/codemap
```

## 쓰는 법

Claude 에게 폴더나 zip 을 주고 "코드맵 만들어줘"라고 하면 SKILL.md 의 절차대로 진행한다.
"간단히" 또는 "자세히"라고 덧붙이면 분석 깊이가 달라진다.

직접 돌려 볼 수도 있다 (Python 3.8+, 설치할 것 없음). 명령은 세 번이다.

```bash
# 1. 준비: 거르고 뼈대를 출력한다
python3 skill_scripts/codemap.py prepare ~/my-project --out codemap_out/my-project

# 2. 읽기: 뼈대를 보고 고른 줄만 꺼낸다 (Claude 가 하는 부분)
python3 skill_scripts/codemap.py read codemap_out/my-project src/app.py::create_app src/db.py:40-72

# 3. 빌드: codemap_out/my-project/map.txt 를 쓴 뒤
python3 skill_scripts/codemap.py build codemap_out/my-project
```

지도 표기(map.txt)는 SKILL.md 의 "map.txt" 절과 `examples/codemap-self.map.txt` 를 보면 된다.

## 옵션

`prepare` (그리고 `scan`):

| 옵션 | 뜻 |
|---|---|
| `--depth quick\|normal\|deep` | 분석 깊이. 코드 조각 수와 읽기 줄 수의 상한이 절반 / 기본 / 두 배 |
| `--keep-tests` | 테스트 코드도 분석 |
| `--keep-samples` | examples / demo 폴더도 분석 |
| `--collapse auto\|always\|never` | 반복 묶음 접기. 기본 `auto` = 번호 시리즈는 항상, 그 외는 큰 프로젝트일 때만 |
| `--reps N` | 반복 묶음에서 남길 대표 파일 수 (기본 2) |
| `--include 'glob'` / `--exclude 'glob'` | 규칙보다 우선하는 강제 포함·제외 |

무엇을 제외했는지는 결과 HTML 오른쪽 위 "파일 N개 분석 · M건 제외" 버튼에서 볼 수 있다.

## 토큰을 아끼는 방법

- **이름만 보고 거르기**: 의존성·빌드 결과물·테스트·이미지 등은 열지도 않는다.
- **뼈대 먼저**: 원문 대신 시그니처·호출 관계·긴 함수 안의 구획만 추린 요약을 읽는다 (원문의 5~8%).
- **분석 예산**: 프로젝트 크기에 맞춰 코드 조각 수와 읽기 줄 수의 상한을 정하고, 읽기는 스크립트가 막는다.
- **간결 표기**: 지도는 기호 몇 개로 적고, 코드 원문과 줄 번호는 스크립트가 채운다.
- **명령 세 번**: 준비 → 읽기 → 빌드. 도구를 부르는 횟수를 줄인다.

효과를 재려면 같은 프로젝트를 두 방식으로 돌린 뒤 비교한다.

```bash
python3 skill_scripts/stats.py codemap_out/기준 codemap_out/비교
```

## 라이선스

MIT
