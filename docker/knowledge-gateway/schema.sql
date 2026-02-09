-- Step 1: Neon schema for guest knowledge connector v1
-- Requires: CREATE EXTENSION privileges for vector + pgcrypto

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS knowledge_connections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  guest_id text NOT NULL,
  provider text NOT NULL CHECK (provider IN ('google_drive','onedrive')),
  provider_user_id text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','revoked','error')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (guest_id, provider, provider_user_id)
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
  connection_id uuid PRIMARY KEY REFERENCES knowledge_connections(id) ON DELETE CASCADE,
  access_token_enc text NOT NULL,
  refresh_token_enc text NOT NULL,
  token_expiry timestamptz,
  scopes text[] NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id uuid NOT NULL REFERENCES knowledge_connections(id) ON DELETE CASCADE,
  provider_file_id text NOT NULL,
  title text NOT NULL,
  mime_type text,
  source_url text,
  content_hash text,
  provider_updated_at timestamptz,
  indexed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (connection_id, provider_file_id)
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  content text NOT NULL,
  token_count integer NOT NULL DEFAULT 0,
  embedding vector(1536) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS sync_cursors (
  connection_id uuid PRIMARY KEY REFERENCES knowledge_connections(id) ON DELETE CASCADE,
  provider_cursor text,
  last_sync_at timestamptz,
  last_status text,
  last_error text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_access_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id text NOT NULL,
  guest_id text NOT NULL,
  query text NOT NULL,
  source_ids uuid[] NOT NULL DEFAULT '{}',
  result_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_connections_guest ON knowledge_connections(guest_id);
CREATE INDEX IF NOT EXISTS idx_sources_connection ON knowledge_sources(connection_id);
CREATE INDEX IF NOT EXISTS idx_logs_guest_time ON knowledge_access_logs(guest_id, created_at DESC);

-- Vector index (cosine distance)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_cosine
  ON knowledge_chunks
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
