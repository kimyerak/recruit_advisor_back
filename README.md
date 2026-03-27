# recruit_advisor_back

KT 채용공고 기반 AI 멘토 어드바이저 백엔드

## 구조

```
backend/
├── main.py                  # FastAPI 앱 진입점
├── api/
│   └── chat.py              # POST /api/chat 엔드포인트
├── graph/
│   ├── builder.py           # LangGraph 그래프 빌드
│   ├── state.py             # ChatState 정의
│   └── nodes/
│       ├── rag.py           # 채용공고 벡터 검색 노드
│       └── responder.py     # 멘토 페르소나 + 답변 생성 노드
├── mentors/
│   └── personas.py          # 3개 멘토 페르소나 및 system_prompt
├── knowledge/
│   ├── loader.py            # PDF → Vision LLM 파싱
│   ├── vectorstore.py       # Chroma 벡터스토어 CRUD
│   └── ingest.py            # PDF 인제스트 스크립트
└── config/
    └── settings.py          # 환경변수 설정
```

## 시작하기

```bash
pip install -r requirements.txt
cp .env.example .env  # OPENAI_API_KEY 입력
uvicorn backend.main:app --reload
```

## JD PDF 인제스트

```bash
python -m backend.knowledge.ingest --pdf path/to/jd.pdf --job_id cloud-migration
```

## API

### `POST /api/chat`
```json
{
  "session_id": "uuid",
  "mentor_id": "kim_seonbae",
  "job_id": "cloud-migration",
  "message": "자격요건이 어떻게 되나요?"
}
```
