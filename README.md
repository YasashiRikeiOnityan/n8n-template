# n8n-template

ビルド、デプロイには `samconfig.toml` が必要です。

### ビルド

```bash
sam build --template-file ./template/stack-n8n-infrastructure.yaml --config-env dev
```

### デプロイ

```bash
sam deploy --config-env dev --no-confirm-changeset --no-fail-on-empty-changeset
```