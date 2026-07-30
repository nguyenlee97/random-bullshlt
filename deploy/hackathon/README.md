# Hackathon VPS deployment

This deployment is a fully isolated Compose project for `zah-4.123c.vn`.
MongoDB, Qdrant, uploaded creatives, model caches, and future Zalo tokens use
dedicated named volumes and are never exposed on a public port.

The Agent behavior flags mirror production. The only deliberate provider
exception is Langfuse: do not place Langfuse keys in any hackathon env file.
Production URLs are replaced by environment-specific local routes for browser,
publisher, screenshot, report, and Zalo links.

## Runtime surfaces

- `/` and `/agent` - public UI and agent
- `/backend/`, `/api/`, `/uploads/` - backend API and creative assets
- `/adspilot/`, `/analytics/` - operator dashboards
- `/znews/`, `/baomoi/`, `/zingmp3/`, `/smoney/`, `/dicungcon/`, `/zagoo/`
  - placement test sites

## Bootstrap

Create `stack.env`, `agent.env`, and `backend.env` beside their example files.
Keep them mode `0600`; do not commit them.

```sh
docker compose \
  --env-file deploy/hackathon/stack.env \
  -f docker-compose.hackathon.yml \
  up -d --build

docker compose \
  --env-file deploy/hackathon/stack.env \
  -f docker-compose.hackathon.yml \
  exec agent python scripts/build_rag_index.py --force
```

The Compose agent health check intentionally uses `/health` during bootstrap.
The final acceptance check must use `/ready` after the RAG index build.

## Zalo activation order

Leave all five Zalo switches disabled until the independent stack is healthy.
Then configure and verify the HTTPS callback and webhook, obtain OA tokens,
confirm signature validation and replay safety, and only then enable inbound
processing followed by outbound delivery.
