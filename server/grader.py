"""Deterministic grading for SRE incident response tasks."""

from __future__ import annotations

from typing import Any, Dict, List

OPTIMAL_STEPS = {"easy": 5, "medium": 10, "hard": 15}


def grade_task(task_id: str, cluster_snapshot: Dict[str, Any], action_history: List[Dict]) -> Dict[str, Any]:
    """Grade a completed episode. Returns {"reward": float, "metadata": dict}."""
    grader_map = {
        "easy": _grade_easy,
        "medium": _grade_medium,
        "hard": _grade_hard,
    }
    grader = grader_map.get(task_id)
    if not grader:
        return {"reward": 0.5, "metadata": {"error": f"Unknown task: {task_id}"}}
    return grader(cluster_snapshot, action_history)


def _efficiency_score(task_id: str, steps_taken: int) -> float:
    """Score based on how efficiently the agent solved the task.
    Returns value in (0, 1) — mathematically cannot be 0.0 or 1.0."""
    optimal = OPTIMAL_STEPS.get(task_id, 10)
    return optimal / (steps_taken + optimal)


def _weighted_score(results: List[Dict]) -> float:
    total_weight = sum(r["weight"] for r in results)
    if total_weight == 0:
        return 0.5
    return sum(r["score"] * r["weight"] for r in results) / total_weight


# ═══════════════════════════════════════════════════════════════════
# EASY — Memory Leak in API Gateway
# ═══════════════════════════════════════════════════════════════════

def _grade_easy(snapshot: Dict, history: List[Dict]) -> Dict[str, Any]:
    services = snapshot.get("services", {})
    steps = snapshot.get("step_count", len(history))
    results = []

    # 1. Did agent investigate the root cause service?
    investigated = any(
        h["command"] in ("check_logs", "get_metrics", "check_processes")
        and h["target"] == "api-gateway"
        for h in history
    )
    results.append({"name": "Investigated api-gateway", "score": 1.0 if investigated else 0.0, "weight": 0.2})

    # 2. Was api-gateway restarted?
    restarted = any(
        h["command"] == "restart_service" and h["target"] == "api-gateway"
        for h in history
    )
    results.append({"name": "Restarted api-gateway", "score": 1.0 if restarted else 0.0, "weight": 0.3})

    # 3. Is api-gateway healthy now?
    gw = services.get("api-gateway", {})
    healthy = gw.get("status") == "healthy"
    results.append({"name": "api-gateway is healthy", "score": 1.0 if healthy else 0.0, "weight": 0.2})

    # 4. Didn't restart healthy services unnecessarily
    unnecessary_restarts = sum(
        1 for h in history
        if h["command"] == "restart_service" and h["target"] not in ("api-gateway", "frontend")
    )
    no_waste = unnecessary_restarts == 0
    results.append({"name": "No unnecessary restarts", "score": 1.0 if no_waste else 0.0, "weight": 0.1})

    # 5. Efficiency — always in (0, 1), prevents total from hitting 0.0 or 1.0
    eff = _efficiency_score("easy", steps)
    results.append({"name": "Resolution efficiency", "score": round(eff, 4), "weight": 0.2})

    return {"reward": round(_weighted_score(results), 4), "metadata": {"evaluations": results}}


# ═══════════════════════════════════════════════════════════════════
# MEDIUM — Cascading Database Failure
# ═══════════════════════════════════════════════════════════════════

def _grade_medium(snapshot: Dict, history: List[Dict]) -> Dict[str, Any]:
    services = snapshot.get("services", {})
    steps = snapshot.get("step_count", len(history))
    results = []

    # 1. Traced dependencies
    traced = any(
        h["command"] == "check_dependencies"
        for h in history
    )
    results.append({"name": "Traced dependency graph", "score": 1.0 if traced else 0.0, "weight": 0.1})

    # 2. Identified postgres as root cause (investigated it)
    db_investigated = any(
        h["command"] in ("check_logs", "get_metrics")
        and h["target"] == "postgres-primary"
        for h in history
    )
    results.append({"name": "Investigated postgres-primary", "score": 1.0 if db_investigated else 0.0, "weight": 0.15})

    # 3. Fixed postgres (restarted or updated config)
    db_fixed = any(
        h["command"] in ("restart_service", "update_config")
        and h["target"] == "postgres-primary"
        for h in history
    )
    db_svc = services.get("postgres-primary", {})
    db_healthy = db_svc.get("status") == "healthy"
    results.append({"name": "Fixed postgres-primary", "score": 1.0 if (db_fixed and db_healthy) else 0.0, "weight": 0.2})

    # 4. Downstream services recovered
    downstream_names = ["user-service", "order-service", "payment-service"]
    recovered = sum(1 for n in downstream_names if services.get(n, {}).get("status") == "healthy")
    downstream_score = recovered / len(downstream_names)
    results.append({"name": "Downstream services recovered", "score": round(downstream_score, 4), "weight": 0.2})

    # 5. Didn't act on red herring alerts (didn't restart cache-service)
    acted_on_noise = any(
        h["command"] in ("restart_service", "scale_service", "rollback_service")
        and h["target"] == "cache-service"
        for h in history
    )
    results.append({"name": "Ignored red herring alerts", "score": 0.0 if acted_on_noise else 1.0, "weight": 0.15})

    # 6. Efficiency
    eff = _efficiency_score("medium", steps)
    results.append({"name": "Resolution efficiency", "score": round(eff, 4), "weight": 0.2})

    return {"reward": round(_weighted_score(results), 4), "metadata": {"evaluations": results}}


# ═══════════════════════════════════════════════════════════════════
# HARD — Crypto-Mining Attack + Disk Full
# ═══════════════════════════════════════════════════════════════════

def _grade_hard(snapshot: Dict, history: List[Dict]) -> Dict[str, Any]:
    services = snapshot.get("services", {})
    steps = snapshot.get("step_count", len(history))
    results = []

    # 1. Investigated worker-service (the compromised service)
    investigated = any(
        h["command"] in ("check_logs", "get_metrics", "check_processes", "check_network")
        and h["target"] == "worker-service"
        for h in history
    )
    results.append({"name": "Investigated worker-service", "score": 1.0 if investigated else 0.0, "weight": 0.1})

    # 2. Killed the crypto miner process
    worker = services.get("worker-service", {})
    miner_killed = any(
        p.get("name") in ("xmrig", "kworker/u8:2") and p.get("status") == "killed"
        for p in worker.get("processes", [])
    )
    results.append({"name": "Killed crypto miner", "score": 1.0 if miner_killed else 0.0, "weight": 0.1})

    # 3. Rolled back compromised deployment
    rolled_back = worker.get("was_rolled_back", False)
    results.append({"name": "Rolled back worker-service", "score": 1.0 if rolled_back else 0.0, "weight": 0.1})

    # 4. Rotated credentials
    creds_rotated = worker.get("credentials_rotated", False)
    results.append({"name": "Rotated credentials", "score": 1.0 if creds_rotated else 0.0, "weight": 0.1})

    # 5. Fixed disk issue on log-aggregator
    log_agg = services.get("log-aggregator", {})
    disk_ok = log_agg.get("disk_usage_percent", 100) < 80
    results.append({"name": "Cleared log-aggregator disk", "score": 1.0 if disk_ok else 0.0, "weight": 0.1})

    # 6. All services healthy
    mostly_healthy = sum(1 for s in services.values() if s.get("status") == "healthy") / max(len(services), 1)
    results.append({"name": "Cluster health restored", "score": round(mostly_healthy, 4), "weight": 0.15})

    # 7. Submitted correct diagnosis
    diagnosis = snapshot.get("diagnosis_submitted")
    correct_diagnosis = False
    if diagnosis:
        rc = diagnosis.get("root_cause", "").lower()
        correct_diagnosis = any(kw in rc for kw in ["crypto", "mining", "xmrig", "malicious", "compromised", "unauthorized"])
    results.append({"name": "Correct diagnosis submitted", "score": 1.0 if correct_diagnosis else 0.0, "weight": 0.15})

    # 8. Efficiency
    eff = _efficiency_score("hard", steps)
    results.append({"name": "Resolution efficiency", "score": round(eff, 4), "weight": 0.2})

    return {"reward": round(_weighted_score(results), 4), "metadata": {"evaluations": results}}
