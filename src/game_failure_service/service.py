"""HTTP boundary for the game agent turn workflow."""

from fastapi import FastAPI, HTTPException

from .game_agent_loop import AgentTurn, TurnResult, decide_turn, run_agent_step
from .infrai_errors import InfraiError


app = FastAPI(title="Game agent failure visibility")


@app.post("/agent-turns", response_model=TurnResult)
def process_agent_turn(turn: AgentTurn) -> TurnResult:
    try:
        return run_agent_step(turn, decide_turn)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail=exc.detail) from exc

