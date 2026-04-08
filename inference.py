"""
Inference Script — SRE Incident Response Environment
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.
    LOCAL_IMAGE_NAME The name of the local image to use for the environment if you are using from_docker_image()

STDOUT FORMAT
- The script must emit exactly three line types to stdout, in this order:

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import asyncio
import json
import os
import textwrap
from typing import List, Optional

from openai import OpenAI

from sre_incident_env import SREAction, SREIncidentEnv

IMAGE_NAME = os.getenv("IMAGE_NAME")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
BENCHMARK = "sre_incident_env"
TEMPERATURE = 0.7
MAX_TOKENS = 300
SUCCESS_SCORE_THRESHOLD = 0.3

TASKS = [
    {"task_id": "easy", "max_steps": 15, "max_reward": 1.0},
    {"task_id": "medium", "max_steps": 20, "max_reward": 1.0},
    {"task_id": "hard", "max_steps": 25, "max_reward": 1.0},
]

SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert SRE (Site Reliability Engineer) responding to a production incident.
    You interact with a simulated microservices cluster through commands.

    Available commands:
    - check_logs <service>: View recent logs
    - get_metrics <service>: Get CPU, memory, latency, error rate
    - list_alerts: List all active alerts
    - check_dependencies <service>: Show dependency graph
    - check_network <service>: Show network connections
    - check_processes <service>: List running processes
    - restart_service <service>: Restart a service
    - scale_service <service> replicas=<n>: Scale a service
    - rollback_service <service>: Rollback to previous deployment
    - kill_process <service> pid=<pid>: Kill a specific process
    - update_config <service> key=<k> value=<v>: Update config
    - rotate_credentials <service>: Rotate credentials
    - clear_disk <service> path=<path>: Clear disk space
    - submit_diagnosis root_cause=<text> affected_services=<svc1,svc2>: Submit root cause

    Respond with ONLY a JSON object: {"command": "...", "target": "...", "parameters": {...}}
    Do not include any other text.
""").strip()


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


def parse_action(text: str) -> SREAction:
    """Parse LLM response into SREAction."""
    text = text.strip()
    # Try JSON parse first
    try:
        data = json.loads(text)
        return SREAction(
            command=data.get("command", "list_alerts"),
            target=data.get("target", ""),
            parameters=data.get("parameters", {}),
        )
    except (json.JSONDecodeError, KeyError):
        pass

    # Fallback: parse text like "check_logs api-gateway"
    parts = text.split()
    if len(parts) >= 2:
        return SREAction(command=parts[0], target=parts[1])
    elif len(parts) == 1:
        return SREAction(command=parts[0])
    return SREAction(command="list_alerts")


def build_user_prompt(step: int, last_output: str, last_reward: float, history: List[str]) -> str:
    history_block = "\n".join(history[-4:]) if history else "None"
    return textwrap.dedent(f"""
        Step: {step}
        Last command output:
        {last_output[:1500]}

        Last reward: {last_reward:.2f}
        Previous actions:
        {history_block}

        Analyze the situation and decide your next action.
        Respond with ONLY a JSON object: {{"command": "...", "target": "...", "parameters": {{...}}}}
    """).strip()


def get_model_action(client: OpenAI, step: int, last_output: str, last_reward: float, history: List[str]) -> SREAction:
    user_prompt = build_user_prompt(step, last_output, last_reward, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        return parse_action(text) if text else SREAction(command="list_alerts")
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return SREAction(command="list_alerts")


async def run_task(client: OpenAI, env: SREIncidentEnv, task: dict) -> None:
    task_id = task["task_id"]
    max_steps = task["max_steps"]
    max_total_reward = task["max_reward"]

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = await env.reset(task_id=task_id)
        last_output = result.observation.output
        last_reward = 0.0

        for step in range(1, max_steps + 1):
            if result.done:
                break

            action = get_model_action(client, step, last_output, last_reward, history)
            action_str = f"{action.command}({action.target})"

            result = await env.step(action)
            obs = result.observation

            reward = result.reward or 0.0
            done = result.done
            error = None

            rewards.append(reward)
            steps_taken = step
            last_output = obs.output
            last_reward = reward

            log_step(step=step, action=action_str, reward=reward, done=done, error=error)

            history.append(f"Step {step}: {action_str} -> reward {reward:+.2f}")

            if done:
                break

        score = sum(rewards) / max_total_reward if max_total_reward > 0 else 0.0
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    env = await SREIncidentEnv.from_docker_image(IMAGE_NAME)

    try:
        for task in TASKS:
            await run_task(client, env, task)
    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error (container cleanup): {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
