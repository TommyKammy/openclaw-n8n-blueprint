# OpenClaw + n8n エンタープライズ構成テンプレート

このリポジトリは、新しいサーバーに以下を再現性高く構築するためのテンプレートです。

- n8n + PostgreSQL
- OpenClaw Gateway
- OpenClaw -> n8n 同期ワーカー
- Slack / Microsoft Teams ゲストの n8n 自動プロビジョニング
- Nginx + TLS 終端

## 構成概要

- 外部公開は `nginx` のみ（`80/443`）
- `n8n` は内部ネットワークで稼働
- `openclaw` は Gateway/Hook を内部で提供
- `slack_n8n_provisioner.py` が Slack/Teams イベントを処理
- `openclaw_n8n_sync_worker.py` が OpenClaw のジョブを n8n ワークフローへ同期

## 主な機能

- 単一のプロビジョナーで Slack / Teams のゲストユーザーを n8n に自動登録
- OpenClaw -> n8n 同期時に許可リストと所有者割り当てを適用
- チャットごとのユーザー分離メモリ（セッション分離）
- プロビジョナーと同期ワーカーのヘルスチェック/メトリクス公開
- ハードニング済みの本番向け compose プロファイル

## チャット履歴の分離について

- Slack と Teams のチャット履歴は、ユーザー単位で分離される設計です。
- OpenClaw の DM セッションは `per-sender` + `per-channel-peer` で分離されます。
- 同期ワーカーが生成するワークフローにも、ユーザー単位の `sessionKey` とメモリ分離ポリシーを埋め込みます。
- これにより、別ユーザー間で会話メモリが混在・参照されるリスクをデフォルトで抑止します。

## 主なルーティング

- `/` -> n8n UI/API
- `/webhook/*` -> n8n Webhook（公開）
- `/openclaw-hooks/*` -> OpenClaw Hook
- `/slack/events` -> Slack Events API
- `/teams/events` -> Microsoft Graph 通知
- `/slack/provisioner/healthz` -> プロビジョナー健康チェック
- `/sync-worker/healthz` -> 同期ワーカー健康チェック
- `/sync-worker/metrics` -> 同期メトリクス（Prometheus形式）

## 主要ファイル

- `docker-compose.yml`（標準）
- `docker-compose.prod.yml`（ハードニング版）
- `docker/nginx/n8n.conf`
- `docker/openclaw/`
- `docker/provisioner/`
- `docker/sync/`
- `slack_n8n_provisioner.py`
- `scripts/teams/`（Graph サブスクリプション作成/更新）
- `SETUP-GUIDE.md`（詳細手順）

## クイックスタート

1. 環境変数を作成

```bash
cp .env.example .env
```

2. TLS証明書を配置

- `certs/fullchain.pem`
- `certs/privkey.pem`

3. 起動（標準）

```bash
docker compose up -d --build
```

4. 起動（ハードニング版）

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

5. 動作確認

```bash
docker compose ps
curl -I https://<domain>/slack/provisioner/healthz
curl -I https://<domain>/sync-worker/healthz
curl -s https://<domain>/sync-worker/metrics
```

## 必須設定（.env）

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `N8N_HOST`, `WEBHOOK_URL`, `N8N_ENCRYPTION_KEY`
- `OPENCLAW_GATEWAY_TOKEN`
- `OPENCLAW_HOOK_URL`, `OPENCLAW_HOOK_TOKEN`
- `SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN`
- `N8N_API_KEY`, `N8N_BASE_URL`
- `SYNC_ALLOWED_SLACK_USER_IDS`, `SYNC_ALLOWED_EMAILS`

Teams連携（任意）:

- `TEAMS_ENABLED=true`
- `TEAMS_CLIENT_STATE=<secret>`
- `ALLOWED_TEAMS_TENANT_IDS=<tenant-id>`
- `TEAMS_REQUIRE_GUEST_ONLY=true`

## Teams Graph サブスクリプション

作成:

```bash
MODE=create ./scripts/teams/create_or_renew_graph_subscription.sh
```

更新（自動化テンプレートあり）:

- `scripts/teams/systemd/teams-graph-subscription-renew.service`
- `scripts/teams/systemd/teams-graph-subscription-renew.timer`

詳細は `scripts/teams/README.md` を参照してください。

## セキュリティ注意点

- 秘密情報（トークン/鍵）を git に含めない
- 本番導入前にすべての秘密情報をローテーション
- 公開ポートは nginx のみ
- Docker socket マウントは高権限扱いとして管理
