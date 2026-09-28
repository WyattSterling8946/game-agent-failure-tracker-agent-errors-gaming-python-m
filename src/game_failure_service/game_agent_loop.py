"""Business rules for player assets moving through a game agent loop."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from .infrai_errors import infrai


class PlayerAsset(BaseModel):
    asset_id: str
    creator_id: str
    kind: Literal["skin", "map", "dialogue"]


class LiveEvent(BaseModel):
    event_id: str
    name: str
    phase: Literal["preview", "live", "closed"]


class ModerationQueue(BaseModel):
    queue_id: str
    status: Literal["pending", "approved", "rejected"]


class AgentTurn(BaseModel):
    turn_id: str
    agent_name: str = Field(min_length=1)
    step: str = Field(min_length=1)
    asset: PlayerAsset
    live_event: LiveEvent
    moderation: ModerationQueue


class TurnResult(BaseModel):
    turn_id: str
    action: Literal["queued_for_moderation", "processed"]
    asset_id: str


def decide_turn(turn: AgentTurn) -> TurnResult:
    """Hold unreviewed assets; process assets with a final moderation decision."""
    action = "queued_for_moderation" if turn.moderation.status == "pending" else "processed"
    return TurnResult(turn_id=turn.turn_id, action=action, asset_id=turn.asset.asset_id)


def run_agent_step(turn: AgentTurn, operation: Callable[[AgentTurn], Any]) -> Any:
    """Run one step and group unexpected failures by agent, step, and asset kind."""
    try:
        return operation(turn)
    except Exception as exc:
        fingerprint = [turn.agent_name, turn.step, turn.asset.kind]
        infrai.errors.capture(
            {
                "title": f"{turn.agent_name}/{turn.step} failed",
                "message": f"{type(exc).__name__}: {exc}",
                "level": "error",
                "fingerprint": fingerprint,
                "exception": traceback.format_exc(),
                "context": {
                    "turn_id": turn.turn_id,
                    "asset_id": turn.asset.asset_id,
                    "creator_id": turn.asset.creator_id,
                    "live_event_id": turn.live_event.event_id,
                    "live_event_phase": turn.live_event.phase,
                    "moderation_queue_id": turn.moderation.queue_id,
                    "moderation_status": turn.moderation.status,
                },
            },
            idempotency_key=f"agent-turn:{turn.turn_id}:{turn.step}",
        )
        raise

