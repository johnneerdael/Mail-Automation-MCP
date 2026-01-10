# Embeddings & Semantic Search

Gmail Secretary supports AI-powered semantic search using vector embeddings. Instead of keyword matching, find emails by meaning—search "budget concerns" and find emails about "cost overruns" or "spending issues".

## Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Email Text    │────▶│ Embeddings API   │────▶│ Vector (3072d)  │
│ "Meeting moved" │     │ (Gemini default) │     │ [0.12, -0.34,…] │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                              L2 Normalized ──────────────┤
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Search Query   │────▶│ Embeddings API   │────▶│  Inner Product  │
│ "schedule change"│    │  + Hard Filters  │     │     Search      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Architecture

### Why These Design Choices?

| Design | Choice | Why |
|--------|--------|-----|
| **Provider** | Gemini (default) | Best quality/cost ratio, 3072 dims, generous free tier |
| **Dimensions** | 3072 | Captures nuances in business emails and professional jargon |
| **Normalization** | All vectors L2-normalized | Enables faster inner product search |
| **Index** | HNSW with `vector_ip_ops` | Inner product is faster than cosine for normalized vectors |
| **Search** | Metadata-augmented | Hard filters prevent "vector drift" |

### Metadata-Augmented Search

The strongest pattern for LLM search is **hard filters FIRST, then semantic ranking**:

```sql
-- Prevents finding semantically similar emails from wrong sender/date
SELECT * FROM emails e
JOIN email_embeddings emb ON ...
WHERE e.from_addr ILIKE '%john%'        -- Hard filter (metadata)
  AND e.date >= '2024-01-01'            -- Hard filter (metadata)
ORDER BY emb.embedding <#> query_vec    -- Semantic ranking
LIMIT 10;
```

This prevents "vector drift" where search finds semantically similar content from the wrong context.

## Requirements

- **PostgreSQL** with **pgvector** extension
- **Embeddings API** (Gemini recommended, or Cohere/OpenAI)

## Dimension Selection Guide

::: danger Important: Choose Dimensions Carefully
**Dimension size cannot be changed after initial sync without re-embedding all emails.** See [Migration Guide](#migration-guide) if you need to change dimensions later.
:::

| Dimensions | MTEB Score | Storage (25k emails) | Best For |
|------------|------------|---------------------|----------|
| **768** | 67.99 | ~60 MB | Cost-sensitive, simpler queries |
| **1536** | 68.17 | ~120 MB | Balanced, most users |
| **3072** | 68.16 | ~240 MB | Business email, nuanced search |

::: tip Quality vs Dimensions
MTEB benchmark scores are nearly identical across dimensions (67.99 - 68.17). The main tradeoff is **storage size**, not quality. Choose based on your storage constraints and query complexity.
:::

### When to Use Each

**768 dimensions**:
- ✅ Personal email with simple queries
- ✅ Storage-constrained environments
- ✅ Faster index builds
- ❌ No quality difference for most use cases

**1536 dimensions**:
- ✅ General purpose, good balance
- ✅ Mixed personal and work email
- ✅ Most common choice

**3072 dimensions** (Recommended):
- ✅ Business email with complex threads
- ✅ Maximum semantic information retained
- ✅ Future-proof for advanced queries
- ❌ 4x storage vs 768

## Migration Guide

### Changing Embedding Dimensions

If you need to change dimensions after initial sync (e.g., upgrading from 768 to 3072):

```bash
# 1. Stop the engine
docker compose stop engine

# 2. Connect to PostgreSQL and drop embeddings table
docker compose exec postgres psql -U secretary -d secretary -c "DROP TABLE IF EXISTS email_embeddings;"

# 3. Update config.yaml with new dimensions
# dimensions: 3072

# 4. Restart engine - table recreates automatically
docker compose up -d engine
```

::: warning Re-embedding Required
This will re-embed ALL emails from scratch. On Tier 1, 25k emails takes ~17 minutes. On free tier, ~25 days.
:::

### Switching Providers

When switching providers (e.g., Cohere → Gemini), you must re-embed if dimensions differ:

| From | To | Re-embed? |
|------|----|-----------|
| Cohere 1536d | Gemini 1536d | No (same dimensions) |
| Cohere 1536d | Gemini 3072d | Yes |
| OpenAI 1536d | Gemini 1536d | Yes (different model = different vectors) |

::: tip Same Dimensions, Different Models
Even with matching dimensions, different models produce incompatible vectors. Always re-embed when changing models.
:::

## Choosing a Provider

### Decision Matrix

| Scenario | Recommended Provider | Why |
|----------|---------------------|-----|
| **Initial sync (large mailbox)** | Gemini Paid (Tier 1+) | Unlimited daily requests, fast sync |
| **Maintenance only** | Gemini Free | 1,000 RPD sufficient for daily new emails |
| **Cost-sensitive + small mailbox** | Gemini Free | Free, but 25+ days for 25k emails |
| **Need fallback resilience** | Cohere + Gemini Free | Combine free tiers |
| **Privacy-first / air-gapped** | Ollama (local) | No API calls, your hardware |

### Gemini Rate Limits (AI Studio)

::: warning Per-Text Rate Limiting
Each text in a batch request counts as **one request** toward your rate limit. `batch_size` only reduces HTTP overhead, not API quota usage.
:::

| Tier | RPM | RPD | TPM | Best For |
|------|-----|-----|-----|----------|
| **Free** | 100 | 1,000 | 30,000 | Maintenance (new emails only) |
| **Tier 1** ($0) | 1,500 | Unlimited | 1,000,000 | Initial sync, production |
| **Tier 2+** | 4,000+ | Unlimited | 4,000,000+ | High-volume production |

**Initial sync time estimates (25,000 emails):**
- Free tier: ~25 days (1,000 RPD limit)
- Tier 1: ~17 minutes (1,500 RPM)

::: tip Recommended Strategy
Use **Tier 1 (paid)** for initial sync to embed your entire mailbox quickly, then optionally switch to **Free tier** for ongoing maintenance (typically <100 new emails/day).
:::

### All Providers Reference

| Provider | Model | Dimensions | Rate Limits | Cost |
|----------|-------|------------|-------------|------|
| **Gemini Free** | `text-embedding-004` | 768-3072 | 100 RPM, 1k RPD | Free |
| **Gemini Tier 1** | `text-embedding-004` | 768-3072 | 1.5k RPM, unlimited | Pay-as-you-go |
| **Cohere Trial** | `embed-v4.0` | 256-1536 | 1k calls/month | Free |
| **Cohere Prod** | `embed-v4.0` | 256-1536 | 10k calls/min | $0.10/1M tokens |
| **OpenAI** | `text-embedding-3-small` | 512-1536 | Varies by tier | $0.02/1M tokens |
| **OpenAI** | `text-embedding-3-large` | 256-3072 | Varies by tier | $0.13/1M tokens |
| **Ollama** | `nomic-embed-text` | 768 | Your hardware | Free (local) |

## Quick Start (Gemini Recommended)

```yaml
embeddings:
  enabled: true
  provider: gemini
  gemini_api_key: ${GEMINI_API_KEY}
  gemini_model: text-embedding-004
  dimensions: 3072
  batch_size: 100
  task_type: RETRIEVAL_DOCUMENT
```

Get your API key at [Google AI Studio](https://aistudio.google.com/apikey). Enable billing for Tier 1 to unlock 1,500 RPM and unlimited daily requests.

## Recommended Configurations

Copy-paste configs optimized for each tier. These settings are tuned to **maximize throughput while staying within rate limits**.

### Gemini Paid Tier 1+ (Recommended for Initial Sync)

**Limits**: 1,500 RPM, unlimited daily, 1M TPM

```yaml
embeddings:
  enabled: true
  provider: gemini
  gemini_api_key: ${GEMINI_API_KEY}
  gemini_model: text-embedding-004
  dimensions: 3072        # Best quality for business email
  batch_size: 100         # Reduces HTTP overhead (rate limit is per-text)
  task_type: RETRIEVAL_DOCUMENT
```

**What these settings mean:**
- `dimensions: 3072` → Maximum semantic nuance
- `batch_size: 100` → Fewer HTTP calls (but each text still counts as 1 request)
- All vectors are L2-normalized for inner product search
- **Initial sync of 25k emails**: ~17 minutes

### Gemini Free Tier (Maintenance Only)

**Limits**: 100 RPM, 1,000 RPD, 30k TPM

```yaml
embeddings:
  enabled: true
  provider: gemini
  gemini_api_key: ${GEMINI_API_KEY}
  gemini_model: text-embedding-004
  dimensions: 3072        # All dimensions available on free tier
  batch_size: 100
  task_type: RETRIEVAL_DOCUMENT
```

::: danger Daily Request Limit
With 1,000 requests/day on free tier, you can only embed **1,000 emails/day** (each text = 1 request, regardless of batch_size). For initial sync of 25k emails, this takes **~25 days**.

**Recommendation**: Use Tier 1 (paid) for initial sync, then switch to free for maintenance.
:::

### Cohere Free Tier (Trial Key)

Combine free tiers for resilience. When Cohere hits rate limit, automatically switch to Gemini:

```yaml
embeddings:
  enabled: true
  provider: cohere
  api_key: ${COHERE_API_KEY}
  model: embed-v4.0
  dimensions: 768         # Must match across providers!
  batch_size: 80
  input_type: search_document
  truncate: END
  
  fallback_provider: gemini
  gemini_api_key: ${GEMINI_API_KEY}
  gemini_model: text-embedding-004
  task_type: RETRIEVAL_DOCUMENT
```

::: warning Dimension Matching
When using fallback, both providers MUST produce the same dimensions. Configure both to 768, 1536, or 3072.
:::

**Why this works:**
- Cohere trial: 1,000 calls/month → 80,000 emails
- Gemini free: 1,000 calls/day → 20,000 emails/day
- Combined: Handle bursts and large initial syncs
- 60-second cooldown between provider switches

### Local Models (Ollama)

**Limits**: Your hardware

```yaml
embeddings:
  enabled: true
  provider: openai_compat
  endpoint: http://localhost:11434/v1
  model: nomic-embed-text
  api_key: ""             # Not needed for local
  dimensions: 768
  batch_size: 50          # Depends on GPU memory
```

**Tuning for your hardware:**
- **8GB VRAM**: `batch_size: 20-30`
- **16GB VRAM**: `batch_size: 50-100`
- **24GB+ VRAM**: `batch_size: 100-200`

## Setup Guide

### 1. Enable PostgreSQL with pgvector

```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: secretary
      POSTGRES_USER: secretary
      POSTGRES_PASSWORD: secretarypass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
```

### 2. Configure Embeddings

```yaml
# config.yaml
database:
  backend: postgres
  postgres:
    host: postgres
    port: 5432
    database: secretary
    user: secretary
    password: secretarypass
    
  embeddings:
    enabled: true
    provider: gemini
    gemini_api_key: ${GEMINI_API_KEY}
    gemini_model: text-embedding-004
    dimensions: 3072
    batch_size: 100
    task_type: RETRIEVAL_DOCUMENT
```

### 3. Start the Server

```bash
docker compose up -d
```

Embeddings are generated automatically during email sync.

## Providers

### Cohere (Recommended)

Native SDK with optimized retrieval via `input_type` parameter.

```yaml
embeddings:
  enabled: true
  provider: cohere
  model: embed-v4.0
  api_key: ${COHERE_API_KEY}
  input_type: search_document
  dimensions: 1536
  batch_size: 80
  truncate: END
```

| Option | Default | Description |
|--------|---------|-------------|
| `provider` | `openai_compat` | Set to `cohere` for native SDK |
| `model` | - | `embed-v4.0` recommended |
| `input_type` | `search_document` | Used for indexing; auto-switches to `search_query` for searches |
| `batch_size` | `96` | Max texts per API call (Cohere limit: 96) |
| `truncate` | `END` | Server-side truncation: `NONE`, `START`, `END` |

**Rate Limits (Trial Key)**:
- 100,000 tokens per minute
- 1,000 API calls per month
- Built-in rate limiting with exponential backoff

**Rate Limits (Production Key)**:
- 2,000 inputs per minute
- No monthly call limit

::: tip Automatic Query Optimization
The system automatically uses `input_type: search_query` when searching, improving retrieval accuracy. You only configure `search_document` for indexing.
:::

### Google Gemini

Native SDK with `task_type` parameter for optimized retrieval.

```yaml
embeddings:
  enabled: true
  provider: gemini
  gemini_api_key: ${GEMINI_API_KEY}
  gemini_model: text-embedding-004
  task_type: RETRIEVAL_DOCUMENT
  dimensions: 3072
  batch_size: 100
```

| Option | Default | Description |
|--------|---------|-------------|
| `provider` | - | Set to `gemini` for native SDK |
| `gemini_api_key` | `${GEMINI_API_KEY}` | Google AI Studio API key |
| `gemini_model` | `text-embedding-004` | Recommended model |
| `task_type` | `RETRIEVAL_DOCUMENT` | For indexing; auto-switches to `RETRIEVAL_QUERY` for searches |
| `dimensions` | `3072` | 768, 1536, or 3072 (all available on all tiers) |
| `batch_size` | `100` | Texts per HTTP call (rate limit is per-text, not per-call) |

**Available Task Types:**
| TaskType | Use Case |
|----------|----------|
| `RETRIEVAL_DOCUMENT` | Indexing emails (default) |
| `RETRIEVAL_QUERY` | Search queries (auto-switched) |
| `SEMANTIC_SIMILARITY` | Comparing text similarity |
| `CLASSIFICATION` | Categorization tasks |
| `CLUSTERING` | Grouping similar content |
| `QUESTION_ANSWERING` | Q&A retrieval |
| `FACT_VERIFICATION` | Fact-checking |
| `CODE_RETRIEVAL_QUERY` | Code search |

::: tip TaskType Affects Embeddings
The same text produces **different vectors** with different task types. The system automatically uses `RETRIEVAL_DOCUMENT` when indexing and `RETRIEVAL_QUERY` when searching for optimal retrieval accuracy.
:::

::: warning Vector Normalization
All vectors are L2-normalized before storage, enabling fast inner product search. This is handled automatically by the client.
:::

### Provider Fallback

Configure automatic failover when primary provider hits rate limits:

```yaml
embeddings:
  enabled: true
  provider: cohere
  api_key: ${COHERE_API_KEY}
  model: embed-v4.0
  fallback_provider: gemini
  gemini_api_key: ${GEMINI_API_KEY}
  gemini_model: gemini-embedding-001
  dimensions: 768
```

When Cohere returns 429 (rate limit), the system automatically switches to Gemini with a 60-second cooldown before retrying Cohere.

### OpenAI

```yaml
embeddings:
  enabled: true
  provider: openai_compat
  endpoint: https://api.openai.com/v1
  model: text-embedding-3-small
  api_key: ${OPENAI_API_KEY}
  dimensions: 1536
  batch_size: 100
```

### Azure OpenAI

```yaml
embeddings:
  enabled: true
  provider: openai_compat
  endpoint: https://your-resource.openai.azure.com/openai/deployments/your-deployment
  model: text-embedding-3-small
  api_key: ${AZURE_OPENAI_KEY}
  dimensions: 1536
```

### Local Models (Ollama)

```yaml
embeddings:
  enabled: true
  provider: openai_compat
  endpoint: http://ollama:11434/api
  model: nomic-embed-text
  api_key: ""
  dimensions: 768
```

### LiteLLM Proxy

Route through LiteLLM for unified API access:

```yaml
embeddings:
  enabled: true
  provider: openai_compat
  endpoint: http://litellm:4000/v1
  model: text-embedding-3-small
  api_key: ${LITELLM_API_KEY}
  dimensions: 1536
```

## Configuration Reference

### Full Configuration

```yaml
database:
  backend: postgres
  
  postgres:
    host: localhost
    port: 5432
    database: secretary
    user: secretary
    password: secretarypass
    ssl_mode: disable        # disable, require, verify-ca, verify-full
    
  embeddings:
    enabled: true
    provider: gemini         # gemini | cohere | openai_compat
    fallback_provider: ""    # Optional: auto-failover on rate limit
    endpoint: ""             # Required for openai_compat
    model: ""                # Model name (provider-specific)
    api_key: ""              # API key for openai_compat/cohere
    dimensions: 3072         # Must match model output
    batch_size: 100          # Texts per HTTP call
    input_type: search_document  # Cohere: search_document | search_query
    truncate: END                # Cohere: NONE | START | END
    gemini_api_key: ""           # For gemini provider or fallback
    gemini_model: text-embedding-004
    task_type: RETRIEVAL_DOCUMENT  # Gemini task type
```

### Environment Variables

Override config with environment variables:

```bash
# Provider selection
EMBEDDINGS_PROVIDER=cohere

# API configuration
EMBEDDINGS_API_KEY=your-key
EMBEDDINGS_API_BASE=https://api.openai.com/v1
EMBEDDINGS_MODEL=text-embedding-3-small

# For Cohere specifically
COHERE_API_KEY=your-cohere-key

# For Gemini specifically
GEMINI_API_KEY=your-gemini-key
```

## MCP Tools

### semantic_search_emails

Search emails by meaning:

```json
{
  "tool": "semantic_search_emails",
  "arguments": {
    "query": "budget concerns for Q4",
    "limit": 20,
    "similarity_threshold": 0.7
  }
}
```

**Parameters**:
- `query` (required): Natural language search query
- `limit` (optional): Max results, default 20
- `similarity_threshold` (optional): Min similarity score 0.0-1.0, default 0.5

**Response**:
```json
{
  "results": [
    {
      "uid": 12345,
      "subject": "Q4 Spending Review",
      "from": "cfo@company.com",
      "date": "2026-01-08T10:30:00Z",
      "similarity": 0.89,
      "snippet": "We need to address the cost overruns..."
    }
  ]
}
```

### find_related_emails

Find emails similar to a reference email:

```json
{
  "tool": "find_related_emails",
  "arguments": {
    "uid": 12345,
    "limit": 10
  }
}
```

### get_embedding_status

Check embeddings system health:

```json
{
  "tool": "get_embedding_status"
}
```

**Response**:
```json
{
  "enabled": true,
  "provider": "cohere",
  "model": "embed-v4.0",
  "total_emails": 24183,
  "emails_with_embeddings": 24183,
  "coverage": "100%"
}
```

## Web UI Integration

The web interface includes semantic search:

1. Navigate to `/search`
2. Toggle "Semantic" switch
3. Enter natural language query
4. Results ranked by similarity

Requires environment variables:
```bash
EMBEDDINGS_PROVIDER=cohere
EMBEDDINGS_API_KEY=your-key
EMBEDDINGS_MODEL=embed-v4.0
```

## Database Schema

Embeddings are stored in PostgreSQL with pgvector using HNSW index for fast inner product search:

```sql
CREATE TABLE email_embeddings (
    id SERIAL PRIMARY KEY,
    email_uid INTEGER NOT NULL,
    folder VARCHAR(255) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding vector(3072),  -- Matches configured dimensions
    model VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(email_uid, folder)
);

-- HNSW index with inner product ops (faster for normalized vectors)
CREATE INDEX ON email_embeddings 
    USING hnsw (embedding vector_ip_ops)
    WITH (m = 16, ef_construction = 64);
```

::: tip Why Inner Product?
All vectors are L2-normalized before storage, making inner product (`<#>`) mathematically equivalent to cosine similarity but faster to compute.
:::

## Performance Tuning

### Index Tuning

For large mailboxes (>100k emails), tune the HNSW index:

```sql
-- Adjust m (connections per node) and ef_construction (build quality)
CREATE INDEX ON email_embeddings 
    USING hnsw (embedding vector_ip_ops)
    WITH (m = 32, ef_construction = 128);  -- Higher = better quality, slower build

-- Set ef for query time (higher = more accurate, slower)
SET hnsw.ef_search = 100;
```

### Incremental Sync

Only new emails are embedded during sync. The `content_hash` prevents re-embedding unchanged emails:

```
First sync:  24,183 emails → ~30 minutes (rate limited)
Daily sync:  ~50 new emails → ~5 seconds
```

## Troubleshooting

### Rate Limit Errors

```
ERROR - Cohere embeddings API error: 429 rate limit exceeded
```

**Solution**: Reduce batch size and max_chars:
```yaml
batch_size: 50
max_chars: 20000
```

### Dimension Mismatch

```
ERROR - expected 1536 dimensions, got 768
```

**Solution**: Ensure `dimensions` matches your model:
- `text-embedding-3-small`: 1536
- `text-embedding-3-large`: 3072
- `nomic-embed-text`: 768
- `embed-v4.0`: 1536 (default)

### pgvector Not Found

```
ERROR - extension "vector" is not available
```

**Solution**: Use the pgvector Docker image:
```yaml
postgres:
  image: pgvector/pgvector:pg16  # NOT postgres:16
```

### Embeddings Not Generated

Check status:
```json
{"tool": "get_embedding_status"}
```

Common causes:
- `enabled: false` in config
- Missing API key
- PostgreSQL not connected
- Sync not completed

## Cost Estimation

### Cohere

| Tier | Price | Notes |
|------|-------|-------|
| Trial | Free | 100k tokens/min, 1k calls/month |
| Production | $0.10/1M tokens | 2k inputs/min |

**Example**: 25,000 emails × 500 avg tokens = 12.5M tokens = **$1.25** one-time, then pennies for daily sync.

### OpenAI

| Model | Price |
|-------|-------|
| text-embedding-3-small | $0.02/1M tokens |
| text-embedding-3-large | $0.13/1M tokens |

**Example**: 25,000 emails × 500 avg tokens = 12.5M tokens = **$0.25** (small) one-time.

## Next Steps

- [Web UI Guide](/webserver/) - Use semantic search in the browser
- [Agent Patterns](/guide/agents) - Build AI workflows with semantic search
- [MCP Tools Reference](/tools/) - Complete tool documentation
