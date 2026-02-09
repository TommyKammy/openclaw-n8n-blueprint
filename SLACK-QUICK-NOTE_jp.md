# Clawアプリ利用メモ（Slack向け）

Slackでは **Clawアプリのみ** を使ってください。Codexアプリは廃止運用です。

## よく使うコマンド

- 現在モデル確認: `/status`
- モデル一覧/状態: `/model status`
- Codexへ切替: `/model codex`
- 既定(Kimi)へ戻す: `/model k2p5`
- 新しいセッション開始: `/new`

## 注意点

- コマンドは単独メッセージで送ってください。
- 例: 先に `/model codex` を送ってから通常の質問を送る。
- OpenAIのクォータ超過時は `/model k2p5` で戻してください。
