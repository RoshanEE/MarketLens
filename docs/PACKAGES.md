# MarketLens — Backend Package Reference

---

## Web Framework

| Package | What it is | Use in project |
|---|---|---|
| `fastapi` | Async Python web framework | Defines all API routes (`/runs`, `/stream`, `/auth/me`, `/health`) |
| `starlette` | ASGI toolkit FastAPI is built on | Transitive dep; provides `StreamingResponse` (used for SSE) and middleware |
| `uvicorn` | ASGI server | Runs the FastAPI app in development (`--reload`) and production |
| `httptools` | Fast HTTP parser | Transitive dep of uvicorn; improves HTTP parsing throughput |
| `watchfiles` | File system watcher | Transitive dep of uvicorn; powers `--reload` in dev mode |
| `python-multipart` | Form data parser | Required by FastAPI to parse `multipart/form-data` bodies |
| `click` | CLI argument parsing | Transitive dep of uvicorn; used for its `uvicorn` CLI entry point |
| `h11` | HTTP/1.1 state machine | Transitive dep of uvicorn/httpcore; handles low-level HTTP framing |

---

## Database / Supabase

| Package | What it is | Use in project |
|---|---|---|
| `supabase` | Supabase Python SDK | `security.py` — `create_client()` + `client.auth.get_user(token)` to verify JWTs; also pulls in auth, storage, realtime sub-clients as transitive deps |
| `asyncpg` | Async PostgreSQL driver | SQLAlchemy's async engine uses this to connect to Supabase's Postgres (`postgresql+asyncpg://`) |
| `SQLAlchemy` | Python ORM | Defines `ResearchRun`, `SourceUrl`, `Report` models; all DB queries use `AsyncSession` |
| `psycopg2-binary` | Sync PostgreSQL driver | Used by `migrate.py` for synchronous migration script; may also be needed for Alembic |
| `greenlet` | Lightweight coroutines | Transitive dep of SQLAlchemy async; bridges sync/async boundaries internally |

---

## Cryptography

| Package | What it is | Use in project |
|---|---|---|
| `cryptography` | Cryptographic primitives | Transitive dep of the Supabase SDK for TLS/HTTPS operations |
| `cffi` | C Foreign Function Interface | Transitive dep of `cryptography`; allows calling C crypto libraries from Python |
| `pycparser` | C code parser | Transitive dep of `cffi` |

---

## AI / LLM

| Package | What it is | Use in project |
|---|---|---|
| `anthropic` | Anthropic SDK | `LLMClient` wraps this; used if `ANALYSIS_MODEL` or `JUDGE_MODEL` points to a Claude model |
| `openai` | OpenAI SDK | `LLMClient` wraps this; used for GPT-4.1 (analysis) and GPT-4.1-mini (chunker + judge) |
| `jiter` | Fast JSON iterator | Transitive dep of both SDKs; used internally for streaming JSON parsing |
| `tqdm` | Progress bar library | Transitive dep of the Anthropic SDK |

---

## HTTP & Async Networking

| Package | What it is | Use in project |
|---|---|---|
| `httpx` | Async HTTP client | `crawler.py` — issues concurrent HTTP requests to crawl each source URL |
| `httpcore` | Low-level HTTP engine | Transitive dep of `httpx`; handles connection pooling and protocol details |
| `anyio` | Async compatibility layer | Transitive dep of `httpx` and FastAPI; provides async primitives that work with asyncio |
| `sniffio` | Async library detector | Transitive dep of `anyio`; detects which async library is running |
| `h2` | HTTP/2 protocol implementation | Transitive dep of `httpx`; enables HTTP/2 connections to crawl targets |
| `hpack` | HTTP/2 header compression | Transitive dep of `h2` |
| `hyperframe` | HTTP/2 frame parser | Transitive dep of `h2` |
| `websockets` | WebSocket protocol | Transitive dep of Supabase `realtime` client |
| `multidict` | Multi-value dict | Transitive dep of Supabase `realtime` (which uses aiohttp internally) |
| `propcache` | Property caching | Transitive dep of `yarl`/aiohttp |
| `yarl` | URL parsing library | Transitive dep of Supabase SDK and aiohttp |

---

## Web Scraping

| Package | What it is | Use in project |
|---|---|---|
| `trafilatura` | Article content extractor | `crawler.py` — primary extractor; strips nav/ads/boilerplate and returns clean article text |
| `beautifulsoup4` | HTML parser | `crawler.py` — fallback when Trafilatura returns nothing; extracts visible text from raw HTML |
| `soupsieve` | CSS selector engine | Transitive dep of BeautifulSoup4 |
| `lxml` | Fast XML/HTML parser | Transitive dep of both trafilatura and bs4; used as their parsing backend |
| `lxml_html_clean` | HTML sanitizer for lxml | Transitive dep of trafilatura; strips unsafe/junk HTML elements |
| `htmldate` | Date extractor from HTML | Transitive dep of trafilatura; extracts publication dates from crawled pages |
| `courlan` | URL cleaner/canonicalizer | Transitive dep of trafilatura; normalizes and validates URLs |
| `jusText` | Boilerplate removal | Transitive dep of trafilatura; one of its content extraction strategies |
| `tld` | Top-level domain lookup | Transitive dep of trafilatura/courlan; used for URL domain classification |

---

## Config & Validation

| Package | What it is | Use in project |
|---|---|---|
| `pydantic` | Data validation library | All request/response schemas (`ResearchRunCreate`, `ReportOut`, etc.); also used for `Settings` model |
| `pydantic-settings` | Settings management | `config.py` — `Settings` class reads env vars from `.env` via `BaseSettings` |
| `pydantic_core` | Pydantic's Rust core | Transitive dep of pydantic; the high-performance validation engine |
| `annotated-types` | Type annotation helpers | Transitive dep of pydantic |
| `python-dotenv` | `.env` file loader | Transitive dep of pydantic-settings; loads `backend/.env` into environment |
| `docstring_parser` | Docstring parser | Transitive dep of the Anthropic SDK; used for tool/function schema generation |
| `typing_extensions` | Backported type hints | Transitive dep across many packages |
| `typing-inspection` | Runtime type introspection | Transitive dep of pydantic |

---

## Date & Time

| Package | What it is | Use in project |
|---|---|---|
| `python-dateutil` | Date parsing utilities | Transitive dep of `htmldate` |
| `dateparser` | Natural language date parser | Transitive dep of `htmldate`; parses varied date formats on crawled pages |
| `pytz` | Timezone definitions (legacy) | Transitive dep of dateparser |
| `tzdata` | IANA timezone database | Transitive dep of pytz |
| `tzlocal` | Local timezone detection | Transitive dep of dateparser |
| `babel` | Locale/internationalization | Transitive dep of dateparser; helps parse localized date strings |

---

## Logging & Resilience

| Package | What it is | Use in project |
|---|---|---|
| `structlog` | Structured logging | Used throughout — `log.info(...)`, `log.error(...)` with key-value context in every service |
| `tenacity` | Retry library | `crawler.py` — retries failed HTTP requests with exponential backoff |

---

## Testing

| Package | What it is | Use in project |
|---|---|---|
| `pytest` | Test framework | Runs all tests in `backend/tests/` |
| `pytest-asyncio` | Async test support | Allows `async def test_*` functions; configured with `asyncio_mode = strict` in `pytest.ini` |

---

## Utilities

| Package | What it is | Use in project |
|---|---|---|
| `colorama` | ANSI color codes on Windows | Transitive dep of click/structlog; makes colored terminal output work on Windows |
| `distro` | Linux distro detection | Transitive dep of the Anthropic/OpenAI SDKs; included in telemetry/user-agent strings |
| `packaging` | Version parsing | Transitive dep across many packages |
| `deprecation` | Deprecation warning helpers | Transitive dep of supabase sub-clients |
| `PyYAML` | YAML parser | Transitive dep; likely pulled in by one of the SDKs |
| `regex` | Enhanced regex engine | Transitive dep of trafilatura and dateparser |
| `six` | Python 2/3 compat shim | Transitive dep of older libraries (dateutil, etc.) — legacy but harmless |
| `charset-normalizer` | Encoding detection | Transitive dep of httpx/requests; detects character encoding of crawled pages |
| `certifi` | CA certificate bundle | Transitive dep of httpx; validates TLS certificates on crawled URLs and API calls |
| `idna` | Internationalized domain names | Transitive dep of httpx; handles non-ASCII domain names in URLs |
| `urllib3` | HTTP client library | Transitive dep; used by some libraries that haven't migrated to httpx |
