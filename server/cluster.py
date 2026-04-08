"""In-memory microservices cluster simulator."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Process:
    pid: str
    name: str
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    status: str = "running"
    malicious: bool = False


@dataclass
class Service:
    name: str
    status: str = "healthy"  # healthy, degraded, down
    cpu_percent: float = 15.0
    memory_percent: float = 30.0
    latency_ms: float = 50.0
    error_rate: float = 0.0
    disk_usage_percent: float = 40.0
    logs: List[str] = field(default_factory=list)
    processes: List[Process] = field(default_factory=list)
    network_connections: List[Dict[str, str]] = field(default_factory=list)
    config: Dict[str, str] = field(default_factory=dict)
    deployment_version: str = "v1.0.0"
    previous_version: str = "v0.9.0"
    credentials_rotated: bool = False
    restart_count: int = 0
    was_rolled_back: bool = False


@dataclass
class Alert:
    severity: str  # critical, warning, info
    service: str
    message: str
    timestamp: str
    is_noise: bool = False
    ttl: int = -1  # steps until auto-resolve, -1 = permanent


class Cluster:
    def __init__(self):
        self.services: Dict[str, Service] = {}
        self.dependency_graph: Dict[str, List[str]] = {}
        self.alerts: List[Alert] = []
        self.step_count: int = 0
        self.root_cause_service: str = ""
        self.root_cause_issue: str = ""
        self.fix_actions_taken: List[Dict[str, Any]] = []
        self.investigation_history: List[Dict[str, Any]] = []
        self.diagnosis_submitted: Optional[Dict[str, Any]] = None
        self.degradation_rate: float = 0.02
        self.rng: random.Random = random.Random(42)

    def reset(self, scenario: Dict[str, Any], seed: Optional[int] = None) -> None:
        if seed is not None:
            self.rng = random.Random(seed)
        else:
            self.rng = random.Random(42)

        self.step_count = 0
        self.fix_actions_taken = []
        self.investigation_history = []
        self.diagnosis_submitted = None
        self.services = {}
        self.alerts = []

        self.dependency_graph = scenario.get("dependency_graph", {})
        self.root_cause_service = scenario.get("root_cause", {}).get("service", "")
        self.root_cause_issue = scenario.get("root_cause", {}).get("issue", "")
        self.degradation_rate = scenario.get("degradation_rate", 0.02)

        for svc_def in scenario.get("services", []):
            processes = [
                Process(**p) for p in svc_def.get("processes", [])
            ]
            svc = Service(
                name=svc_def["name"],
                status=svc_def.get("status", "healthy"),
                cpu_percent=svc_def.get("cpu_percent", 15.0),
                memory_percent=svc_def.get("memory_percent", 30.0),
                latency_ms=svc_def.get("latency_ms", 50.0),
                error_rate=svc_def.get("error_rate", 0.0),
                disk_usage_percent=svc_def.get("disk_usage_percent", 40.0),
                logs=list(svc_def.get("logs", [])),
                processes=processes,
                network_connections=list(svc_def.get("network_connections", [])),
                config=dict(svc_def.get("config", {})),
                deployment_version=svc_def.get("deployment_version", "v1.0.0"),
                previous_version=svc_def.get("previous_version", "v0.9.0"),
            )
            self.services[svc.name] = svc

        for alert_def in scenario.get("alerts", []):
            self.alerts.append(Alert(**alert_def))

    def tick(self) -> None:
        """Advance simulation one step — degrade unhealthy services, cascade."""
        self.step_count += 1

        # Remove expired noise alerts
        self.alerts = [
            a for a in self.alerts
            if not (a.is_noise and a.ttl > 0 and self.step_count > a.ttl)
        ]

        for name, svc in self.services.items():
            if svc.status == "down":
                svc.error_rate = min(100.0, svc.error_rate + 5.0)
                svc.latency_ms = min(30000.0, svc.latency_ms * 1.1)
            elif svc.status == "degraded":
                svc.cpu_percent = min(100.0, svc.cpu_percent + self.degradation_rate * 100)
                svc.memory_percent = min(100.0, svc.memory_percent + self.degradation_rate * 50)
                svc.latency_ms = min(30000.0, svc.latency_ms * (1.0 + self.degradation_rate))
                svc.error_rate = min(100.0, svc.error_rate + self.degradation_rate * 10)

                if svc.cpu_percent > 95 or svc.memory_percent > 95 or svc.error_rate > 50:
                    svc.status = "down"
                    svc.logs.append(f"[CRITICAL] {name} is DOWN — resource exhaustion")

        # Cascade: if a service depends on a down service, it degrades
        if self.step_count > 2:
            for name, deps in self.dependency_graph.items():
                if name in self.services and self.services[name].status == "healthy":
                    for dep in deps:
                        if dep in self.services and self.services[dep].status == "down":
                            self.services[name].status = "degraded"
                            self.services[name].error_rate += 10.0
                            self.services[name].latency_ms *= 2.0
                            self.services[name].logs.append(
                                f"[ERROR] Dependency {dep} is down — {name} degrading"
                            )

    def get_system_health(self) -> float:
        if not self.services:
            return 100.0
        scores = []
        for svc in self.services.values():
            if svc.status == "healthy":
                scores.append(100.0)
            elif svc.status == "degraded":
                scores.append(max(0, 50.0 - svc.error_rate))
            else:
                scores.append(0.0)
        return round(sum(scores) / len(scores), 1)

    def get_services_status(self) -> Dict[str, str]:
        return {name: svc.status for name, svc in self.services.items()}

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        return [
            {
                "severity": a.severity,
                "service": a.service,
                "message": a.message,
                "timestamp": a.timestamp,
            }
            for a in self.alerts
        ]

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "services": {
                name: {
                    "status": svc.status,
                    "cpu_percent": svc.cpu_percent,
                    "memory_percent": svc.memory_percent,
                    "error_rate": svc.error_rate,
                    "restart_count": svc.restart_count,
                    "was_rolled_back": svc.was_rolled_back,
                    "credentials_rotated": svc.credentials_rotated,
                    "disk_usage_percent": svc.disk_usage_percent,
                    "processes": [
                        {"pid": p.pid, "name": p.name, "status": p.status, "malicious": p.malicious}
                        for p in svc.processes
                    ],
                }
                for name, svc in self.services.items()
            },
            "fix_actions_taken": self.fix_actions_taken,
            "investigation_history": self.investigation_history,
            "diagnosis_submitted": self.diagnosis_submitted,
            "step_count": self.step_count,
        }

    def execute_command(self, command: str, target: str, parameters: Dict[str, Any]) -> str:
        self.investigation_history.append({
            "step": self.step_count,
            "command": command,
            "target": target,
            "parameters": parameters,
        })

        handler = getattr(self, f"_cmd_{command}", None)
        if handler is None:
            return f"Unknown command: {command}. Available: {', '.join(AVAILABLE_COMMANDS)}"
        return handler(target, parameters)

    # ── Investigation Commands ───────────────────────────────────────

    def _cmd_check_logs(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found. Available: {', '.join(self.services.keys())}"
        lines = params.get("lines", 20)
        recent = svc.logs[-lines:]
        if not recent:
            return f"[{target}] No log entries."
        return f"[{target}] Recent logs:\n" + "\n".join(recent)

    def _cmd_get_metrics(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found. Available: {', '.join(self.services.keys())}"
        return (
            f"[{target}] Metrics:\n"
            f"  Status: {svc.status}\n"
            f"  CPU: {svc.cpu_percent:.1f}%\n"
            f"  Memory: {svc.memory_percent:.1f}%\n"
            f"  Disk: {svc.disk_usage_percent:.1f}%\n"
            f"  Latency: {svc.latency_ms:.0f}ms\n"
            f"  Error Rate: {svc.error_rate:.1f}%\n"
            f"  Restarts: {svc.restart_count}\n"
            f"  Version: {svc.deployment_version}"
        )

    def _cmd_list_alerts(self, target: str, params: Dict) -> str:
        active = self.get_active_alerts()
        if not active:
            return "No active alerts."
        lines = []
        for a in active:
            lines.append(f"  [{a['severity'].upper()}] {a['service']}: {a['message']} ({a['timestamp']})")
        return f"Active alerts ({len(active)}):\n" + "\n".join(lines)

    def _cmd_check_dependencies(self, target: str, params: Dict) -> str:
        if target and target in self.dependency_graph:
            deps = self.dependency_graph[target]
            dep_status = []
            for d in deps:
                s = self.services.get(d)
                dep_status.append(f"  {d}: {s.status if s else 'unknown'}")
            return f"[{target}] depends on:\n" + "\n".join(dep_status) if dep_status else f"[{target}] has no dependencies."

        lines = []
        for svc, deps in self.dependency_graph.items():
            if deps:
                lines.append(f"  {svc} -> {', '.join(deps)}")
        return "Dependency graph:\n" + "\n".join(lines) if lines else "No dependencies defined."

    def _cmd_check_network(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found."
        if not svc.network_connections:
            return f"[{target}] No active network connections."
        lines = [f"  {c.get('src', '?')} -> {c.get('dst', '?')} ({c.get('state', '?')})" for c in svc.network_connections]
        return f"[{target}] Network connections:\n" + "\n".join(lines)

    def _cmd_check_processes(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found."
        if not svc.processes:
            return f"[{target}] No running processes."
        lines = []
        for p in svc.processes:
            flag = " [SUSPICIOUS]" if p.cpu_percent > 80 else ""
            lines.append(f"  PID {p.pid}: {p.name} (CPU: {p.cpu_percent:.1f}%, MEM: {p.memory_mb:.0f}MB, {p.status}){flag}")
        return f"[{target}] Processes:\n" + "\n".join(lines)

    # ── Remediation Commands ─────────────────────────────────────────

    def _cmd_restart_service(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found."

        self.fix_actions_taken.append({"command": "restart_service", "target": target})
        svc.restart_count += 1

        # Restart only helps if root cause is fixed or it IS the root cause with a simple fix
        root_fixed = self._is_root_cause_addressed()
        if target == self.root_cause_service and root_fixed:
            svc.status = "healthy"
            svc.cpu_percent = 15.0
            svc.memory_percent = 30.0
            svc.latency_ms = 50.0
            svc.error_rate = 0.0
            svc.logs.append(f"[INFO] {target} restarted successfully — service recovered")
            self._try_recover_dependents()
            return f"[{target}] Service restarted. Status: healthy"
        elif target == self.root_cause_service:
            # Temporary fix, will degrade again
            svc.status = "degraded"
            svc.cpu_percent = max(svc.cpu_percent - 20, 30.0)
            svc.memory_percent = max(svc.memory_percent - 20, 30.0)
            svc.error_rate = max(svc.error_rate - 10, 5.0)
            svc.logs.append(f"[WARN] {target} restarted but root cause not fixed — will degrade again")
            return f"[{target}] Service restarted. Status: degraded (root cause not resolved)"
        elif svc.status != "healthy":
            # Non-root-cause service: check if its dependency is fixed
            deps = self.dependency_graph.get(target, [])
            deps_ok = all(
                self.services.get(d, Service(name=d)).status == "healthy"
                for d in deps
            )
            if deps_ok:
                svc.status = "healthy"
                svc.error_rate = 0.0
                svc.latency_ms = 50.0
                svc.logs.append(f"[INFO] {target} restarted — dependencies healthy, recovered")
                return f"[{target}] Service restarted. Status: healthy"
            else:
                svc.logs.append(f"[WARN] {target} restarted but dependencies still unhealthy")
                return f"[{target}] Service restarted but dependencies are still down. Status: {svc.status}"
        else:
            svc.logs.append(f"[INFO] {target} restarted (was already healthy)")
            return f"[{target}] Service was already healthy. Restarted anyway."

    def _cmd_scale_service(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found."
        replicas = params.get("replicas", 2)
        self.fix_actions_taken.append({"command": "scale_service", "target": target, "replicas": replicas})
        if svc.status == "degraded":
            svc.latency_ms = max(50.0, svc.latency_ms / replicas)
            svc.error_rate = max(0, svc.error_rate - 5.0 * replicas)
            svc.logs.append(f"[INFO] {target} scaled to {replicas} replicas")
        return f"[{target}] Scaled to {replicas} replicas."

    def _cmd_rollback_service(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found."

        self.fix_actions_taken.append({"command": "rollback_service", "target": target})
        svc.was_rolled_back = True
        svc.deployment_version = svc.previous_version
        # Remove malicious processes on rollback
        svc.processes = [p for p in svc.processes if not p.malicious]
        if target == self.root_cause_service:
            svc.cpu_percent = max(20.0, svc.cpu_percent - 40)
            svc.logs.append(f"[INFO] {target} rolled back to {svc.previous_version}")
        else:
            svc.logs.append(f"[INFO] {target} rolled back to {svc.previous_version}")
        return f"[{target}] Rolled back to {svc.previous_version}."

    def _cmd_kill_process(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found."
        pid = str(params.get("pid", ""))
        if not pid:
            return "Error: 'pid' parameter required."

        self.fix_actions_taken.append({"command": "kill_process", "target": target, "pid": pid})
        for p in svc.processes:
            if p.pid == pid:
                p.status = "killed"
                if p.malicious:
                    svc.cpu_percent = max(15.0, svc.cpu_percent - 60)
                    svc.logs.append(f"[INFO] Killed malicious process {pid} ({p.name})")
                    return f"[{target}] Killed process {pid} ({p.name}). CPU usage dropped significantly."
                else:
                    svc.logs.append(f"[WARN] Killed process {pid} ({p.name})")
                    return f"[{target}] Killed process {pid} ({p.name})."
        return f"[{target}] Process {pid} not found."

    def _cmd_update_config(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found."
        key = params.get("key", "")
        value = params.get("value", "")
        if not key:
            return "Error: 'key' parameter required."

        self.fix_actions_taken.append({"command": "update_config", "target": target, "key": key, "value": value})
        svc.config[key] = value
        svc.logs.append(f"[INFO] Config updated: {key}={value}")
        return f"[{target}] Config updated: {key}={value}"

    def _cmd_rotate_credentials(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found."

        self.fix_actions_taken.append({"command": "rotate_credentials", "target": target})
        svc.credentials_rotated = True
        svc.logs.append(f"[INFO] Credentials rotated for {target}")
        return f"[{target}] Credentials rotated successfully."

    def _cmd_clear_disk(self, target: str, params: Dict) -> str:
        svc = self.services.get(target)
        if not svc:
            return f"Service '{target}' not found."
        path = params.get("path", "/var/log")

        self.fix_actions_taken.append({"command": "clear_disk", "target": target, "path": path})
        svc.disk_usage_percent = max(20.0, svc.disk_usage_percent - 50)
        if svc.disk_usage_percent < 80 and svc.status == "degraded":
            svc.status = "healthy"
            svc.error_rate = 0.0
            svc.logs.append(f"[INFO] Disk cleared at {path}. Service recovered.")
            return f"[{target}] Cleared {path}. Disk: {svc.disk_usage_percent:.0f}%. Service recovered."
        svc.logs.append(f"[INFO] Disk cleared at {path}. Usage: {svc.disk_usage_percent:.0f}%")
        return f"[{target}] Cleared {path}. Disk usage: {svc.disk_usage_percent:.0f}%"

    def _cmd_submit_diagnosis(self, target: str, params: Dict) -> str:
        root_cause = params.get("root_cause", "")
        affected = params.get("affected_services", [])
        if not root_cause:
            return "Error: 'root_cause' parameter required."

        self.diagnosis_submitted = {
            "root_cause": root_cause,
            "affected_services": affected,
        }
        self.fix_actions_taken.append({"command": "submit_diagnosis", "root_cause": root_cause})
        return f"Diagnosis submitted: {root_cause}"

    # ── Helpers ──────────────────────────────────────────────────────

    def _is_root_cause_addressed(self) -> bool:
        """Check if the fix actions taken so far address the root cause."""
        actions = {(a["command"], a.get("target", "")) for a in self.fix_actions_taken}
        svc = self.services.get(self.root_cause_service)
        if not svc:
            return False

        # Check if malicious processes are killed
        has_active_malicious = any(
            p.malicious and p.status != "killed" for p in svc.processes
        )
        if has_active_malicious:
            return False

        # Check disk issues
        if svc.disk_usage_percent > 90:
            return False

        return True

    def _try_recover_dependents(self) -> None:
        """After root cause is fixed, try to recover dependent services."""
        for name, deps in self.dependency_graph.items():
            svc = self.services.get(name)
            if svc and svc.status in ("degraded", "down"):
                all_deps_ok = all(
                    self.services.get(d, Service(name=d)).status == "healthy"
                    for d in deps
                )
                if all_deps_ok:
                    svc.status = "degraded"  # Will need restart to fully recover
                    svc.error_rate = max(0, svc.error_rate - 20)


AVAILABLE_COMMANDS = [
    "check_logs", "get_metrics", "list_alerts", "check_dependencies",
    "check_network", "check_processes", "restart_service", "scale_service",
    "rollback_service", "kill_process", "update_config", "rotate_credentials",
    "clear_disk", "submit_diagnosis",
]
