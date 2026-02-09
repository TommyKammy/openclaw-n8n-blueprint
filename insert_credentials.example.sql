-- Example ONLY. Do not put real tokens in git.
--
-- If you must insert credentials into n8n via SQL, prefer using n8n Credentials UI
-- or the public API where possible. At minimum, keep secrets out of your repo.

INSERT INTO credentials_entity (id, name, type, data, "isManaged", "isGlobal", "isResolvable", "resolvableAllowFallback", createdAt, updatedAt)
VALUES (
  'github-cred-001',
  'GitHub API',
  'githubApi',
  '{"githubToken": "REPLACE_ME"}',
  false, false, false, false,
  NOW(), NOW()
)
ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updatedAt = NOW();

INSERT INTO credentials_entity (id, name, type, data, "isManaged", "isGlobal", "isResolvable", "resolvableAllowFallback", createdAt, updatedAt)
VALUES (
  'slack-cred-001',
  'Slack Bot',
  'slackApi',
  '{"accessToken": "REPLACE_ME"}',
  false, false, false, false,
  NOW(), NOW()
)
ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updatedAt = NOW();

INSERT INTO credentials_entity (id, name, type, data, "isManaged", "isGlobal", "isResolvable", "resolvableAllowFallback", createdAt, updatedAt)
VALUES (
  'n8n-cred-001',
  'n8n API',
  'n8nApi',
  '{"apiKey": "REPLACE_ME"}',
  false, false, false, false,
  NOW(), NOW()
)
ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updatedAt = NOW();

INSERT INTO credentials_entity (id, name, type, data, "isManaged", "isGlobal", "isResolvable", "resolvableAllowFallback", createdAt, updatedAt)
VALUES (
  'vercel-cred-001',
  'Vercel Token',
  'vercelApi',
  '{"token": "REPLACE_ME"}',
  false, false, false, false,
  NOW(), NOW()
)
ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updatedAt = NOW();
