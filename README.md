# Engineering Manager Copilot

A FastAPI service that reads engineering documents and turns them into a
structured review: findings, open questions, suggested changes and a
consolidated Review Brief.

Documents are chunked, embedded and stored in MongoDB Atlas. A retrieval
augmented generation (RAG) pass sends the most relevant chunks to Groq,
which returns structured JSON that is persisted and served through the API.

Every document, chunk, finding, question and decision carries the
`user_id` of the person who uploaded it, and every read is filtered on it.
One user can never see another user's data.

---

## How it works

The end to end workflow is four steps.

```
1. CREATE PROJECT
   POST /api/v1/projects
   name + objective describe what the review should look for
                    |
2. UPLOAD SOURCES
   POST /api/v1/projects/{project_id}/sources/upload
   one or more PDF / DOCX / TXT files, saved to uploads/
                    |
3. RUN THE AI REVIEW
   POST /api/v1/projects/{project_id}/ai-trigger
   every source is reviewed, in parallel
                    |
4. READ THE RESULTS
   GET  /findings      GET /questions      GET /changes
   GET  /review-brief  GET /decisions      POST /decisions
```

### What happens inside the AI trigger

```
project_id + user_id
        |
   load project                          404 if not yours
        |
   load EVERY source for the project     400 if there are none
        |
   ai_review_status = "processing"
        |
   warm the embedding model + vector store   (once, on one thread)
        |
   +----------------------------------------------+
   |  ThreadPoolExecutor, MAX_REVIEW_WORKERS = 4  |
   |                                              |
   |  for each source, independently:             |
   |     partition  ->  filter  ->  chunk         |
   |     embed + store chunks   (skipped if the   |
   |                             source is already|
   |                             ingested)        |
   |     vector search, top REVIEW_TOP_K = 3      |
   |     Groq, structured JSON output             |
   |     store findings / questions / changes     |
   +----------------------------------------------+
        |
   build the Review Brief ONCE, after all workers finish
        |
   ai_review_status = "completed" | "partial" | "failed"
        |
   return aggregated counts + per source rows
```

Two details in that diagram matter:

**Sources are reviewed in parallel, but each review sees only its own
file.** A Groq prompt never mixes content across documents, so a finding
always traces back to exactly one source.

**The Review Brief is built once, after the fan out.** Building it inside
the workers would race: each build reads the whole project back out of
MongoDB and upserts the same document, so the last writer would win with a
partial snapshot.

### Ingestion is idempotent, review results are not

`count_chunks` guards ingestion, so re-triggering a review does not
re-chunk or re-embed a file that is already stored.

Findings, questions and changes are **appended**, not replaced. Triggering
a review twice leaves two sets of results in the collections, while the
project counters reflect only the most recent run.

---

## Project structure

```
app/
  main.py                     FastAPI app, router registration, OpenAPI fix
  api/routes/
    auth.py                   signup, me
    projects.py               create / list / get / delete projects
    upload.py                 multi-file upload, list, delete sources
    ai_review.py              the AI trigger endpoint
    findings.py               list and delete findings
    questions.py              list, get and delete questions
    changes.py                list, get and delete changes
    decisions.py              list / create / update / delete decisions
    review_brief.py           consolidated brief
  core/
    config.py                 all environment-backed settings
    security.py               JWT creation and decoding, password hashing
    deps.py                   get_current_user, the auth dependency
  db/
    mongodb.py                client, collection handles, startup helpers
  schemas/                    Pydantic request and response models
  services/
    document_processor.py     partition -> filter -> chunk -> Document
    embeddings.py             cached HuggingFace embedding model
    vector_store.py           Atlas vector search, index-lag tolerant
    vector_index.py           creates the vector index at startup
    ai_review_service.py      the review pipeline and the parallel trigger
    ai_review_storage.py      persists findings/questions/changes + brief
uploads/                      uploaded source files, named by source id
```

---

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env            # then fill in the values below
uvicorn app.main:app --reload
```

Swagger UI: <http://127.0.0.1:8000/docs>

On startup the app pings MongoDB, creates any missing collections, and
creates the Atlas vector search index if it does not exist.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `MONGODB_URI` | — | **Required.** Atlas connection string |
| `MONGODB_DATABASE` | `emc_db` | Database name |
| `VECTOR_INDEX_NAME` | `vector_index` | Atlas vector search index |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 384-dimension embeddings |
| `GROQ_API_KEY` | — | **Required.** Groq API key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model used for the review |
| `MAX_CHARACTERS` | `2000` | Hard chunk size cap |
| `NEW_AFTER_N_CHARS` | `1500` | Soft chunk boundary |
| `COMBINE_TEXT_UNDER_N_CHARS` | `500` | Merge fragments below this |
| `OVERLAP` | `200` | Character overlap between chunks |
| `VECTOR_SEARCH_SYNC_TIMEOUT` | `45` | Seconds to wait for the index to catch up |
| `VECTOR_SEARCH_SYNC_INTERVAL` | `1.5` | Seconds between search retries |
| `VECTOR_INDEX_READY_TIMEOUT` | `180` | Seconds startup waits for the index |

Two settings are **not** environment-backed and live in code:

- `MAX_REVIEW_WORKERS = 4` and `REVIEW_TOP_K = 3` in `app/services/ai_review_service.py`
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRES_MINUTES` in `app/core/security.py`

---

## API reference

All routes except `/`, `/health` and `/api/v1/auth/signup` require
`Authorization: Bearer <token>`.

### Authentication

| Method | Path |
|---|---|
| POST | `/api/v1/auth/signup` |
| GET | `/api/v1/auth/me` |

Signup returns a JWT valid for 60 minutes. **There is currently no login
or refresh endpoint** — the login route in `auth.py` is commented out, so
signup is the only way to obtain a token.

### Projects

| Method | Path |
|---|---|
| POST | `/api/v1/projects` |
| GET | `/api/v1/projects` |
| GET | `/api/v1/projects/{project_id}` |
| DELETE | `/api/v1/projects/{project_id}` |

`name` and `objective` are required; `analysis_focus` is optional. All
three are used to build the retrieval query, so a specific objective
produces a sharper review.

### Sources

| Method | Path |
|---|---|
| POST | `/api/v1/projects/{project_id}/sources/upload` |
| GET | `/api/v1/projects/{project_id}/sources` |
| DELETE | `/api/v1/projects/{project_id}/sources/{source_id}` |

Upload accepts **multiple files** in one request as repeated `files`
parts. PDF, DOCX and TXT only, at most 10 files per request and 25 MB per
file. Each file is processed independently, so one bad file does not fail
the batch:

```json
{
  "status": "partial",
  "message": "2 of 3 sources uploaded successfully",
  "projectId": "project_8f4a72c91b32",
  "uploadedCount": 2,
  "failedCount": 1,
  "sources": [ { "id": "source_...", "sourceName": "a.pdf", "...": "..." } ],
  "failed": [ { "sourceName": "budget.xlsx", "error": "Unsupported file type. ..." } ]
}
```

`status` is `"success"` when everything landed, `"partial"` otherwise. If
nothing lands the request returns 400.

### AI Review

| Method | Path |
|---|---|
| POST | `/api/v1/projects/{project_id}/ai-trigger` |

No request body. Reviews every source on the project and returns counts,
not content — read the findings and questions endpoints for the detail.

```json
{
  "success": true,
  "message": "AI review is ready",
  "data": {
    "projectId": "project_...",
    "status": "completed",
    "aiReviewReady": true,
    "sourceCount": 2,
    "reviewedCount": 2,
    "failedCount": 0,
    "findingCount": 6,
    "questionCount": 6,
    "changeCount": 0,
    "sources": [
      { "sourceId": "source_...", "sourceName": "payments.txt",
        "findingCount": 3, "questionCount": 3, "changeCount": 0 }
    ],
    "failed": []
  }
}
```

`status` is `"completed"`, `"partial"` or `"failed"`. Top level counts sum
over successful sources only.

400 is returned for an unknown project, a project with no sources, or when
every source fails. 500 covers everything else, including missing Groq
configuration.

This call is **synchronous** and holds the connection for the whole run.
Two small text files take roughly 75 seconds; PDFs are considerably slower
because `partition_pdf` runs with `strategy="hi_res"`.

### Findings

| Method | Path |
|---|---|
| GET | `/api/v1/projects/{project_id}/findings` |
| DELETE | `/api/v1/projects/{project_id}/findings/{finding_id}` |

```json
{
  "success": true,
  "message": "Findings fetched successfully",
  "data": {
    "projectId": "project_...",
    "findingCount": 1,
    "findings": [
      {
        "id": "finding_a32eff94",
        "title": "No tested database restore path",
        "summary": "Backups run nightly but restores are untested.",
        "priority": "high",
        "category": "resilience",
        "section": "2.1",
        "page": 4,
        "confidence": 0.82,
        "needsAttention": true,
        "suggestedQuestion": "When was the last restore rehearsal?",
        "evidence": [
          {
            "id": "EV-1a2b3c4d",
            "sourceId": "source_abc123",
            "sourceName": "payments.txt",
            "page": 4,
            "section": "2.1",
            "quote": "restores have not been tested"
          }
        ],
        "created_at": "2026-08-25T20:26:08.370000"
      }
    ]
  }
}
```

Evidence is embedded inside each finding, and every entry carries the
verbatim `quote` backing the claim.

### Questions

| Method | Path |
|---|---|
| GET | `/api/v1/projects/{project_id}/questions` |
| GET | `/api/v1/projects/{project_id}/questions/{question_id}` |
| DELETE | `/api/v1/projects/{project_id}/questions/{question_id}` |

```json
{
  "id": "Q-be3071fb",
  "text": "What decisions are currently pending and what is their status?",
  "priority": "medium",
  "findingId": "finding_a4c91d070abf",
  "evidenceId": "EV-1fe64c1e",
  "createdAt": "2026-08-25T14:01:55.670000"
}
```

The question text lives under **`text`**, not `question`. Documents
written before the rename still hold `question`, and reads fall back to
it, so old and new rows both work without a migration.

`sourceId` is deliberately not returned. To trace a question back to its
file, follow `findingId` and read the `sourceId` on that finding's
evidence.

DELETE decrements the project `question_count`, guarded so it never drops
below zero.

### Changes

| Method | Path |
|---|---|
| GET | `/api/v1/projects/{project_id}/changes` |
| GET | `/api/v1/projects/{project_id}/changes/{change_id}` |
| DELETE | `/api/v1/projects/{project_id}/changes/{change_id}` |

Changes are modifications the review found described in the sources -
something added, altered, removed, still unresolved since a previous
review, or explicitly planned.

```json
{
  "id": "C-1a2b3c4d",
  "title": "Security scanning",
  "detail": "Dependency and container scans are now part of CI.",
  "changeType": "added",
  "section": "8.4",
  "page": 36,
  "createdAt": "2026-08-25T14:01:55.670000"
}
```

`changeType` is one of `added`, `modified`, `removed`, `unresolved` or
`planned`.

Unlike the other delete endpoints, DELETE decrements no counter: projects
carry no `change_count` field, because the AI trigger `$unset`s it on
every run.

### Decisions

| Method | Path |
|---|---|
| GET | `/api/v1/projects/{project_id}/decisions` |
| POST | `/api/v1/projects/{project_id}/decisions` |
| PATCH | `/api/v1/projects/{project_id}/decisions/{decision_id}` |
| DELETE | `/api/v1/projects/{project_id}/decisions/{decision_id}` |

Decisions are created by hand, not by the AI. A decision may optionally
link to a `finding_id`, which is validated against the same project.

`status` is `open` or `resolved`. Moving to `resolved` stamps
`resolvedAt`; moving back to `open` clears it. PATCH is a true partial
update — an omitted field is left alone, while an explicit `null` clears
it — and an empty body returns 400.

### Review Brief

| Method | Path |
|---|---|
| GET | `/api/v1/projects/{project_id}/review-brief` |

The consolidated view of everything the review produced, rebuilt at the
end of each AI trigger.

---

## Data model

All collections live in `MONGODB_DATABASE` and are created at startup.

| Collection | Holds |
|---|---|
| `users` | Accounts and hashed passwords |
| `projects` | Project metadata, review status, counters |
| `sources` | One document per uploaded file |
| `document_chunks` | Embedded chunks — the vector search collection |
| `findings` | Review findings, with evidence embedded |
| `questions` | Open questions raised by the review |
| `decisions` | Manually recorded decisions |
| `changes` | Suggested changes |
| `review_brief` | One consolidated brief per project |

There is **no `evidence` collection** — evidence is an embedded array
inside each finding.

### Finding document

| Field | Type | Notes |
|---|---|---|
| `_id` | str | `finding_<12 hex>`, returned as `id` |
| `project_id` | str | Not exposed by the API |
| `source_id` | str | Not exposed by the API |
| `user_id` | str | Not exposed by the API |
| `title` | str | |
| `summary` | str | |
| `priority` | str | Normalised by `normalize_priority()` |
| `category` | str | |
| `section` | str | |
| `page` | int | |
| `confidence` | float | |
| `needsAttention` | bool | |
| `suggestedQuestion` | str or null | The only nullable field |
| `evidence` | list | `id`, `sourceId`, `sourceName`, `page`, `section`, `quote` |
| `created_at` | datetime | UTC |

### Chunk metadata

`project_id`, `source_id`, `user_id`, `chunk_id`, `page_number`,
`section`, `source`. All three ids are used as vector search pre-filters.

---

## Document processing

`app/services/document_processor.py` runs four stages:

1. **Partition** — `partition_pdf` (`strategy="hi_res"`), `partition_docx`
   or `partition_text` by extension.
2. **Filter** — keeps `Title`, `NarrativeText`, `Text`, `ListItem`,
   `Header`, `Footer`, `UncategorizedText`.
3. **Chunk** — `chunk_by_title`, so chunks respect section boundaries
   rather than cutting blindly every N characters.
4. **Wrap** — LangChain `Document` objects carrying the metadata above.

Each stage raises if it produces nothing, so an empty result cannot pass
silently through to the model.

### Atlas index lag

Atlas builds its vector index asynchronously, so chunks written a moment
ago are not immediately searchable. `search_chunks` retries until the
index catches up, then falls back to a direct collection read, and only
re-raises if nothing is stored at all. This is what stops the first review
of a freshly uploaded file failing with "No vector chunks found".

---

## Known gaps

Behaviour worth knowing before relying on the service.

- **No login or refresh endpoint.** Tokens expire after 60 minutes and
  signup is the only way to get a new one. `JWT_SECRET` is also hardcoded
  to a placeholder in `app/core/security.py` and should move to `.env`.
- **Re-triggering a review appends.** Findings, questions and changes from
  earlier runs are never removed, so results accumulate while the project
  counters show only the latest run.
- **Only 3 chunks per source reach the model** (`REVIEW_TOP_K`). Content
  ranked fourth or lower is never seen, however well the file is chunked.
- **`GET /findings` returns 200 for an unknown project**, not 404 — it has
  no ownership check, unlike questions and decisions.
- **Timestamps read from MongoDB have no timezone suffix.** `MongoClient`
  runs with `tz_aware=False`, so a value returned right after a write
  carries `Z` while the same value on a later read does not. Clients that
  parse ISO strings may treat the latter as local time.
- **`source_count` is not incremented on upload.** It is corrected the
  next time a review completes.
- **The AI trigger is synchronous.** `ai_review_status` already models
  `processing -> completed`, so moving the trigger to a background task
  and polling the project is the natural next step for large batches.
