from typing import Any, Dict

from openenv.core.env_client import EnvClient
from openenv.core.client_types import StepResult

from .models import SREAction, SREObservation, SREState


class SREIncidentEnv(EnvClient[SREAction, SREObservation, SREState]):

    def _step_payload(self, action: SREAction) -> Dict[str, Any]:
        return {
            "command": action.command,
            "target": action.target,
            "parameters": action.parameters,
        }

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[SREObservation]:
        obs_data = payload.get("observation", {})
        done = payload.get("done", False)
        reward = payload.get("reward")

        observation = SREObservation(
            done=done,
            reward=reward,
            output=obs_data.get("output", ""),
            alerts=obs_data.get("alerts", []),
            system_health=obs_data.get("system_health", 0.0),
            services_status=obs_data.get("services_status", {}),
            step_count=obs_data.get("step_count", 0),
            max_steps=obs_data.get("max_steps", 20),
            available_commands=obs_data.get("available_commands", []),
        )

        return StepResult(
            observation=observation,
            reward=reward,
            done=done,
        )

    def _parse_state(self, payload: Dict[str, Any]) -> SREState:
        return SREState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            task_id=payload.get("task_id", ""),
            task_difficulty=payload.get("task_difficulty", ""),
            cluster_snapshot=payload.get("cluster_snapshot", {}),
        )
