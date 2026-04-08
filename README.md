---
title: SRE Incident Response Environment
emoji: 🔧
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 8000
tags:
  - openenv
---

# SRE Incident Response Environment

An OpenEnv environment where AI agents diagnose and resolve production infrastructure incidents in a simulated microservices cluster.

## Motivation

Site Reliability Engineering (SRE) incident response is a high-stakes, real-world task performed daily by millions of engineers. Agents must investigate alerts, trace dependencies, identify root causes, and apply fixes under time pressure — all while avoiding destructive actions on healthy services.

## Action Space

The agent sends structured commands:

```python
SREAction(command="check_logs", target="api-gateway", parameters={"lines": 20})
```

| Command | Target | Parameters | Description |
|---------|--------|------------|-------------|
| `check_logs` | service | `{lines: int}` | View recent log entries |
| `get_metrics` | service | | CPU, memory, latency, error rate |
| `list_alerts` | — | | All active alerts |
| `check_dependencies` | service | | Dependency graph |
| `check_network` | service | | Network connections |
| `check_processes` | service | | Running processes with PIDs |
| `restart_service` | service | | Restart a service |
| `scale_service` | service | `{replicas: int}` | Scale up/down |
| `rollback_service` | service | | Rollback to previous deploy |
| `kill_process` | service | `{pid: str}` | Kill a specific process |
| `update_config` | service | `{key, value}` | Update config |
| `rotate_credentials` | service | | Rotate service credentials |
| `clear_disk` | service | `{path: str}` | Clear disk space |
| `submit_diagnosis` | — | `{root_cause, affected_services}` | Submit root cause |

## Observation Space

```python
SREObservation(
    output: str,              # Command result text
    alerts: list[dict],       # Active alerts
    system_health: float,     # 0-100 cluster health
    services_status: dict,    # {service: "healthy"|"degraded"|"down"}
    step_count: int,
    max_steps: int,
    available_commands: list[str],
    done: bool,
    reward: float | None,
)
```

## Tasks

### Easy — Memory Leak in API Gateway
Single service (`api-gateway`) with memory leak causing OOM kills. Clear log signals, no red herrings. **Optimal: ~5 steps. Max: 15 steps.**

### Medium — Cascading Database Failure
`postgres-primary` connection pool exhausted, causing cascading failures across 3 dependent services. Includes red herring alerts on `cache-service`. **Optimal: ~10 steps. Max: 20 steps.**

### Hard — Crypto-Mining Attack + Disk Full
Compromised `worker-service` running crypto miner (xmrig). Concurrent disk full on `log-aggregator`. Agent must kill malicious process, rollback deployment, rotate credentials, AND clear disk. **Optimal: ~15 steps. Max: 25 steps.**

## Reward Design

The grader runs at every step. Each step's reward is the **increase** in grader score since the last step:

- Step makes progress (e.g. restarts the right service) → reward > 0
- Step makes no progress (e.g. checks an irrelevant service) → reward = 0
- Sum of all step rewards = final grader score (0.0-1.0)

Each task's grader evaluates weighted binary criteria (e.g., "Was the root cause service restarted?" = 0 or 1, weight 0.4). The final score is the weighted average.

Progressive system degradation creates time pressure — services get worse each step, making criteria harder to satisfy if the agent is slow.

## Setup

```bash
# Install
pip install openenv-core

# Run locally
git clone <this-repo>
cd sre-incident-env
pip install -r requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 8000

# Or via Docker
docker build -t sre-incident-env .
docker run -p 8000:8000 sre-incident-env
```

## Usage

```python
from sre_incident_env import SREIncidentEnv, SREAction

async with SREIncidentEnv(base_url="http://localhost:8000") as env:
    result = await env.reset(task_id="easy")
    print(result.observation.output)  # Initial alert description

    result = await env.step(SREAction(command="check_logs", target="api-gateway"))
    print(result.observation.output)  # Log entries
    print(result.reward)              # Per-step reward
```

## Baseline Scores

| Task | Score | Steps |
|------|-------|-------|
| Easy | ~0.60 | 5-8 |
| Medium | ~0.35 | 10-15 |
| Hard | ~0.25 | 15-20 |

*Scores from Qwen2.5-72B-Instruct via HF Router.*

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `https://router.huggingface.co/v1` | LLM API endpoint |
| `MODEL_NAME` | `Qwen/Qwen2.5-72B-Instruct` | Model identifier |
| `HF_TOKEN` | — | HuggingFace API key |
| `IMAGE_NAME` | — | Docker image name |
