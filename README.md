# KT Recruit Advisor — 백엔드

KT 채용 준비생을 위한 AI 챗봇 백엔드입니다.
KT 위즈 마스코트 **빅(Vic)** 과 **또리(Ddory)** 캐릭터가 채용공고 분석, 자소서 조언, 커리어 고민에 답변하며,
KT 재직 선배들의 실제 경험 데이터를 RAG로 참조해 근거 있는 답변을 제공합니다.

---

## 목차

1. [시스템 아키텍처](#1-시스템-아키텍처)
2. [데이터 구성](#2-데이터-구성)
3. [AI 처리 흐름 (Agentic RAG)](#3-ai-처리-흐름-agentic-rag)
4. [캐릭터 소개](#4-캐릭터-소개)
5. [API 명세](#5-api-명세)
6. [환경 설정 및 실행](#6-환경-설정-및-실행)
7. [데이터 관리](#7-데이터-관리)
8. [기술 스택](#8-기술-스택)
9. [디렉터리 구조](#9-디렉터리-구조)

---

## 1. 시스템 아키텍처

```
┌─────────────┐     POST /api/chat      ┌──────────────────────────────────────┐
│  Frontend   │ ──────────────────────► │           FastAPI Backend            │
│ (React)     │ ◄────────────────────── │                                      │
└─────────────┘    reply + suggestions  │  ┌────────────────────────────────┐  │
                                        │  │        LangGraph Workflow       │  │
                                        │  │                                 │  │
                                        │  │  intent → rag → grade           │  │
                                        │  │                ↓                │  │
                                        │  │          clear_context          │  │
                                        │  │                ↓                │  │
                                        │  │           responder             │  │
                                        │  └────────────────────────────────┘  │
                                        │                                      │
                                        │  ┌──────────────────────────────┐   │
                                        │  │        ChromaDB (로컬)        │   │
                                        │  │  · jd_collection             │   │
                                        │  │  · linkareer_collection       │   │
                                        │  │  · senior_collection          │   │
                                        │  └──────────────────────────────┘   │
                                        └──────────────────────────────────────┘
```

---

## 2. 데이터 구성

AI가 정확한 답변을 하려면 근거가 되는 데이터가 필요합니다.
세 가지 출처의 데이터를 ChromaDB에 저장하고, 질문에 따라 적절한 컬렉션에서 검색합니다.

### ChromaDB 컬렉션 구성

| 컬렉션 | 데이터 출처 | 사용 시점 | 검색 개수 |
|---|---|---|---|
| `jd_collection` | KT 채용공고 PDF | 채용공고·자격요건 질문 | 4개 |
| `senior_collection` | KT 재직 선배 경험담 | 자소서·커리어 고민·실무 질문 | 3개 |

### 채용공고 PDF (`jd_collection`)

`backend/knowledge/data/job_postings/`에 넣은 KT 채용공고 PDF 파일들입니다.

- PDF 각 페이지를 **이미지로 변환**해 GPT-4o Vision이 읽습니다
- 일반 텍스트 추출로는 놓치기 쉬운 표, 인포그래픽, 이미지 속 텍스트까지 인식합니다
- 추출 항목: 직무명, 자격요건, 주요 업무, 복리후생, 전형 절차
- `job_id` 메타데이터로 저장해 특정 채용공고만 필터링 검색 가능

### 선배 경험담 (`senior_collection`)

`backend/knowledge/senior_data.py`에 정의된 KT 재직자 경험 문서입니다.

- 선배별·주제별로 청크 분리 (입사준비 / 실무경험 / 면접준비 / 팀분위기)
- "KT 팀 분위기 어때?" 같은 질문에 실제 선배 이야기를 인용해 답변
- 현재 3명 × 4주제 = **12개 문서** 저장

> **선배 데이터를 추가하거나 수정하려면** `knowledge/senior_data.py`의 `SENIOR_DOCUMENTS` 리스트를 편집하고
> `python -m backend.knowledge.ingest_senior`를 실행하면 됩니다.

---

## 3. AI 처리 흐름 (Agentic RAG)

사용자가 메시지를 보내면 LangGraph가 다음 단계를 자동으로 실행합니다.

```
사용자 메시지
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│ ① intent_node                                           │
│    LLM이 질문의 의도를 스스로 분류                         │
│    jd (채용공고) / resume (자소서) / advice (커리어 고민)  │
└───────────────────────────┬─────────────────────────────┘
                            │ (모든 intent가 RAG를 거침)
                            ▼
┌─────────────────────────────────────────────────────────┐
│ ② rag_node                                              │
│    intent에 따라 다른 DB에서 관련 문서 검색               │
│    jd             → jd_collection (채용공고)              │
│    resume, advice → senior_collection (선배 경험담)      │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│ ③ grade_node                                            │
│    검색된 문서가 질문에 실제로 유용한지 LLM이 평가          │
│    relevant     → 문서를 context로 전달                  │
│    not_relevant → 문서 버림 (clear_context)              │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│ ④ responder_node                                        │
│    캐릭터 페르소나 + 대화 히스토리 + context 합쳐서 답변   │
│    선배 경험이 있으면 "선배 얘기로는~" 형태로 인용         │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
                후속 추천 질문 3개 생성 (비동기 병렬)
                            │
                            ▼
                   { reply, suggestions }
```

### 각 노드 설명

| 노드 | 역할 | 사용 모델 |
|---|---|---|
| `intent_node` | 질문 의도 분류 (jd / resume / advice) | GPT-4o-mini (temp=0) |
| `rag_node` | intent별 적절한 ChromaDB 컬렉션 검색 | — (벡터 검색) |
| `grade_node` | 검색 결과 관련성 평가 (relevant / not_relevant) | GPT-4o-mini (temp=0) |
| `responder_node` | 최종 답변 생성 (멀티턴 대화 유지) | GPT-4o-mini (temp=0.7) |

---

## 4. 캐릭터 소개

KT 위즈 야구단 마스코트인 빅과 또리 중 하나를 선택합니다.
두 캐릭터 모두 동일한 선배 경험 데이터를 참조하지만, 말투와 접근 방식이 다릅니다.

### 빅 (`vic`)

| 항목 | 내용 |
|---|---|
| 상징 | 힘과 공격, 주황색 |
| 대상 | KT 입사를 구체적으로 준비 중인 취준생·경력직 |
| 말투 | 직접적이고 실용적 — "핵심만 말할게", "바로 이거야!" |
| 특기 | 채용공고 자격요건 분석, 면접 실전 준비, 지원 직전 최종 점검 |

### 또리 (`ddory`)

| 항목 | 내용 |
|---|---|
| 상징 | 민첩성과 수비, 파란색 |
| 대상 | KT라는 회사에 관심이 생긴 대학생·탐색 단계 취준생 |
| 말투 | 밝고 친근함 — "같이 알아보자!", 이모지 활용 |
| 특기 | 직군 탐색, 조직문화 안내, KT 전반적인 이해 |

> **캐릭터 말투·설정 수정**: `mentors/profiles/vic.txt` 또는 `ddory.txt` 편집
> **KT 공통 지침 수정**: `mentors/base_prompt.txt` 편집 (서버 재시작 필요)

---

## 5. API 명세

Base URL: `http://localhost:8000`

### `GET /health`

서버 상태 확인.

```
200 OK
{"status": "ok"}
```

### `POST /api/chat`

캐릭터와 대화하는 메인 엔드포인트.

**Request**

```json
{
  "session_id": "user-abc-123",
  "mentor_id": "vic",
  "job_id": "kt-cloud-2024",
  "message": "클라우드 직군 면접 어떻게 준비해?"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `session_id` | string | O | 대화 세션 ID. 같은 ID면 이전 대화를 기억합니다 (멀티턴) |
| `mentor_id` | string | O | `vic` 또는 `ddory` |
| `job_id` | string | X | 특정 채용공고만 검색하고 싶을 때 사용. 없으면 `""` |
| `message` | string | O | 사용자 메시지 |

**Response**

```json
{
  "reply": "클라우드 면접 핵심만 말할게. 딱 3가지야...",
  "session_id": "user-abc-123",
  "suggestions": [
    "기술 면접 질문 예시는?",
    "자격증 어떤 게 필요해?",
    "포트폴리오 어떻게 준비해?"
  ]
}
```

| 필드 | 설명 |
|---|---|
| `reply` | 캐릭터 답변 |
| `session_id` | 요청한 session_id 그대로 반환 |
| `suggestions` | 이어서 물어볼 만한 추천 질문 3개 (15자 이내) |

**에러 응답**

```json
{"detail": "에러 메시지"}
```

| 상태코드 | 원인 |
|---|---|
| `422` | 요청 형식 오류 (필수 필드 누락 등) |
| `500` | 서버 내부 오류 (LLM 호출 실패 등) |

---

## 6. 환경 설정 및 실행

### 사전 요구사항

- Python 3.11+
- OpenAI API Key

### 1. 환경변수 설정

`backend/.env` 파일 생성:

```env
# OpenAI (필수)
OPENAI_API_KEY=sk-...

# 모델 설정
MODEL_NAME=gpt-4o-mini
EMB_MODEL_NAME=text-embedding-3-small

# LangSmith (선택 — LLM 호출 로그 추적)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=kt-agent
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 선배 경험 데이터 인제스트

```bash
set -a && source backend/.env && set +a
python -c "
from backend.knowledge.senior_data import get_senior_documents
from backend.knowledge.vectorstore import ingest_senior_documents
ingest_senior_documents(get_senior_documents())
"
```

### 4. (선택) 채용공고 PDF 인제스트

```bash
python -m backend.knowledge.ingest --pdf path/to/jd.pdf --job_id cloud-2024
```

### 5. 서버 실행

```bash
set -a && source backend/.env && set +a
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

`http://localhost:8000/health` 에서 상태 확인.

---

## 7. 데이터 관리

### 선배 경험 데이터 수정·추가

`backend/knowledge/senior_data.py`의 `SENIOR_DOCUMENTS` 리스트를 편집합니다.

```python
Document(
    page_content="""[선배 정보] 홍길동 | KT 네트워크 직군 5년차 | 한양대 전기공학

[주제: 입사 준비]
네트워크 직군은 CCNA 자격증이 실제로 많이 도움이 됩니다...
""",
    metadata={"senior": "홍길동", "role": "KT 네트워크 직군", "topic": "입사준비"},
),
```

편집 후 재인제스트:

```bash
python -c "
from backend.knowledge.senior_data import get_senior_documents
from backend.knowledge.vectorstore import ingest_senior_documents
ingest_senior_documents(get_senior_documents())
"
```

> `ingest_senior_documents`는 기존 데이터를 전부 지우고 다시 저장합니다 (중복 방지).

### 캐릭터 페르소나 수정

| 수정 대상 | 파일 |
|---|---|
| 빅 말투·성격·전문 분야 | `mentors/profiles/vic.txt` |
| 또리 말투·성격·전문 분야 | `mentors/profiles/ddory.txt` |
| KT 핵심가치·공통 답변 지침 | `mentors/base_prompt.txt` |

텍스트 파일을 직접 편집하면 서버 재시작 시 자동 반영됩니다.

### 채용공고 삭제

```python
from backend.knowledge.vectorstore import delete_job
delete_job("cloud-2024")
```

---

## 8. 기술 스택

| 역할 | 기술 |
|---|---|
| API 서버 | FastAPI + Uvicorn |
| AI 워크플로우 | LangGraph (노드·엣지 기반 그래프) |
| LLM | OpenAI GPT-4o-mini (추론/답변), GPT-4o (PDF Vision 파싱) |
| 임베딩 | OpenAI text-embedding-3-small |
| 벡터 DB | ChromaDB (로컬 파일 저장) |
| LLM 프레임워크 | LangChain |
| 모니터링 | LangSmith (LLM 호출 추적) |
| 설정 관리 | pydantic-settings |

---

## 9. 디렉터리 구조

```
backend/
├── main.py                          # FastAPI 앱 진입점, CORS 설정
├── requirements.txt
├── .env                             # 환경변수 (git 제외)
│
├── api/
│   └── chat.py                      # POST /api/chat, 후속 질문 생성
│
├── graph/                           # LangGraph 워크플로우
│   ├── builder.py                   # 그래프 조립 및 라우팅 로직
│   ├── state.py                     # 노드 간 공유 상태 (ChatState)
│   └── nodes/
│       ├── intent.py                # ① 의도 분류 (jd / resume / advice)
│       ├── rag.py                   # ② 벡터 검색 (intent별 컬렉션 분기)
│       ├── grade.py                 # ③ 문서 관련성 평가
│       └── responder.py             # ④ 캐릭터 페르소나 기반 답변 생성
│
├── mentors/                         # 캐릭터 설정
│   ├── personas.py                  # 캐릭터 로딩 로직 (vic / ddory)
│   ├── base_prompt.txt              # KT 브랜드·공통 지침
│   └── profiles/
│       ├── vic.txt                  # 빅 캐릭터 설정
│       └── ddory.txt                # 또리 캐릭터 설정
│
├── knowledge/                       # 데이터 수집 및 저장
│   ├── vectorstore.py               # ChromaDB CRUD (3개 컬렉션)
│   ├── senior_data.py               # KT 선배 경험 문서 (RAG 데이터)
│   ├── loader.py                    # PDF → GPT-4o Vision → 텍스트
│   ├── ingest.py                    # 채용공고 PDF 인제스트 스크립트
│   ├── crawl_linkareer.py           # 링커리어 자소서 크롤러
│   └── data/
│       └── job_postings/            # 채용공고 PDF 저장 위치
│
└── config/
    └── settings.py                  # .env 로드 (pydantic-settings)
```
