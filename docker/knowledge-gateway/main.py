#!/usr/bin/env python3
"""
Knowledge Gateway Service - Guest Knowledge Connector v1
FastAPI application for OAuth, sync, and retrieval API
"""

import os
import json
import base64
import hashlib
import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import httpx
import asyncpg
from cryptography.fernet import Fernet

# Configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost/knowledge")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "https://knowledge.example.com/oauth/google/callback")
INTERNAL_API_TOKEN = os.environ.get("INTERNAL_API_TOKEN", "")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode())
fernet = Fernet(ENCRYPTION_KEY.encode())

# Database pool
db_pool: Optional[asyncpg.Pool] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection lifecycle"""
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    yield
    await db_pool.close()


app = FastAPI(
    title="Guest Knowledge Connector API",
    version="1.0.0",
    lifespan=lifespan
)


# Pydantic Models
class OAuthStartRequest(BaseModel):
    guest_id: str
    slack_user_id: str
    redirect_hint: Optional[str] = "slack"


class OAuthStartResponse(BaseModel):
    auth_url: str
    state: str


class SearchRequest(BaseModel):
    guest_id: str
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    snippet: str
    source_id: str
    title: str
    source_url: Optional[str]


class SearchResponse(BaseModel):
    answers: List[SearchResult]


class SyncRequest(BaseModel):
    connection_id: str


class DisconnectRequest(BaseModel):
    connection_id: str
    purge_index: bool = False


# Auth dependency
async def verify_token(authorization: Optional[str] = Header(None)):
    if not INTERNAL_API_TOKEN:
        return True
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    if token != INTERNAL_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return True


# OAuth Endpoints
@app.post("/oauth/google/start", response_model=OAuthStartResponse)
async def oauth_google_start(
    req: OAuthStartRequest,
    authorized: bool = Depends(verify_token)
):
    """Generate Google OAuth URL for guest connection"""
    state = secrets.token_urlsafe(32)
    
    # Store state in temporary table/cache for validation
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_states (
                state text PRIMARY KEY,
                guest_id text NOT NULL,
                slack_user_id text NOT NULL,
                redirect_hint text,
                created_at timestamptz DEFAULT now(),
                expires_at timestamptz DEFAULT now() + interval '10 minutes'
            )
            """
        )
        await conn.execute(
            """
            INSERT INTO oauth_states (state, guest_id, slack_user_id, redirect_hint, expires_at)
            VALUES ($1, $2, $3, $4, now() + interval '10 minutes')
            """,
            state, req.guest_id, req.slack_user_id, req.redirect_hint
        )
    
    scopes = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/userinfo.email"
    ]
    
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={' '.join(scopes)}"
        f"&state={state}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    
    return OAuthStartResponse(auth_url=auth_url, state=state)


@app.get("/oauth/google/callback")
async def oauth_google_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None)
):
    """Handle Google OAuth callback"""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    
    # Validate state
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT guest_id, slack_user_id, redirect_hint FROM oauth_states WHERE state = $1 AND expires_at > now()",
            state
        )
        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired state")
        
        await conn.execute("DELETE FROM oauth_states WHERE state = $1", state)
        
        guest_id = row["guest_id"]
        slack_user_id = row["slack_user_id"]
        redirect_hint = row["redirect_hint"]
        
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
            )
            
            if token_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to exchange code for tokens")
            
            tokens = token_resp.json()
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token", "")
            expires_in = tokens.get("expires_in", 3600)
            token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Get user info
            user_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            user_info = user_resp.json()
            provider_user_id = user_info.get("id", "")
            
            # Encrypt tokens
            access_enc = fernet.encrypt(access_token.encode()).decode()
            refresh_enc = fernet.encrypt(refresh_token.encode()).decode()
            
            # Create or update connection
            conn_id = await conn.fetchval(
                """
                INSERT INTO knowledge_connections (guest_id, provider, provider_user_id, status)
                VALUES ($1, 'google_drive', $2, 'active')
                ON CONFLICT (guest_id, provider, provider_user_id)
                DO UPDATE SET status = 'active', updated_at = now()
                RETURNING id
                """,
                guest_id, provider_user_id
            )
            
            # Store tokens
            await conn.execute(
                """
                INSERT INTO oauth_tokens (connection_id, access_token_enc, refresh_token_enc, token_expiry, scopes, updated_at)
                VALUES ($1, $2, $3, $4, $5, now())
                ON CONFLICT (connection_id)
                DO UPDATE SET access_token_enc = $2, refresh_token_enc = $3, token_expiry = $4, scopes = $5, updated_at = now()
                """,
                conn_id, access_enc, refresh_enc, token_expiry, 
                ["https://www.googleapis.com/auth/drive.readonly"]
            )
            
            # Initialize sync cursor
            await conn.execute(
                """
                INSERT INTO sync_cursors (connection_id, last_sync_at, last_status, updated_at)
                VALUES ($1, null, 'pending', now())
                ON CONFLICT (connection_id)
                DO UPDATE SET updated_at = now()
                """,
                conn_id
            )
    
    # Redirect based on hint
    if redirect_hint == "slack":
        return RedirectResponse(url=f"slack://channel?message=Connected+Google+Drive+successfully")
    
    return {"status": "success", "message": "Google Drive connected successfully"}


# Knowledge Search Endpoint
@app.post("/knowledge/search", response_model=SearchResponse)
async def knowledge_search(
    req: SearchRequest,
    authorized: bool = Depends(verify_token)
):
    """Search guest knowledge with vector similarity"""
    # TODO: Integrate with embedding service (OpenAI or local)
    # For now, return simple text search results
    
    async with db_pool.acquire() as conn:
        # Get connection for guest
        conn_row = await conn.fetchrow(
            "SELECT id FROM knowledge_connections WHERE guest_id = $1 AND status = 'active' LIMIT 1",
            req.guest_id
        )
        
        if not conn_row:
            return SearchResponse(answers=[])
        
        connection_id = conn_row["id"]
        
        # Simple text search on chunks (placeholder for vector search)
        # In production, this would use embedding + vector similarity
        chunks = await conn.fetch(
            """
            SELECT kc.id, kc.content, kc.chunk_index, ks.title, ks.source_url, ks.id as source_id
            FROM knowledge_chunks kc
            JOIN knowledge_sources ks ON kc.source_id = ks.id
            WHERE ks.connection_id = $1
            AND kc.content ILIKE $2
            ORDER BY kc.chunk_index
            LIMIT $3
            """,
            connection_id, f"%{req.query}%", req.top_k
        )
        
        results = []
        source_ids = []
        for chunk in chunks:
            results.append(SearchResult(
                snippet=chunk["content"][:500],
                source_id=str(chunk["source_id"]),
                title=chunk["title"],
                source_url=chunk["source_url"]
            ))
            source_ids.append(chunk["source_id"])
        
        # Log access
        request_id = secrets.token_hex(16)
        await conn.execute(
            """
            INSERT INTO knowledge_access_logs (request_id, guest_id, query, source_ids, result_count, created_at)
            VALUES ($1, $2, $3, $4, $5, now())
            """,
            request_id, req.guest_id, req.query, source_ids, len(results)
        )
    
    return SearchResponse(answers=results)


# Sync Endpoint
@app.post("/knowledge/sync/run", status_code=202)
async def knowledge_sync_run(
    req: SyncRequest,
    authorized: bool = Depends(verify_token)
):
    """Trigger sync for a connection"""
    async with db_pool.acquire() as conn:
        # Verify connection exists
        row = await conn.fetchrow(
            "SELECT id, guest_id FROM knowledge_connections WHERE id = $1",
            req.connection_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Update sync cursor to mark as syncing
        await conn.execute(
            """
            UPDATE sync_cursors 
            SET last_status = 'syncing', updated_at = now()
            WHERE connection_id = $1
            """,
            req.connection_id
        )
    
    # Trigger background sync (in production, use Celery/Redis)
    asyncio.create_task(sync_connection(req.connection_id))
    
    return {"status": "accepted", "message": "Sync job queued"}


async def sync_connection(connection_id: str):
    """Background task to sync Google Drive files"""
    try:
        async with db_pool.acquire() as conn:
            # Get tokens
            token_row = await conn.fetchrow(
                """
                SELECT access_token_enc, refresh_token_enc, token_expiry
                FROM oauth_tokens WHERE connection_id = $1
                """,
                connection_id
            )
            
            if not token_row:
                await update_sync_status(connection_id, "error", "No tokens found")
                return
            
            # Decrypt access token
            access_token = fernet.decrypt(token_row["access_token_enc"].encode()).decode()
            
            # Fetch files from Google Drive
            async with httpx.AsyncClient() as client:
                files_resp = await client.get(
                    "https://www.googleapis.com/drive/v3/files",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={
                        "q": "mimeType contains 'text/' or mimeType = 'application/pdf'",
                        "fields": "files(id,name,mimeType,modifiedTime,webViewLink)"
                    }
                )
                
                if files_resp.status_code != 200:
                    await update_sync_status(connection_id, "error", f"Drive API error: {files_resp.status_code}")
                    return
                
                files = files_resp.json().get("files", [])
                
                for file in files:
                    provider_file_id = file["id"]
                    title = file["name"]
                    mime_type = file["mimeType"]
                    source_url = file.get("webViewLink", "")
                    provider_updated_at = file.get("modifiedTime")
                    
                    # Calculate content hash (placeholder)
                    content_hash = hashlib.sha256(provider_file_id.encode()).hexdigest()[:16]
                    
                    # Upsert source
                    source_id = await conn.fetchval(
                        """
                        INSERT INTO knowledge_sources (connection_id, provider_file_id, title, mime_type, source_url, content_hash, provider_updated_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, now())
                        ON CONFLICT (connection_id, provider_file_id)
                        DO UPDATE SET title = $3, mime_type = $4, source_url = $5, content_hash = $6, provider_updated_at = $7, updated_at = now()
                        RETURNING id
                        """,
                        connection_id, provider_file_id, title, mime_type, source_url, content_hash, provider_updated_at
                    )
                    
                    # TODO: Fetch file content and create chunks with embeddings
                    # For now, create a placeholder chunk
                    await conn.execute(
                        """
                        INSERT INTO knowledge_chunks (source_id, chunk_index, content, token_count, embedding, created_at)
                        VALUES ($1, 0, $2, 0, (SELECT array_agg(random())::vector(1536) FROM generate_series(1, 1536)), now())
                        ON CONFLICT (source_id, chunk_index) DO NOTHING
                        """,
                        source_id, f"Placeholder content for {title}"
                    )
            
            await update_sync_status(connection_id, "success", None)
            
    except Exception as e:
        await update_sync_status(connection_id, "error", str(e))


async def update_sync_status(connection_id: str, status: str, error: Optional[str]):
    """Update sync cursor status"""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sync_cursors 
            SET last_sync_at = CASE WHEN $2 = 'success' THEN now() ELSE last_sync_at END,
                last_status = $2,
                last_error = $3,
                updated_at = now()
            WHERE connection_id = $1
            """,
            connection_id, status, error
        )


# Disconnect Endpoint
@app.post("/knowledge/disconnect")
async def knowledge_disconnect(
    req: DisconnectRequest,
    authorized: bool = Depends(verify_token)
):
    """Disconnect provider and optionally purge data"""
    async with db_pool.acquire() as conn:
        # Verify connection exists
        row = await conn.fetchrow(
            "SELECT id, guest_id FROM knowledge_connections WHERE id = $1",
            req.connection_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        if req.purge_index:
            # Delete all related data
            await conn.execute(
                "DELETE FROM knowledge_chunks WHERE source_id IN (SELECT id FROM knowledge_sources WHERE connection_id = $1)",
                req.connection_id
            )
            await conn.execute("DELETE FROM knowledge_sources WHERE connection_id = $1", req.connection_id)
            await conn.execute("DELETE FROM sync_cursors WHERE connection_id = $1", req.connection_id)
            await conn.execute("DELETE FROM oauth_tokens WHERE connection_id = $1", req.connection_id)
            await conn.execute("DELETE FROM knowledge_connections WHERE id = $1", req.connection_id)
        else:
            # Just mark as revoked
            await conn.execute(
                "UPDATE knowledge_connections SET status = 'revoked', updated_at = now() WHERE id = $1",
                req.connection_id
            )
    
    return {"status": "disconnected", "purged": req.purge_index}


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
