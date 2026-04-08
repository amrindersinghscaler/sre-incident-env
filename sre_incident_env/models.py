from typing import Any, Dict, List, Optional
from openenv.core.env_server import Action, Observation, State
from pydantic import BaseModel, Field


class SREAction(Action):
    command: str = Field(description="Command to execute (e.g. check_logs, restart_service)")
    target: str = Field(default="", description="Service name or resource identifier")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional command parameters")


class SREObservation(Observation):
    output: str = Field(default="", description="Command result text")
    alerts: List[Dict[str, Any]] = Field(default_factory=list, description="Active alerts")
    system_health: float = Field(default=100.0, description="Overall cluster health 0-100")
    services_status: Dict[str, str] = Field(default_factory=dict, description="Service name -> status")
    step_count: int = Field(default=0, description="Current step number")
    max_steps: int = Field(default=20, description="Maximum steps for this episode")
    available_commands: List[str] = Field(default_factory=list, description="Available commands")


class SREReward(BaseModel):
    """Typed reward model for grading results."""
    score: float = Field(ge=0.0, le=1.0, description="Grader score 0.0-1.0")
    evaluations: List[Dict[str, Any]] = Field(default_factory=list, description="Per-criterion results")


class SREState(State):
    task_id: str = Field(default="", description="Current task identifier")
    task_difficulty: str = Field(default="", description="easy, medium, or hard")
    cluster_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Full cluster state")
