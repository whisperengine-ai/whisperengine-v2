# PRD-007: System Scalability & Observability

**Status:** ✅ Implemented
**Owner:** Mark Castillo
**Created:** December 4, 2025
**Updated:** December 4, 2025

## Origin

> **How did this need emerge?** As we added more autonomous features (lurking, dreaming, enrichment), the system load increased. We needed better ways to manage background tasks and understand performance bottlenecks.

| Field | Value |
|-------|-------|
| **Origin** | Engineering Necessity |
| **Proposed by** | Mark Castillo |
| **Catalyst** | Need to run expensive background jobs (dreams, enrichment) without slowing down chat responses |

## Problem Statement
A single-threaded or simple synchronous bot cannot handle:
- Long-running tasks (generating a dream takes 30s+).
- Bursty traffic (multiple users chatting at once).
- Complex background analysis (graph enrichment).
Without a robust queue and metrics, the bot becomes unresponsive or crashes under load.

## User Stories
1.  **As a user**, I want the bot to respond quickly to my chat, even if it's thinking about a dream in the background.
2.  **As a developer**, I want to know *why* a response was slow (LLM latency vs. DB lock vs. Queue wait).
3.  **As a developer**, I want to prioritize "chat" tasks over "dream" tasks so users never wait.
4.  **As a developer**, I want to see trends in token usage and costs over time.

## Functional Requirements

### 1. Advanced Task Queue
- **Requirement:** Asynchronous job processing with priorities.
- **Mechanism:** `arq` (Redis-based) with separate queues for `cognition` (high priority), `social`, `sensory`, and `background` (low priority).
- **Features:** Retries, scheduled jobs, job cancellation.
- **Roadmap Item:** **E24**

### 2. Metrics & Analytics
- **Requirement:** Real-time visibility into system performance.
- **Mechanism:** InfluxDB for time-series data + Grafana for visualization.
- **Metrics:** Latency, token usage, queue depth, error rates, sentiment trends.
- **Roadmap Item:** **O1**

### 3. Worker Scaling
- **Requirement:** Ability to add more processing power without changing code.
- **Mechanism:** Docker Compose scaling for worker containers.

## Success Metrics
- **P99 Latency:** 99th percentile response time should be < 5 seconds.
- **Uptime:** 99.9% availability.
- **Queue Clearance:** Background queues should clear within X minutes during off-peak hours.

## Privacy & Safety
- **Data Retention:** Metrics data should be retained for a limited time (e.g., 30 days) or aggregated.
- **PII:** Logs and metrics must not contain Personally Identifiable Information (PII) or message content.
