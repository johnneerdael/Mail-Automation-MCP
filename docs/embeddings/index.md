# Embeddings & Semantic Search

Gmail Secretary supports AI-powered semantic search using vector embeddings. Instead of keyword matching, find emails by meaning—search "budget concerns" and find emails about "cost overruns" or "spending issues".

## Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Email Text    │────▶│ Embeddings API   │────▶│ Vector (1536d)  │
│ "Meeting moved" │     │ (Cohere/Gemini)  │     │ [0.12, -0.34,…] │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Search Query   │────▶│ Embeddings API   │────▶│   Similarity    │
│ "schedule change"│    │                  │     │     Search      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Requirements

- **PostgreSQL** with **pgvector** extension
- **Embeddings API** (Cohere, Gemini, OpenAI, or compatible)

## Model Defaults Reference

Use this table to configure optimal settings for your provider:

| Provider | Model | Dimensions | Batch Size | Max Chars | Rate Limits |
|----------|-------|------------|------------|-----------|-------------|
| **Cohere (trial)** | `embed-v4.0` | 1536 | 80 | 40000 | 100k tok/min, 1k calls/mo |
| **Cohere (prod)** | `embed-v4.0` | 1536 | 96 | 500000 | 2k inputs/min |
| **Gemini (free)** | `gemini-embedding-001` | 768 | 100 | 8000 | 100 RPM, 30k TPM, 1k RPD |
| **Gemini (paid)** | `text-embedding-004` | 768-3072 | 100 | 8000 | 3k RPM, 1M TPM |
| **OpenAI** | `text-embedding-3-small` | 1536 | 100 | 32000 | Varies by tier |
| **OpenAI** | `text-embedding-3-large` | 3072 | 100 | 32000 | Varies by tier |

::: tip Choosing Dimensions
- **768**: Fastest, good for most use cases
- **1536**: Balanced quality/performance (recommended)
- **3072**: Highest quality, more storage, slower searches
:::

## Quick Start

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
    provider: cohere          # or openai_compat
    model: embed-v4.0
    api_key: ${COHERE_API_KEY}
    dimensions: 1536
    batch_size: 80
    max_chars: 40000
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
  max_chars: 40000
  truncate: END
```

| Option | Default | Description |
|--------|---------|-------------|
| `provider` | `openai_compat` | Set to `cohere` for native SDK |
| `model` | - | `embed-v4.0` recommended (1.28M token context) |
| `input_type` | `search_document` | Used for indexing; auto-switches to `search_query` for searches |
| `batch_size` | `96` | Max texts per API call (Cohere limit: 96) |
| `max_chars` | `500000` | Client-side truncation before API call |
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

Native SDK with `task_type` parameter for optimized retrieval. Supports Matryoshka Representation Learning (MRL) for flexible dimensions.

```yaml
embeddings:
  enabled: true
  provider: gemini
  gemini_api_key: ${GEMINI_API_KEY}
  gemini_model: gemini-embedding-001
  task_type: RETRIEVAL_DOCUMENT
  dimensions: 768
  batch_size: 100
  max_chars: 8000
```

| Option | Default | Description |
|--------|---------|-------------|
| `provider` | - | Set to `gemini` for native SDK |
| `gemini_api_key` | `${GEMINI_API_KEY}` | Google AI API key |
| `gemini_model` | `gemini-embedding-001` | Or `text-embedding-004` |
| `task_type` | `RETRIEVAL_DOCUMENT` | For indexing; auto-switches to `RETRIEVAL_QUERY` for searches |
| `dimensions` | `768` | 768, 1536, or 3072 |
| `batch_size` | `100` | Max texts per API call |
| `max_chars` | `8000` | Gemini max input is ~8k chars |

**Rate Limits (Free Tier)**:
- 100 requests per minute (RPM)
- 30,000 tokens per minute (TPM)
- 1,000 requests per day (RPD)

**Rate Limits (Pay-as-you-go)**:
- 3,000 RPM
- 1,000,000 TPM
- Unlimited RPD

::: warning Dimension Normalization
Gemini's 3072-dimension output is already L2-normalized. For 768 or 1536 dimensions, the system automatically normalizes vectors for accurate cosine similarity.
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
    provider: cohere         # cohere | gemini | openai_compat
    fallback_provider: gemini  # Optional: auto-failover on rate limit
    endpoint: ""             # Required for openai_compat
    model: embed-v4.0
    api_key: ""
    dimensions: 1536
    batch_size: 80
    max_chars: 40000
    input_type: search_document  # Cohere: search_document | search_query
    truncate: END                # Cohere: NONE | START | END
    gemini_api_key: ""           # For gemini provider or fallback
    gemini_model: gemini-embedding-001
    task_type: RETRIEVAL_DOCUMENT  # Gemini: RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY
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

Embeddings are stored in PostgreSQL with pgvector:

```sql
CREATE TABLE email_embeddings (
    id SERIAL PRIMARY KEY,
    email_uid INTEGER NOT NULL,
    folder VARCHAR(255) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding vector(1536),
    model VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(email_uid, folder)
);

CREATE INDEX ON email_embeddings 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

## Performance Tuning

### Batch Size

Larger batches = fewer API calls but more memory:

```yaml
batch_size: 80    # Good for Cohere trial (rate limited)
batch_size: 100   # Good for OpenAI / production Cohere
batch_size: 200   # Good for local models
```

### Index Tuning

For large mailboxes (>100k emails), tune the IVFFlat index:

```sql
-- More lists = faster search, slower index build
CREATE INDEX ON email_embeddings 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 1000);

-- Set probes for query time (higher = more accurate, slower)
SET ivfflat.probes = 10;
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
