from __future__ import annotations

import pytest

from game_failure_service.game_agent_loop import AgentTurn, decide_turn, run_agent_step


def make_turn(status: str = "pending") -> AgentTurn:
    return AgentTurn.model_validate(
        {
            "turn_id": "turn-2048",
            "agent_name": "ugc-review-agent",
            "step": "classify-player-map",
            "asset": {"asset_id": "map-77", "creator_id": "player-9", "kind": "map"},
            "live_event": {"event_id": "summer-raid", "name": "Summer Raid", "phase": "live"},
            "moderation": {"queue_id": "ugc-primary", "status": status},
        }
    )


def test_pending_asset_stays_in_moderation_queue() -> None:
    result = decide_turn(make_turn())

    assert result.action == "queued_for_moderation"
    assert result.asset_id == "map-77"


def test_failure_capture_uses_stable_domain_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def record(payload: dict[str, object], idempotency_key: str) -> dict[str, object]:
        captured.update(payload)
        captured["idempotency_key"] = idempotency_key
        return {"event_id": "event-1"}

    monkeypatch.setattr("game_failure_service.game_agent_loop.infrai.errors.capture", record)

    def fail(_: AgentTurn) -> None:
        raise ValueError("classifier returned an invalid label")

    with pytest.raises(ValueError):
        run_agent_step(make_turn("approved"), fail)

    assert captured["fingerprint"] == ["ugc-review-agent", "classify-player-map", "map"]
    assert captured["idempotency_key"] == "agent-turn:turn-2048:classify-player-map"
    assert captured["context"] == {
        "turn_id": "turn-2048",
        "asset_id": "map-77",
        "creator_id": "player-9",
        "live_event_id": "summer-raid",
        "live_event_phase": "live",
        "moderation_queue_id": "ugc-primary",
        "moderation_status": "approved",
    }

