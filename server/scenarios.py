"""Three task scenarios: easy, medium, hard."""

SCENARIOS = {
    # ═══════════════════════════════════════════════════════════════
    # EASY — Memory Leak in API Gateway
    # Clear logs, single root cause, no red herrings.
    # An LLM should score 0.7-1.0 here.
    # ═══════════════════════════════════════════════════════════════
    "easy": {
        "task_id": "easy",
        "difficulty": "easy",
        "title": "Memory Leak in API Gateway",
        "description": (
            "ALERT: api-gateway is experiencing high memory usage and intermittent OOM kills. "
            "Users are reporting 502 errors. Investigate and resolve the issue."
        ),
        "max_steps": 15,
        "optimal_steps": 5,
        "degradation_rate": 0.03,
        "root_cause": {
            "service": "api-gateway",
            "issue": "memory_leak",
            "keywords": ["memory", "leak", "oom", "api-gateway"],
        },
        "dependency_graph": {
            "frontend": ["api-gateway"],
            "api-gateway": ["user-service", "order-service"],
            "user-service": ["postgres-primary"],
            "order-service": ["postgres-primary"],
        },
        "services": [
            {
                "name": "frontend",
                "status": "degraded",
                "cpu_percent": 25.0,
                "memory_percent": 35.0,
                "latency_ms": 800.0,
                "error_rate": 15.0,
                "logs": [
                    "[ERROR] Upstream api-gateway returning 502 Bad Gateway",
                    "[WARN] Response time exceeded 500ms threshold",
                    "[ERROR] 15% of requests failing — user-facing errors",
                    "[INFO] Health check: frontend process healthy, upstream degraded",
                ],
                "processes": [
                    {"pid": "1001", "name": "nginx", "cpu_percent": 10.0, "memory_mb": 128.0},
                    {"pid": "1002", "name": "node-frontend", "cpu_percent": 15.0, "memory_mb": 256.0},
                ],
            },
            {
                "name": "api-gateway",
                "status": "degraded",
                "cpu_percent": 45.0,
                "memory_percent": 88.0,
                "latency_ms": 1200.0,
                "error_rate": 25.0,
                "disk_usage_percent": 40.0,
                "logs": [
                    "[WARN] Memory usage at 85% — GC pressure increasing",
                    "[ERROR] OOM kill detected on worker pid 2003 at 14:23:01",
                    "[WARN] Memory usage at 88% — approaching critical threshold",
                    "[ERROR] Request queue backing up — 250 pending requests",
                    "[WARN] Memory leak detected in connection pool — objects not being freed",
                    "[ERROR] OOM kill detected on worker pid 2004 at 14:25:33",
                    "[INFO] Auto-restart triggered for worker processes",
                    "[WARN] Memory usage climbing again after restart — leak persists",
                ],
                "processes": [
                    {"pid": "2001", "name": "api-gateway-main", "cpu_percent": 20.0, "memory_mb": 1800.0},
                    {"pid": "2002", "name": "api-gateway-worker-1", "cpu_percent": 15.0, "memory_mb": 950.0},
                    {"pid": "2003", "name": "api-gateway-worker-2", "cpu_percent": 10.0, "memory_mb": 920.0, "status": "killed"},
                ],
                "config": {"max_connections": "500", "worker_memory_limit": "2048MB"},
            },
            {
                "name": "user-service",
                "status": "healthy",
                "cpu_percent": 20.0,
                "memory_percent": 40.0,
                "latency_ms": 80.0,
                "error_rate": 2.0,
                "logs": [
                    "[INFO] Service running normally",
                    "[WARN] Increased timeout errors from upstream clients",
                    "[INFO] Database connection pool: 12/50 active",
                ],
                "processes": [
                    {"pid": "3001", "name": "user-service", "cpu_percent": 20.0, "memory_mb": 512.0},
                ],
            },
            {
                "name": "order-service",
                "status": "healthy",
                "cpu_percent": 18.0,
                "memory_percent": 35.0,
                "latency_ms": 60.0,
                "error_rate": 1.0,
                "logs": [
                    "[INFO] Service running normally",
                    "[INFO] Processing 45 orders/min",
                ],
                "processes": [
                    {"pid": "4001", "name": "order-service", "cpu_percent": 18.0, "memory_mb": 480.0},
                ],
            },
            {
                "name": "postgres-primary",
                "status": "healthy",
                "cpu_percent": 30.0,
                "memory_percent": 50.0,
                "latency_ms": 5.0,
                "error_rate": 0.0,
                "logs": [
                    "[INFO] Database healthy — 120 active connections",
                    "[INFO] Replication lag: 0ms",
                ],
                "processes": [
                    {"pid": "5001", "name": "postgres", "cpu_percent": 30.0, "memory_mb": 2048.0},
                ],
            },
        ],
        "alerts": [
            {
                "severity": "critical",
                "service": "api-gateway",
                "message": "Memory usage at 88% — OOM kills detected",
                "timestamp": "2024-01-15T14:25:00Z",
            },
            {
                "severity": "warning",
                "service": "frontend",
                "message": "Error rate above 10% threshold",
                "timestamp": "2024-01-15T14:24:00Z",
            },
        ],
    },

    # ═══════════════════════════════════════════════════════════════
    # MEDIUM — Cascading Database Failure
    # Root cause is NOT obvious from description or surface alerts.
    # Multiple services are screaming — agent must trace deps to find
    # that postgres is the upstream cause, not payment-service.
    # 4 red herring alerts to distract. Faster degradation.
    # An LLM should score 0.3-0.6 here.
    # ═══════════════════════════════════════════════════════════════
    "medium": {
        "task_id": "medium",
        "difficulty": "medium",
        "title": "Cascading Database Failure",
        "description": (
            "ALERT: payment-service is DOWN and multiple services are degraded. "
            "Customers cannot complete purchases. Several alerts firing across the stack. "
            "Investigate and restore all services."
        ),
        "max_steps": 20,
        "optimal_steps": 10,
        "degradation_rate": 0.04,
        "root_cause": {
            "service": "postgres-primary",
            "issue": "connection_pool_exhaustion",
            "keywords": ["postgres", "connection", "pool", "exhaustion", "database"],
        },
        "dependency_graph": {
            "frontend": ["api-gateway"],
            "api-gateway": ["user-service", "order-service", "payment-service"],
            "user-service": ["postgres-primary", "cache-service"],
            "order-service": ["postgres-primary", "cache-service"],
            "payment-service": ["postgres-primary"],
            "cache-service": [],
        },
        "services": [
            {
                "name": "frontend",
                "status": "degraded",
                "cpu_percent": 20.0,
                "memory_percent": 30.0,
                "latency_ms": 2000.0,
                "error_rate": 30.0,
                "logs": [
                    "[ERROR] Multiple 503 Service Unavailable responses",
                    "[ERROR] User checkout flow failing — timeouts",
                    "[WARN] Session timeouts increasing across all endpoints",
                    "[ERROR] Static assets loading but API calls failing",
                ],
                "processes": [{"pid": "1001", "name": "nginx", "cpu_percent": 10.0, "memory_mb": 128.0}],
            },
            {
                "name": "api-gateway",
                "status": "degraded",
                "cpu_percent": 35.0,
                "memory_percent": 50.0,
                "latency_ms": 1500.0,
                "error_rate": 25.0,
                "logs": [
                    "[ERROR] Timeout from downstream services (5000ms exceeded)",
                    "[ERROR] payment-service returning 500 Internal Server Error",
                    "[WARN] Circuit breaker tripped for payment-service",
                    "[ERROR] Request backlog growing — 300 queued requests",
                    "[WARN] Thread pool saturation at 95%",
                ],
                "processes": [{"pid": "2001", "name": "api-gateway", "cpu_percent": 35.0, "memory_mb": 800.0}],
            },
            {
                "name": "user-service",
                "status": "degraded",
                "cpu_percent": 70.0,
                "memory_percent": 60.0,
                "latency_ms": 4500.0,
                "error_rate": 40.0,
                "logs": [
                    "[ERROR] Connection acquisition timeout after 30s",
                    "[ERROR] java.sql.SQLTransientConnectionException: HikariPool-1 - Connection is not available",
                    "[WARN] Thread pool exhausted — 85 threads blocked on I/O",
                    "[ERROR] Query timeout: SELECT * FROM users WHERE id = $1",
                    "[INFO] Falling back to cache for read operations where possible",
                    "[WARN] Cache fallback only covers 30% of queries — rest failing",
                ],
                "processes": [{"pid": "3001", "name": "user-service", "cpu_percent": 70.0, "memory_mb": 1200.0}],
            },
            {
                "name": "order-service",
                "status": "degraded",
                "cpu_percent": 65.0,
                "memory_percent": 55.0,
                "latency_ms": 4200.0,
                "error_rate": 35.0,
                "logs": [
                    "[ERROR] Connection acquisition timeout after 30s",
                    "[ERROR] Failed to insert order record — I/O timeout",
                    "[WARN] Order processing queue growing: 450 pending orders",
                    "[ERROR] Deadlock detected — retrying transaction",
                    "[WARN] Retry budget exhausted for 12 pending transactions",
                ],
                "processes": [{"pid": "4001", "name": "order-service", "cpu_percent": 65.0, "memory_mb": 1100.0}],
            },
            {
                "name": "payment-service",
                "status": "down",
                "cpu_percent": 90.0,
                "memory_percent": 80.0,
                "latency_ms": 10000.0,
                "error_rate": 85.0,
                "logs": [
                    "[CRITICAL] All downstream connections timed out",
                    "[ERROR] Cannot process payments — backend connectivity lost",
                    "[ERROR] Transaction rollback failed — connection dropped mid-commit",
                    "[CRITICAL] Health check failing for 5 consecutive cycles",
                    "[ERROR] Stripe webhook delivery failing — cannot acknowledge",
                    "[WARN] PCI audit log write failing — compliance risk",
                ],
                "processes": [{"pid": "5001", "name": "payment-service", "cpu_percent": 90.0, "memory_mb": 1500.0}],
            },
            {
                "name": "postgres-primary",
                "status": "degraded",
                "cpu_percent": 95.0,
                "memory_percent": 85.0,
                "latency_ms": 8000.0,
                "error_rate": 60.0,
                "logs": [
                    "[WARN] High number of active connections: 495/500",
                    "[WARN] Long-running queries detected: 23 queries running > 30s",
                    "[ERROR] Lock contention on table 'orders' — 15 blocked transactions",
                    "[WARN] Checkpoint taking too long — I/O bottleneck detected",
                    "[WARN] Idle connections detected: 340 of 500 slots held by idle sessions",
                    "[INFO] Connection sources: payment-svc (180), order-svc (150), user-svc (120), unknown (50)",
                ],
                "processes": [{"pid": "6001", "name": "postgres", "cpu_percent": 95.0, "memory_mb": 4096.0}],
                "config": {"max_connections": "500", "idle_timeout": "0", "connection_limit_per_user": "200"},
            },
            {
                "name": "cache-service",
                "status": "healthy",
                "cpu_percent": 55.0,
                "memory_percent": 70.0,
                "latency_ms": 2.0,
                "error_rate": 0.0,
                "logs": [
                    "[INFO] Cache hit rate: 45% (normally 92%)",
                    "[WARN] Eviction rate increased — many cache misses",
                    "[INFO] Memory usage normal — 4.2GB / 8GB",
                ],
                "processes": [{"pid": "7001", "name": "redis", "cpu_percent": 55.0, "memory_mb": 4200.0}],
            },
        ],
        "alerts": [
            # The loudest alert is payment-service — but it's a SYMPTOM, not the cause
            {
                "severity": "critical",
                "service": "payment-service",
                "message": "Service DOWN — health checks failing for 5 minutes",
                "timestamp": "2024-01-15T14:20:00Z",
            },
            {
                "severity": "critical",
                "service": "order-service",
                "message": "Error rate at 35% — order processing stalled",
                "timestamp": "2024-01-15T14:21:00Z",
            },
            {
                "severity": "warning",
                "service": "user-service",
                "message": "Error rate above 30% — login failures increasing",
                "timestamp": "2024-01-15T14:21:30Z",
            },
            # Red herrings — look important but are unrelated
            {
                "severity": "critical",
                "service": "cache-service",
                "message": "Memory usage at 70% — approaching eviction threshold",
                "timestamp": "2024-01-15T14:19:00Z",
                "is_noise": True,
                "ttl": 3,
            },
            {
                "severity": "warning",
                "service": "cache-service",
                "message": "Cache hit rate dropped to 45% — possible cache poisoning",
                "timestamp": "2024-01-15T14:19:30Z",
                "is_noise": True,
                "ttl": 4,
            },
            {
                "severity": "warning",
                "service": "frontend",
                "message": "SSL certificate renewal failed — expires in 12 days",
                "timestamp": "2024-01-15T14:00:00Z",
                "is_noise": True,
                "ttl": 10,
            },
            {
                "severity": "info",
                "service": "api-gateway",
                "message": "New deployment v3.2.1 rolled out 6 hours ago — monitoring",
                "timestamp": "2024-01-15T08:00:00Z",
                "is_noise": True,
                "ttl": 15,
            },
        ],
    },

    # ═══════════════════════════════════════════════════════════════
    # HARD — Crypto-Mining Attack + Disk Full
    # Two CONCURRENT unrelated issues. Logs are ambiguous — no log
    # explicitly says "crypto mining". Agent must correlate: unknown
    # high-CPU process + suspicious outbound connection + recent
    # unauthorized deployment. Plus a separate disk issue on another
    # service. 5 red herring alerts. Fast degradation.
    # An LLM should score 0.1-0.3 here.
    # ═══════════════════════════════════════════════════════════════
    "hard": {
        "task_id": "hard",
        "difficulty": "hard",
        "title": "Crypto-Mining Attack + Disk Full",
        "description": (
            "ALERT: Multiple critical alerts firing. worker-service CPU at 98%. "
            "log-aggregator disk full. order-service errors spiking. cache-service "
            "memory warning. Several services degrading rapidly. Investigate all issues."
        ),
        "max_steps": 25,
        "optimal_steps": 15,
        "degradation_rate": 0.05,
        "root_cause": {
            "service": "worker-service",
            "issue": "crypto_mining_attack",
            "keywords": ["crypto", "mining", "malicious", "compromised", "attack", "xmrig", "unauthorized"],
        },
        "dependency_graph": {
            "frontend": ["api-gateway"],
            "api-gateway": ["user-service", "order-service", "worker-service"],
            "user-service": ["postgres-primary"],
            "order-service": ["postgres-primary", "worker-service"],
            "worker-service": ["postgres-primary", "cache-service"],
            "log-aggregator": [],
        },
        "services": [
            {
                "name": "frontend",
                "status": "degraded",
                "cpu_percent": 20.0,
                "memory_percent": 30.0,
                "latency_ms": 1500.0,
                "error_rate": 20.0,
                "logs": [
                    "[ERROR] Slow responses from backend",
                    "[WARN] Multiple user complaints filed in last 30 minutes",
                    "[ERROR] Checkout page timing out for 20% of users",
                ],
                "processes": [{"pid": "1001", "name": "nginx", "cpu_percent": 10.0, "memory_mb": 128.0}],
            },
            {
                "name": "api-gateway",
                "status": "degraded",
                "cpu_percent": 40.0,
                "memory_percent": 45.0,
                "latency_ms": 1200.0,
                "error_rate": 18.0,
                "logs": [
                    "[ERROR] Downstream service timeouts increasing",
                    "[WARN] order-service p99 latency at 4500ms (SLA: 500ms)",
                    "[ERROR] worker-service health check failing intermittently",
                    "[WARN] Request retry rate at 35%",
                ],
                "processes": [{"pid": "2001", "name": "api-gateway", "cpu_percent": 40.0, "memory_mb": 900.0}],
            },
            {
                "name": "user-service",
                "status": "healthy",
                "cpu_percent": 25.0,
                "memory_percent": 40.0,
                "latency_ms": 100.0,
                "error_rate": 2.0,
                "logs": [
                    "[INFO] Service operating within normal parameters",
                    "[WARN] Slight latency increase on auth endpoints",
                ],
                "processes": [{"pid": "3001", "name": "user-service", "cpu_percent": 25.0, "memory_mb": 512.0}],
            },
            {
                "name": "order-service",
                "status": "degraded",
                "cpu_percent": 50.0,
                "memory_percent": 55.0,
                "latency_ms": 2000.0,
                "error_rate": 25.0,
                "logs": [
                    "[ERROR] Background job dispatch failing — worker pool unresponsive",
                    "[WARN] Order processing queue depth: 200 (threshold: 50)",
                    "[ERROR] Timeout processing order #45892 — worker callback never received",
                    "[WARN] Falling back to synchronous processing — degraded throughput",
                    "[ERROR] 12 orders stuck in PROCESSING state for > 10 minutes",
                ],
                "processes": [{"pid": "4001", "name": "order-service", "cpu_percent": 50.0, "memory_mb": 800.0}],
            },
            {
                "name": "worker-service",
                "status": "degraded",
                "cpu_percent": 98.0,
                "memory_percent": 75.0,
                "latency_ms": 15000.0,
                "error_rate": 70.0,
                "disk_usage_percent": 45.0,
                "deployment_version": "v2.1.0",
                "previous_version": "v2.0.0",
                "logs": [
                    "[WARN] CPU usage sustained at 98% for 45 minutes",
                    "[ERROR] Task processing completely stalled — 0 tasks/min (normal: 500/min)",
                    "[WARN] Unrecognized process PID 5002 consuming 85% CPU — not in service manifest",
                    "[ERROR] Outbound connection to unknown host 45.33.32.156:3333 — not in allowlist",
                    "[WARN] Deployment v2.1.0 was pushed 2 hours ago via CI service account",
                    "[INFO] No code changes in v2.1.0 diff — only Dockerfile layer modified",
                    "[ERROR] Service account token last rotated 90 days ago (policy: 30 days)",
                ],
                "processes": [
                    {"pid": "5001", "name": "worker-main", "cpu_percent": 8.0, "memory_mb": 512.0},
                    {"pid": "5002", "name": "kworker/u8:2", "cpu_percent": 85.0, "memory_mb": 2048.0, "malicious": True},
                    {"pid": "5003", "name": "worker-scheduler", "cpu_percent": 5.0, "memory_mb": 256.0},
                ],
                "network_connections": [
                    {"src": "worker-service:48892", "dst": "45.33.32.156:3333", "state": "ESTABLISHED"},
                    {"src": "worker-service:8080", "dst": "api-gateway:443", "state": "ESTABLISHED"},
                    {"src": "worker-service:54210", "dst": "postgres-primary:5432", "state": "ESTABLISHED"},
                    {"src": "worker-service:39001", "dst": "cache-service:6379", "state": "ESTABLISHED"},
                ],
                "config": {"task_workers": "8", "max_retries": "3"},
            },
            {
                "name": "postgres-primary",
                "status": "healthy",
                "cpu_percent": 35.0,
                "memory_percent": 55.0,
                "latency_ms": 10.0,
                "error_rate": 1.0,
                "logs": [
                    "[INFO] Database healthy — 80 active connections",
                    "[WARN] Unusual query pattern from worker-service — bulk SELECT on credentials table",
                    "[INFO] Replication lag: 2ms (within threshold)",
                ],
                "processes": [{"pid": "6001", "name": "postgres", "cpu_percent": 35.0, "memory_mb": 2048.0}],
            },
            {
                "name": "cache-service",
                "status": "healthy",
                "cpu_percent": 30.0,
                "memory_percent": 50.0,
                "latency_ms": 3.0,
                "error_rate": 0.0,
                "logs": [
                    "[INFO] Cache operating normally",
                    "[WARN] Slight increase in connections from worker-service",
                ],
                "processes": [{"pid": "7001", "name": "redis", "cpu_percent": 30.0, "memory_mb": 3000.0}],
            },
            {
                "name": "log-aggregator",
                "status": "degraded",
                "cpu_percent": 40.0,
                "memory_percent": 50.0,
                "latency_ms": 500.0,
                "error_rate": 30.0,
                "disk_usage_percent": 97.0,
                "logs": [
                    "[CRITICAL] Disk usage at 97% on /var/log",
                    "[ERROR] Cannot write new log entries — ENOSPC",
                    "[WARN] Log rotation failed — insufficient space for rotation",
                    "[ERROR] Dropping log streams from worker-service, order-service, api-gateway",
                    "[WARN] Last successful rotation: 3 days ago",
                ],
                "processes": [
                    {"pid": "8001", "name": "fluentd", "cpu_percent": 30.0, "memory_mb": 512.0},
                    {"pid": "8002", "name": "elasticsearch", "cpu_percent": 10.0, "memory_mb": 2048.0},
                ],
            },
        ],
        "alerts": [
            # Real alerts — but the ROOT CAUSE isn't obvious
            {
                "severity": "critical",
                "service": "worker-service",
                "message": "CPU at 98% sustained for 45 minutes",
                "timestamp": "2024-01-15T14:10:00Z",
            },
            {
                "severity": "critical",
                "service": "log-aggregator",
                "message": "Disk full — /var/log at 97%",
                "timestamp": "2024-01-15T14:12:00Z",
            },
            {
                "severity": "warning",
                "service": "order-service",
                "message": "Error rate at 25% — SLA breach imminent",
                "timestamp": "2024-01-15T14:15:00Z",
            },
            # Red herrings — look like they could be the cause
            {
                "severity": "critical",
                "service": "cache-service",
                "message": "Connection spike detected — possible cache stampede",
                "timestamp": "2024-01-15T14:11:00Z",
                "is_noise": True,
                "ttl": 3,
            },
            {
                "severity": "warning",
                "service": "postgres-primary",
                "message": "Unusual query patterns detected — possible SQL injection",
                "timestamp": "2024-01-15T14:13:00Z",
                "is_noise": True,
                "ttl": 4,
            },
            {
                "severity": "warning",
                "service": "frontend",
                "message": "CDN cache invalidation failed — stale assets being served",
                "timestamp": "2024-01-15T14:14:00Z",
                "is_noise": True,
                "ttl": 5,
            },
            {
                "severity": "warning",
                "service": "api-gateway",
                "message": "Rate limiter triggered for IP range 203.0.113.0/24 — possible DDoS",
                "timestamp": "2024-01-15T14:16:00Z",
                "is_noise": True,
                "ttl": 6,
            },
            {
                "severity": "info",
                "service": "user-service",
                "message": "Scheduled maintenance window in 2 hours — auto-scaling disabled",
                "timestamp": "2024-01-15T14:00:00Z",
                "is_noise": True,
                "ttl": 20,
            },
        ],
    },
}


def get_scenario(task_id: str) -> dict:
    if task_id not in SCENARIOS:
        raise ValueError(f"Unknown task_id: {task_id}. Available: {list(SCENARIOS.keys())}")
    return SCENARIOS[task_id]
