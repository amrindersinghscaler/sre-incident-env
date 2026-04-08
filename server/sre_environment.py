"""SRE Incident Response Environment — OpenEnv Environment subclass."""

from __future__ import annotations

import uuid
from typing import Optional

from openenv.core.env_server import Environment

from sre_incident_env.models import SREAction, SREObservation, SREState
from server.cluster import Cluster, AVAILABLE_COMMANDS
from server.scenarios import get_scenario
from server.grader import grade_task


class SREEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = False

    def __init__(self):
        super().__init__()
        self.cluster = Cluster()
        self._state = SREState()
        self._task_id = "easy"
        self._max_steps = 15
        self._done = False
        self._scenario = {}
        self._prev_grader_score = 0.0

    def reset(self, seed: Optional[int] = None, episode_id: Optional[str] = None, **kwargs) -> SREObservation:
        self._task_id = kwargs.get("task_id", "easy")
        self._scenario = get_scenario(self._task_id)
        self._max_steps = self._scenario["max_steps"]
        self._done = False
        self._prev_grader_score = 0.0

        self.cluster.reset(self._scenario, seed=seed)

        self._state = SREState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            task_id=self._task_id,
            task_difficulty=self._scenario["difficulty"],
            cluster_snapshot=self.cluster.get_snapshot(),
        )

        return SREObservation(
            done=False,
            reward=None,
            output=self._scenario["description"],
            alerts=self.cluster.get_active_alerts(),
            system_health=self.cluster.get_system_health(),
            services_status=self.cluster.get_services_status(),
            step_count=0,
            max_steps=self._max_steps,
            available_commands=AVAILABLE_COMMANDS,
        )

    def step(self, action: SREAction, timeout_s: Optional[float] = None, **kwargs) -> SREObservation:
        if self._done:
            return SREObservation(
                done=True,
                reward=0.0,
                output="Episode already finished. Call reset() to start a new episode.",
                alerts=[],
                system_health=self.cluster.get_system_health(),
                services_status=self.cluster.get_services_status(),
                step_count=self._state.step_count,
                max_steps=self._max_steps,
                available_commands=AVAILABLE_COMMANDS,
            )

        # Execute command
        output = self.cluster.execute_command(action.command, action.target, action.parameters)

        # Advance simulation (degradation + cascading)
        self.cluster.tick()

        # Update state
        self._state.step_count += 1
        snapshot = self.cluster.get_snapshot()
        self._state.cluster_snapshot = snapshot

        # Run grader to get current score, reward = delta from previous
        # Delta can be NEGATIVE if degradation worsened things or agent
        # took a destructive action (e.g. restarted healthy service).
        # This penalizes clearly undesirable behavior.
        current_grade = grade_task(
            self._task_id,
            snapshot,
            self.cluster.investigation_history,
        )
        current_score = current_grade["reward"]
        step_reward = current_score - self._prev_grader_score
        self._prev_grader_score = current_score

        # Check if episode is done
        at_max_steps = self._state.step_count >= self._max_steps
        all_healthy = all(
            s.get("status") == "healthy" for s in snapshot.get("services", {}).values()
        )
        diagnosis_done = snapshot.get("diagnosis_submitted") is not None
        self._done = at_max_steps or (all_healthy and diagnosis_done)

        return SREObservation(
            done=self._done,
            reward=round(step_reward, 4),
            output=output,
            alerts=self.cluster.get_active_alerts(),
            system_health=self.cluster.get_system_health(),
            services_status=self.cluster.get_services_status(),
            step_count=self._state.step_count,
            max_steps=self._max_steps,
            available_commands=AVAILABLE_COMMANDS,
        )

    @property
    def state(self) -> SREState:
        return self._state
