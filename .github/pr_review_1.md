# PR Review: Implement Postgres persistence and Redis caching with CI quality gates

## ✅ Overall Assessment

This is a **well-executed PR** with solid code quality, comprehensive testing, and clear intent. The Redis caching layer is a clean addition that mirrors the existing Postgres degradation philosophy. No blockers—ready to merge.

---

## Review Comments

### 1. Cache Key Normalization Strategy

**File:** `src/cache.py`  
**Lines:** 41–43

Great use of SHA256 for cache keys. One question: why normalize (strip + lowercase) the request text before hashing?

**Pros:** Reduces cache misses from minor formatting differences (e.g., "  Build me a thing  " vs. "build me a thing").

**Consideration:** This also means requests like `"A B C"` and `"a b c"` are treated as identical. Is that always desired? If users submit semantically equivalent but differently-cased API names, they'll get the same generated project. That might be correct, but worth documenting the assumption.

Suggested addition to the docstring:
```python
def _key(request: str) -> str:
    """Normalize (strip + lowercase) the request, then SHA256 it.
    
    This means 'Build an API' and 'build an api' map to the same key—reducing
    cache misses from whitespace/case variance, but potentially conflating
    semantically distinct requests that differ only in case.
    """
    digest = hashlib.sha256(request.strip().lower().encode()).hexdigest()
    return f"build:{digest}"
```

**Why this matters:** Cache key design directly affects hit rates and can have subtle semantic implications. Documenting the normalization choice helps future maintainers understand trade-offs and catch unintended behavior if requirements change (e.g., if case-sensitive project names become significant).

---

### 2. Coverage Metric Exclusion – Jinja Templates

**File:** `pyproject.toml`  
**Lines:** 25–27

Good call excluding Jinja templates from coverage. Quick clarification: are there any *service code* files in `src/agents/api_builder_agent/` that *should* be covered but might accidentally get filtered by this regex?

The current pattern `/src/agents/api_builder_agent/templates/*` looks correct, but if any `.py` files live in that directory, they'd be excluded too. A quick check:
- Is `templates/` a dedicated subdirectory (safe), or are there `.py` files mixed in (risky)?

If it's a dedicated dir, the current config is perfect. If not, consider tightening the glob.

**Why this matters:** A coverage gate is only as good as what it measures. Accidentally excluding service code from the metric can create false confidence and hide uncovered critical paths. This is a low-risk comment but worth a quick verification.

---

### 3. Redis Connection Timeout – 3 Seconds

**File:** `src/cache.py`  
**Lines:** 31–33

The 3-second socket timeout is a sensible default for a cache layer (fail fast, fall back to fresh build). One consideration:

If Redis is temporarily slow (e.g., under heavy load, disk I/O spike), a 3-second timeout will trigger the fallback to a fresh LLM build, which is ~30–60 seconds. This means a temporarily-slow Redis can actually *increase* latency (3s timeout + 60s build vs. 4–5s slow Redis operation).

This is fine *if* you expect Redis to be stable in production. But if you anticipate transient Redis slowness, you might want to:
1. **Log the timeout event** (already done ✓), or
2. **Consider a slightly longer timeout** (e.g., 5–10s) to distinguish between "Redis is down" vs. "Redis is slow."

Current approach is pragmatic; this is just a note for future tuning if you see unexpected fallbacks in production logs.

**Why this matters:** Cache timeouts can have counterintuitive effects. A short timeout is good for reliability but can mask performance regressions in the Redis layer. Understanding the trade-off helps with operational observability.

---

### 4. Failed Builds – Validation vs. LLM Errors

**File:** `tests/test_cache.py`  
**Lines:** 64–67

The test `test_failed_builds_are_not_cached()` checks that validation errors (HTTP 422) are never cached. Excellent.

One follow-up: does this also cover LLM pipeline errors (e.g., the agent graph returns `result.get("error")`)?

Looking at `src/controllers/api_builder.py` line 57–61, those errors also raise HTTP 422. So the test *should* cover them. But consider an explicit test for LLM failure to be extra clear:

```python
def test_llm_errors_are_not_cached(fake_redis, monkeypatch):
    """Verify that LLM pipeline errors don't pollute the cache."""
    monkeypatch.setattr(settings, "database_url", "")
    client = TestClient(app)
    
    with patch("agents.api_builder_agent.nodes.planner.get_llm",
               side_effect=RuntimeError("llm_error")):
        response = client.post("/api/build", json={"request": BOOK_REQUEST})
    
    assert response.status_code == 422
    assert cache.get_cached_build(BOOK_REQUEST) is None
```

This would make the intent explicit and catch regressions if the error path ever changes.

**Why this matters:** Cache correctness is critical—poisoned cache entries can serve broken results repeatedly. An explicit test for each failure mode (validation, LLM error, etc.) builds confidence that the cache never stores failures, even if the code changes.

---

### 5. X-Cache Header Case – Minor Style Note

**File:** `src/controllers/api_builder.py`  
**Lines:** 52 & 73–76

Small observation: the cache hit response uses lowercase `"X-Cache": "hit"` (line 52), but the response headers are generally case-insensitive in HTTP. This is fine and follows common convention (e.g., CloudFront, Varnish use `X-Cache`), so no change needed—just documenting for consistency.

Consider documenting this in a comment so future maintainers know the header name is intentional:

```python
return Response(
    content=zip_bytes,
    media_type="application/zip",
    headers={"Content-Disposition": f'attachment; filename="{project}.zip"',
             "X-Cache": "hit"},  # Standard cache-hit indicator; case-insensitive in HTTP
)
```

**Why this matters:** HTTP headers are case-insensitive, so this isn't a bug. But documenting design choices (like custom headers) makes the code more maintainable and helps future developers understand the intended client-facing API.

---

## Summary

✅ **All changes are solid.** The PR is well-structured, thoroughly tested, and follows the project's established patterns. These review comments are **suggestions for clarity and future robustness**—not blockers. The code is ready to merge as-is.