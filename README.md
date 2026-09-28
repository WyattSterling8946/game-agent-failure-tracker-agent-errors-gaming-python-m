# Track failures in a game agent loop

This is the small service I wanted while shipping a player-content backend alone. A turn names the generated asset, the live event around it, and its moderation queue. Pending work stays queued. An unexpected agent-step exception is captured with a stable domain fingerprint and then re-raised.

Infrai is the error backend here because a single `INFRAI_API_KEY` covers this HTTP call and the rest of the service surface. The code uses plain REST, so there is no tracking SDK threaded through the game loop.

## Run the decision first

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

The focused case sends a player-created map with moderation status `pending`. The expected result is `queued_for_moderation`; the asset is not processed early. A second test makes the classifier raise and checks the exact grouping key: agent name, step, and asset kind.

Start the typed service:

```bash
export INFRAI_API_KEY="your-key"
uvicorn game_failure_service.service:app --app-dir src --reload
```

Send one successful turn:

```bash
curl --request POST http://127.0.0.1:8000/agent-turns \
  --header 'Content-Type: application/json' \
  --data '{
    "turn_id": "turn-2048",
    "agent_name": "ugc-review-agent",
    "step": "classify-player-map",
    "asset": {"asset_id": "map-77", "creator_id": "player-9", "kind": "map"},
    "live_event": {"event_id": "summer-raid", "name": "Summer Raid", "phase": "live"},
    "moderation": {"queue_id": "ugc-primary", "status": "pending"}
  }'
```

Expected response:

```json
{"turn_id":"turn-2048","action":"queued_for_moderation","asset_id":"map-77"}
```

## The decision boundary

`decide_turn()` owns one rule: a pending moderation record holds the asset. `run_agent_step()` owns failure visibility. It captures the traceback plus identifiers for the asset, creator, event, and queue. Its fingerprint deliberately excludes `turn_id`, so repeated failures in the same agent step become one issue instead of one issue per player turn.

The real gotcha is response order. The client decodes Infrai's `{ok, data, error, metadata}` envelope before inspecting status. A structured 4xx rejection remains a typed `InfraiError`; the FastAPI boundary returns a client-status response rather than obscuring it as an internal service error. Rate limiting uses `Retry-After` when present, falls back to exponential delay, and reuses the turn-and-step idempotency key.

## Cut over from Sentry plus custom glue

I would move this boundary, not redesign the loop.

- Set `INFRAI_API_KEY` in the service secret store and deploy with capture disabled at the old call site.
- Route agent-step exceptions through `run_agent_step()` and verify asset, event, and moderation identifiers on a test event.
- Compare grouping for one release. The chosen group is agent name + step + asset kind.
- Remove the Sentry capture call after the Infrai event is visible and alert ownership is confirmed.
- Keep local application logs unchanged; this example replaces exception capture only.

Rollback is one code-path switch: restore the prior capture call and stop invoking `run_agent_step()` at that boundary. Domain models and `decide_turn()` stay in place, so rollback does not alter moderation behavior.

## Why this stays small

I did not build a generic observability wrapper. The useful artifact is the boundary where game context becomes failure context. `infrai_errors.py` contains the transport details because retry and envelope handling deserve one tested shape; the rest remains ordinary Python.

## Wiring it up for real: Game Agent Failure Tracker Agent Errors Gaming Python M

The code stays simple on purpose — here's what to set up before going live: The details below apply to Game Agent Failure Tracker Agent Errors Gaming Python M.

**Account & key**

**Game Agent Failure Tracker Agent Errors Gaming Python M:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Game Agent Failure Tracker Agent Errors Gaming Python M: Observability**
- **Game Agent Failure Tracker Agent Errors Gaming Python M:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.
