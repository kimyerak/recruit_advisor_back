# KT Recruit Advisor — 백엔드

KT 채용 준비생을 위한 AI 챗봇 백엔드입니다.
KT 위즈 마스코트 **빅(Vic)** 과 **또리(Ddory)** 캐릭터가 채용공고 분석, 자소서 조언, 커리어 고민에 답변하며,
KT 재직 선배들의 실제 경험 데이터를 RAG로 참조해 근거 있는 답변을 제공합니다.

---

## 목차

1. [시스템 아키텍처](#1-시스템-아키텍처)
2. [데이터 구성](#2-데이터-구성)
3. [AI 처리 흐름 (Agentic RAG)](#3-ai-처리-흐름-agentic-rag)
4. [에이전트 설계 전략](#4-에이전트-설계-전략)
5. [추천질문 생성](#5-추천질문-생성)
6. [캐릭터 소개](#6-캐릭터-소개)
7. [API 명세](#7-api-명세)
8. [환경 설정 및 실행](#8-환경-설정-및-실행)
9. [데이터 관리](#9-데이터-관리)
10. [기술 스택](#10-기술-스택)
11. [디렉터리 구조](#11-디렉터리-구조)

---

## 1. 시스템 아키텍처

```
┌─────────────┐     POST /api/chat      ┌──────────────────────────────────────┐
│  Frontend   │ ──────────────────────► │           FastAPI Backend            │
│ (React)     │ ◄────────────────────── │                                      │
└─────────────┘    reply + suggestions  │  ┌────────────────────────────────┐  │
                                        │  │        LangGraph Workflow       │  │
                                        │  │                                 │  │
                                        │  │  guardrail → intent → rag       │  │
                                        │  │                  ↓              │  │
                                        │  │               grade             │  │
                                        │  │                  ↓              │  │
                                        │  │          clear_context          │  │
                                        │  │                  ↓              │  │
                                        │  │           responder             │  │
                                        │  └────────────────────────────────┘  │
                                        │                                      │
                                        │  ┌──────────────────────────────┐   │
                                        │  │        ChromaDB (로컬)        │   │
                                        │  │  · jd_collection             │   │
                                        │  │  · senior_collection          │   │
                                        │  │  · culture_collection         │   │
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
| `jd_collection` | KT 채용공고 PDF | 채용공고·자격요건 질문 (`jd`) | 4개 |
| `senior_collection` | KT 재직 선배 경험담 | 자소서·커리어 고민 질문 (`resume`, `advice`) | 3개 |
| `culture_collection` | KT 복지·조직문화 PDF | 복지·워라밸·사내문화 질문 (`culture`) | 3개 |

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
> 아래 명령으로 재인제스트하면 됩니다.
>
> ```bash
> python -c "
> from backend.knowledge.senior_data import get_senior_documents
> from backend.knowledge.vectorstore import ingest_senior_documents
> ingest_senior_documents(get_senior_documents())
> "
> ```

### 복지·조직문화 PDF (`culture_collection`)

`backend/knowledge/data/케이티 복지_조직문화.pdf`를 GPT-4o Vision으로 파싱해 저장합니다.

- "복지 어때요?", "워라밸은요?", "연봉 수준이 어떻게 돼?" 같은 질문에 활용
- intent `culture`로 분류된 질문에서만 검색됨
- PDF 교체·업데이트 시 아래 명령으로 재인제스트:

```bash
python -c "
from backend.knowledge.loader import load_pdf_with_vision
from backend.knowledge.vectorstore import ingest_culture_documents
docs = load_pdf_with_vision('backend/knowledge/data/케이티 복지_조직문화.pdf', job_id='kt-culture')
ingest_culture_documents(docs)
"
```

---

## 3. AI 처리 흐름 (Agentic RAG)

### RAG 패턴 분류

이 프로젝트의 RAG는 단순 검색→답변 구조가 아니라, 세 가지 패턴이 결합된 **Agentic RAG**입니다.

| 패턴 | 설명 | 담당 노드 |
|---|---|---|
| **Adaptive RAG** | 질문 유형에 따라 검색 전략을 동적으로 바꿈 | `intent_node` → 컬렉션 라우팅 |
| **Corrective RAG** | 검색 결과가 나쁘면 스스로 교정 (문서를 버리고 LLM 자체 지식으로 전환) | `grade_node` → `clear_context` |
| **Agentic RAG** | 위 둘을 LangGraph 워크플로우로 조율하는 상위 구조 | `builder.py` 전체 |

---

사용자가 메시지를 보내면 LangGraph가 다음 단계를 자동으로 실행합니다.

```
사용자 메시지
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│ ① guardrail_node                                        │
│    KT 취업과 무관하거나 유해한 질문 즉시 차단             │
│    ok → 다음 단계 진행                                   │
│    off_topic / harmful → 안내 메시지 반환 후 종료         │
└───────────────────────────┬─────────────────────────────┘
                            │ (ok인 경우만 진행)
                            ▼
┌─────────────────────────────────────────────────────────┐
│ ② intent_node                                           │
│    LLM이 질문의 의도를 스스로 분류                        │
│    jd / resume / culture / advice                       │
└───────────────────────────┬─────────────────────────────┘
                            │ (모든 intent가 RAG를 거침)
                            ▼
┌─────────────────────────────────────────────────────────┐
│ ③ rag_node                                              │
│    intent에 따라 다른 DB에서 관련 문서 검색               │
│    jd             → jd_collection     (채용공고)          │
│    culture        → culture_collection (복지·조직문화)    │
│    resume, advice → senior_collection  (선배 경험담)      │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│ ④ grade_node                                            │
│    검색된 문서가 질문에 실제로 유용한지 LLM이 평가          │
│    relevant     → 문서를 context로 전달                  │
│    not_relevant → 문서 버림 (clear_context)              │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│ ⑤ responder_node                                        │
│    캐릭터 페르소나 + 대화 히스토리 + context 합쳐서 답변   │
│    선배 경험이 있으면 "선배 얘기로는~" 형태로 인용         │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
                후속 추천 질문 3개 생성
                            │
                            ▼
                   { reply, suggestions }
```

### 각 노드 설명

| 노드 | 역할 | 사용 모델 |
|---|---|---|
| `guardrail_node` | 유해·주제 이탈 질문 차단 (ok / off_topic / harmful) | GPT-4o-mini (temp=0) |
| `intent_node` | 질문 의도 분류 (jd / resume / culture / advice) | GPT-4o-mini (temp=0) |
| `rag_node` | intent별 적절한 ChromaDB 컬렉션 검색 | — (벡터 검색) |
| `grade_node` | 검색 결과 관련성 평가 (relevant / not_relevant) | GPT-4o-mini (temp=0) |
| `responder_node` | 최종 답변 생성 (멀티턴 대화 유지) | GPT-4o-mini (temp=0.7) |

---

## 4. 에이전트 설계 전략

단순 RAG 파이프라인이 아니라 **LangGraph 기반 Agentic RAG** 구조로, 질문의 성격에 따라 검색 대상·답변 방식·프롬프트를 모두 다르게 조합합니다.

> **한눈에 보기**
>
> | 분류 | 전략 | 핵심 효과 |
> |---|---|---|
> | LangGraph | 가드레일 선차단 | 불필요한 LLM 호출 원천 차단 |
> | LangGraph | MemorySaver 멀티턴 | session_id별 대화 히스토리 자동 유지 |
> | 의도 분류 | LLM 기반 intent 분류 | 키워드 없는 질문도 정확히 분류 |
> | 의도 분류 | intent 안전망 | LLM 오출력 시 advice로 폴백 |
> | RAG | intent별 컬렉션 라우팅 | 질문 유형에 맞는 DB만 검색 |
> | RAG | job_id 필터링 | 선택한 직군 공고만 정밀 검색 |
> | RAG | LLM Grader | 유사하지만 무관한 문서 걸러냄 |
> | 프롬프트 | 동적 시스템 프롬프트 | intent·컨텍스트 라벨·지침을 런타임 조합 |
> | 프롬프트 | temperature 차별화 | 분류는 결정론적, 답변은 자연스럽게 |

---

### 4-1. LangGraph 파이프라인 설계

#### 가드레일 선차단

그래프의 첫 번째 노드로 `guardrail_node`를 배치해, KT 취업과 무관하거나 유해한 질문을 즉시 차단합니다.
차단되면 `END`로 바로 분기해 이후 RAG·LLM 호출이 전혀 일어나지 않습니다.

```
사용자 질문 → guardrail_node
    ├─ ok        → intent → rag → grade → responder
    ├─ off_topic → 안내 메시지 반환 후 END  (RAG 호출 없음)
    └─ harmful   → 거절 메시지 반환 후 END  (RAG 호출 없음)
```

키워드 필터가 아니라 LLM이 문맥을 이해해 판단하므로, "KT 폭파시키는 법" 같은 우회 시도도 차단합니다.

#### MemorySaver로 멀티턴 대화 유지

LangGraph의 `MemorySaver` checkpointer를 사용해 `session_id`(= `thread_id`)별로 대화 히스토리를 메모리에 유지합니다.

```python
# builder.py
checkpointer = MemorySaver()
graph = g.compile(checkpointer=checkpointer)

# chat.py
config = {"configurable": {"thread_id": req.session_id}}
result = await graph.ainvoke(input, config=config)
```

같은 `session_id`로 요청하면 이전 대화 내용이 `state["messages"]`에 자동 누적됩니다.
"아까 말한 그 직무에서 자격증이 필요해?"처럼 앞 대화를 참조하는 질문도 자연스럽게 처리합니다.

#### Graceful Degradation (단계별 실패 허용)

각 노드가 독립적으로 실패해도 파이프라인은 끝까지 실행됩니다.

| 실패 지점 | 동작 | 결과 |
|---|---|---|
| RAG 검색 실패 | `context = ""` 로 진행 | LLM 자체 지식으로 답변 |
| Grader 실패 | `not_relevant` 로 판정 | 문서 버리고 계속 진행 |
| 잘못된 intent | `advice` 로 폴백 | 선배 경험 DB 검색 |

ChromaDB 연결 오류·임베딩 오류 등 인프라 장애 시에도 사용자는 빈 화면 대신 답변을 받습니다.

---

### 4-2. 의도 분류 (Intent Classification)

#### LLM 기반 분류 — 키워드 매칭 없음

키워드 매칭은 "자격증 필요해?"처럼 특정 단어가 없는 질문에 취약합니다.
`intent_node`는 LLM이 질문 전체 문맥을 읽고 4가지 의도 중 하나로 분류합니다.

| intent | 의미 | 예시 질문 |
|---|---|---|
| `jd` | 채용공고·자격요건·직무 | "클라우드 자격요건 알려줘" |
| `resume` | 자소서 작성·면접 준비 | "자소서 1번 어떻게 쓰면 돼?" |
| `culture` | 복지·워라밸·조직문화 | "복지포인트 얼마야?" |
| `advice` | 커리어 고민·직무 선택 | "KT 어떤 직무가 저한테 맞을까요?" |

`temperature=0`으로 결정론적으로 동작해, 같은 질문에는 항상 같은 의도가 분류됩니다.

#### 분류 안전망 (Fallback)

LLM이 4가지 값 외의 엉뚱한 단어를 출력해도 파이프라인이 멈추지 않습니다.

```python
# intent.py
if intent not in ("jd", "resume", "culture", "advice"):
    intent = "advice"   # 예상 외 출력 → 선배 경험 DB로 폴백
```

---

### 4-3. Agentic RAG

#### intent별 컬렉션 라우팅

모든 질문을 단일 DB에서 검색하면 "자소서 어떻게 써?"에 채용공고 내용이 나올 수 있습니다.
intent에 따라 검색 대상 컬렉션을 바꿔 관련성을 높입니다.

| intent | 검색 컬렉션 | 이유 |
|---|---|---|
| `jd` | `jd_collection` | 자격요건·직무 질문엔 공고 원문이 최선 |
| `culture` | `culture_collection` | 복지·워라밸 질문엔 공식 복지 문서가 최선 |
| `resume`, `advice` | `senior_collection` | 자소서·커리어 고민엔 실제 선배 경험이 최선 |

#### job_id 기반 채용공고 필터링

`job_id`를 요청에 포함하면 해당 직군 공고 문서만 검색합니다.

```
job_id = ""           → 전체 채용공고에서 검색
job_id = "cloud-2024" → 클라우드 공고 문서만 검색
```

여러 직군 공고를 동시에 DB에 올려놓고, 프론트에서 선택한 직군만 정밀 검색할 수 있습니다.
엉뚱한 직군의 자격요건이 섞여 나오는 문제를 방지합니다.

#### LLM Grader — 문서 관련성 평가

벡터 유사도 검색은 "가장 비슷한 문서"를 반환하지만, 실제로 질문에 도움이 되는지는 보장하지 않습니다.
`grade_node`는 검색된 문서를 LLM이 직접 읽고 유용성을 판단합니다.

```
[질문]    클라우드 직군 면접 준비 어떻게 해?
[검색됨]  KT 네트워크 장비 유지보수 관련 문서

→ grade_node : not_relevant
→ clear_context : context = ""
→ responder_node : LLM 자체 지식으로 답변
```

관련 없는 문서를 억지로 쓰면 틀린 정보를 인용하는 hallucination이 생깁니다.
문서를 버리고 LLM 자체 지식으로 답변하는 편이 낫기 때문에 이 단계를 추가했습니다.

---

### 4-4. 프롬프트 엔지니어링

#### 동적 시스템 프롬프트 조합

매 요청마다 시스템 프롬프트를 런타임에 조합합니다.
고정 프롬프트 하나가 아니라, 역할에 맞는 블록을 쌓아올리는 방식입니다.

```
[KT 브랜드 공통 지침]          ← base_prompt.txt (항상 포함)
+ [캐릭터 설정]                ← vic.txt 또는 ddory.txt
+ [검색된 문서 + 라벨]         ← intent에 따라 라벨 변경
+ [자소서 전용 가이던스]        ← intent == "resume" 일 때만 추가
```

intent에 따라 라벨도 달라져 LLM이 자료의 성격을 정확히 파악합니다.

| intent | 프롬프트 내 라벨 |
|---|---|
| `jd` | `[채용공고 정보]` |
| `resume` | `[자소서 합격 사례]` |
| `culture` | `[KT 복지·조직문화 정보]` |
| `advice` | `[선배 경험]` |

#### temperature 차별화

노드 역할에 따라 temperature를 다르게 설정해 정확성과 자연스러움을 함께 챙깁니다.

| 노드 | temperature | 이유 |
|---|---|---|
| `guardrail_node` | 0 | 차단 여부는 항상 일관되어야 함 |
| `intent_node` | 0 | 같은 질문은 항상 같은 의도로 분류되어야 함 |
| `grade_node` | 0 | 관련성 평가는 주관이 개입되면 안 됨 |
| `responder_node` | 0.7 | 답변은 매번 조금씩 달라야 대화가 자연스러움 |
| `_generate_suggestions` | 0.8 | 추천 질문은 다양할수록 좋음 |

---

## 5. 추천질문 생성

멘토 답변이 반환될 때마다 **LLM을 별도로 한 번 더 호출**해 이어서 물어볼 만한 질문 3개를 생성합니다.

### 동작 방식

```
멘토 답변 완성
    │
    ▼
_generate_suggestions(reply, intent)
    │
    ├── intent별 주제 힌트 설정
    │     jd      → "채용공고, 자격요건, 근무환경, 직무 내용"
    │     culture → "복지, 워라밸, 연봉, 조직문화, 사내 분위기"
    │     advice  → "실무 경험, 팀 분위기, 커리어 성장, 회사 문화"
    │     resume  → "자소서 항목, 표현 방식, KT 핵심가치, 면접 준비"
    │
    ├── GPT-4o-mini에게 프롬프트 전송
    │     "이 답변 읽고 이어서 물어볼 질문 3개를 JSON 배열로만 답해"
    │     "각 질문은 15자 이내"
    │
    └── JSON 파싱 성공 → suggestions 반환
        JSON 파싱 실패 → [] 반환 (에러 무시)
```

### 설계 의도

- 매 답변마다 **답변 내용 + 의도**를 함께 반영한 질문을 동적으로 생성
- 미리 정해진 질문 목록이 아니라 대화 흐름에 맞게 달라짐
- 사용자가 다음에 뭘 물어야 할지 몰라도 대화가 자연스럽게 이어지도록 유도

> 추천질문 생성 로직은 `api/chat.py`의 `_generate_suggestions()` 함수 참고.

---

## 6. 캐릭터 소개

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

## 7. API 명세

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

## 8. 환경 설정 및 실행

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

## 9. 데이터 관리

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

## 10. 기술 스택

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

## 11. 디렉터리 구조

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
│       ├── guardrail.py             # ① 유해·주제 이탈 질문 차단
│       ├── intent.py                # ② 의도 분류 (jd / resume / culture / advice)
│       ├── rag.py                   # ③ 벡터 검색 (intent별 컬렉션 분기)
│       ├── grade.py                 # ④ 문서 관련성 평가
│       └── responder.py             # ⑤ 캐릭터 페르소나 기반 답변 생성
│
├── mentors/                         # 캐릭터 설정
│   ├── personas.py                  # 캐릭터 로딩 로직 (vic / ddory)
│   ├── base_prompt.txt              # KT 브랜드·공통 지침
│   └── profiles/
│       ├── vic.txt                  # 빅 캐릭터 설정
│       └── ddory.txt                # 또리 캐릭터 설정
│
├── knowledge/                       # 데이터 수집 및 저장
│   ├── vectorstore.py               # ChromaDB CRUD (jd / senior / culture 컬렉션)
│   ├── senior_data.py               # KT 선배 경험 문서 (RAG 데이터)
│   ├── loader.py                    # PDF → GPT-4o Vision → 텍스트
│   ├── ingest.py                    # 채용공고 PDF 인제스트 스크립트
│   ├── crawl_linkareer.py           # 링커리어 자소서 크롤러
│   └── data/
│       ├── job_postings/            # 채용공고 PDF 저장 위치
│       └── 케이티 복지_조직문화.pdf  # 복지·조직문화 RAG 데이터
│
└── config/
    └── settings.py                  # .env 로드 (pydantic-settings)
```
