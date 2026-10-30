# Document Service: Django Backend

A persistent backend built with Django and Django REST Framework. Users register, log in with JWT, upload documents (a file or a JSON body), list them with pagination, and run text queries over their own documents. Every query is logged.

## Tech stack

| Area | Choice |
|------|--------|
| Language | Python 3.12 |
| Framework | Django + Django REST Framework |
| Auth | JWT via `djangorestframework-simplejwt` (with token blacklist) |
| Database | SQLite (default, easy to swap for Postgres) |
| File parsing | `pypdf` (PDF), `python-docx` (DOCX), built-in decoding (TXT, MD) |

## Project structure

```
docservice/
├── config/                  # project settings and root URLs
├── api/
│   ├── models.py            # Document, QueryLog, UserSession
│   ├── serializers/
│   │   ├── __init__.py
│   │   └── document.py      # DocumentSerializer (validation + text extraction)
│   ├── views.py             # auth, document and query views
│   ├── urls.py
│   ├── pagination.py        # StandardPagination
│   ├── exceptions.py        # PayloadTooLarge (413)
│   ├── utils.py             # extract_text for uploaded files
│   └── admin.py
├── manage.py
└── requirements.txt
```

## Setup

```powershell
git clone <repo-url>
cd docservice
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin
python manage.py runserver
```

Check that the server is up: `GET http://127.0.0.1:8000/health` returns `{"status": "ok"}`.

## Configuration

Set in `config/settings.py`:

| Setting | Value | Purpose |
|---------|-------|---------|
| `MAX_UPLOAD_SIZE` | 5 MB | Larger uploads return 413 |
| `ALLOWED_EXTENSIONS` | `.txt .md .pdf .docx` | Upload whitelist |
| `SIMPLE_JWT.ACCESS_TOKEN_LIFETIME` | 30 minutes | Access token validity |
| `SIMPLE_JWT.REFRESH_TOKEN_LIFETIME` | 1 day | Refresh token validity |
| Pagination | page size 10, `page_size` override, max 100 | List endpoints |

## Data model

| Model | Fields |
|-------|--------|
| `Document` | id (UUID), title, content, uploaded_at, owner (FK User) |
| `QueryLog` | id (UUID), query_text, result_summary, created_at, user (FK User) |
| `UserSession` | id, user (FK User), token, created_at, expires_at |

## API reference

All endpoints except `/health`, `/register` and `/login` require the header:

```
Authorization: Bearer <access_token>
```

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Liveness check |
| POST | `/register` | No | Create a user |
| POST | `/login` | No | Returns `access` and `refresh` tokens |
| POST | `/logout` | Yes | Blacklists the refresh token |
| POST | `/token/refresh` | No | Exchanges a refresh token for a new access token |
| POST | `/documents` | Yes | Upload a file or send JSON; returns 201 |
| GET | `/documents` | Yes | Paginated list of the caller's documents |
| GET | `/documents/{id}` | Yes | One document; 404 if missing or not owned |
| DELETE | `/documents/{id}` | Yes | Returns 204; 403 if not the owner |
| POST | `/query` | Yes | Runs a query, creates and returns a `QueryLog` |
| GET | `/queries` | Yes | Paginated query history of the caller |

### Request examples

Register and log in (JSON):

```json
{"username": "alice", "password": "pass12345"}
```

Create a document from JSON:

```json
{"title": "Meeting notes", "content": "Discussed the roadmap..."}
```

Create a document from a file: send `multipart/form-data` with a `file` field. `title` and `content` are optional (see decisions below).

Run a query:

```json
{"query_text": "roadmap"}
```

### Paginated response shape

```json
{
  "count": 23,
  "next": "http://127.0.0.1:8000/documents?page=2",
  "previous": null,
  "results": []
}
```

Use `?page=2&page_size=5` to navigate.

### Document response

```json
{
  "id": "3f8a1c5e-9b2d-4e7a-8c61-0d5f2a7b9e14",
  "title": "notes.pdf",
  "content": "...extracted text...",
  "uploaded_at": "2026-10-30T10:15:00Z",
  "owner": "alice"
}
```

### Status codes

| Code | When |
|------|------|
| 200 | Successful read |
| 201 | Document, user or query created |
| 204 | Document or session deleted |
| 400 | Validation failure, such as an unsupported file type, missing fields, or an unreadable file |
| 401 | Missing, invalid or expired token |
| 403 | Deleting a document you don't own |
| 404 | Document not found, or not owned (on GET) |
| 413 | Uploaded file exceeds the size limit |

## Key flows

### Authentication

```
POST /register  -> user created (201)
POST /login     -> credentials checked
                -> refresh token created, UserSession row saved (token = refresh jti)
                -> returns access (30 min) + refresh (1 day)
API calls       -> Authorization: Bearer <access>
access expires  -> POST /token/refresh with refresh -> new access token
POST /logout    -> refresh token blacklisted, UserSession row removed
```

### Document creation

```
POST /documents
  -> JWT checked (401 if invalid)
  -> parser chosen by Content-Type (multipart or JSON)
  -> validate_file (if a file was sent):
       extension in whitelist?   else 400
       size <= 5 MB?             else 413
       PDF/DOCX header matches?  else 400
  -> validate:
       a file or content is required    else 400
       title missing  -> filename if a file was sent, otherwise 400
       content missing -> text extracted from the file
  -> row saved with owner = authenticated user
  -> 201 with the document
```

### Ownership rules

```
GET    /documents            -> filtered to owner=request.user
GET    /documents/{id}       -> missing or not owned -> 404
DELETE /documents/{id}       -> missing -> 404, not owned -> 403, owned -> 204
```

### Query

```
POST /query
  -> keyword search over the caller's documents
  -> QueryLog saved (query_text, result_summary, user)
  -> 201 with the QueryLog

GET /queries -> the caller's QueryLogs, newest first, paginated
```

## Design decisions

1. **JWT with a blacklist instead of DRF's built-in token.** The spec allows "an equivalent scheme". JWT is stateless and widely used. Short-lived access tokens limit the damage of a leak, and the blacklist lets logout revoke refresh tokens.
2. **`UserSession` records logins.** The token itself is self-contained, so `UserSession` stores the refresh token's `jti` plus creation and expiry times. It satisfies the specified model and gives a place to audit or revoke sessions.
3. **Only extracted text is stored.** The spec's `Document` has `id, title, content, uploaded_at, owner` and no file field. Uploads are validated and parsed, and the text goes into `content`. No files are written to disk, so there's nothing to clean up on delete and nothing to serve.
4. **Title and content fall back from the file.** A file-only upload uses the filename as the title and the extracted text as content. Explicit values from the client always win. JSON requests must include a title.
5. **Custom 413 exception.** DRF's `ValidationError` always produces 400, so a dedicated `PayloadTooLarge` exception gives the specified status code.
6. **Layered file validation.** Extension whitelist, size limit, and a magic-byte check for PDF and DOCX, so a renamed executable can't pass as a PDF. Files with no readable text, such as scanned PDFs, are rejected with 400.
7. **404 for unreadable, 403 for undeletable.** GET returns 404 for another user's document so the ID's existence isn't revealed, while DELETE returns 403, as specified.
8. **UUID primary keys.** Document and query IDs are random UUIDs, so they can't be guessed or enumerated, and they don't reveal how many records exist.
9. **Owner shown as username.** `owner` is serialized with a slug field. The database still stores the foreign key, and the owner is always set from the token, never from the request body.
10. **Stable pagination.** Models define default `ordering`, so pages don't shuffle between requests. Page size defaults to 10, with a client override capped at 100.
11. **Auth endpoints skip authentication.** `/register` and `/login` set `authentication_classes = []`, so a stale token header can't break them.
12. **Query scope.** Queries only search the caller's own documents.

## Security notes

- Passwords are hashed by Django's auth system, with a minimum length of 8.
- Owner-scoped querysets are used everywhere, so users can't read other users' data.
- Access tokens stay valid until they expire, even after logout. This is the standard JWT trade-off, which is why they're short-lived.
- Set a private `SECRET_KEY` and `DEBUG = False` for any real deployment.

## Testing

Manual cases to run in Postman:

| Case | Expected |
|------|----------|
| Any protected call with no token | 401 |
| JSON create with title and content | 201 |
| File only (no title, no content) | 201, title = filename, content = file text |
| Unsupported extension, such as `.zip` | 400 |
| File over 5 MB | 413 |
| `GET /documents?page=2&page_size=2` | Paginated shape, `previous` populated |
| Second user `GET` on another user's document | 404 |
| Second user `DELETE` on another user's document | 403 |
| Owner `DELETE`, then `GET` the same id | 204, then 404 |
| `POST /token/refresh` after logout | 401 |

Automated tests run with:

```powershell
python manage.py test
```

## Known limitations and future improvements

- Original files aren't kept. A `FileField`, an owner-only download endpoint and object storage (S3 via `django-storages`) would add that.
- The query search is keyword-based. It could move to full-text search, or to embeddings for semantic search.
- Scanned PDFs need OCR to be supported.
- Refresh token rotation (`ROTATE_REFRESH_TOKENS` with `BLACKLIST_AFTER_ROTATION`) would further limit stolen refresh tokens.
- Rate limiting on `/login`, and a production database and server (Postgres, gunicorn), are not set up.
