# System Knowledge: The Heartbeat & Resurrection System

**Created:** February 24, 2026
**Status:** Active

## Overview
The Heartbeat System ensures ValH remains responsive and proactive. It consists of three decoupled components working in unison to prevent "zombie" states (process running but unresponsive) and enable scheduled self-maintenance.

## Architecture

### 1. The Pulse (Internal Trigger)
*   **Component:** `HeartbeatService` (`src/services/heartbeat_service.py`)
*   **Function:** A background asyncio task that wakes up every **30 minutes**.
*   **Mechanism:** Publishes a `HEARTBEAT` event to the `CommandBus`.
*   **Payload:** `{"instruction": "Perform system health check", "timestamp": ...}`
*   **Decoupling:** The service does not know *who* listens. It simply pulses.

### 2. The Brain (Internal Processor)
*   **Component:** `MainAgent` (`src/agents/main_agent.py`)
*   **Function:** Subscribes to `HEARTBEAT` events.
*   **Mechanism:**
    *   Routes the event to a dedicated **System Chat Session (ID: 0)**.
    *   Treats the payload instruction as a prompt.
    *   Executes reasoning or tools (e.g., checking logs, summarizing memory) without user intervention.
    *   Logs the output to `valh.log` instead of sending a Telegram message.

### 3. The Watchdog (External Monitor)
*   **Component:** `resurrector.py`
*   **Function:** Ensures the application is alive and responsive.
*   **Mechanism:**
    *   **Active Polling:** Pings `http://localhost:8000/health` every **30 seconds**.
    *   **Logic:**
        *   **200 OK:** System is healthy.
        *   **Connection Refused / Timeout:** System is down or frozen.
    *   **Recovery:** If 3 consecutive checks fail (90s total), it **force kills** and restarts the `main.py` process.

## Configuration
*   **Heartbeat Interval:** Hardcoded to 1800s (30m) in `main.py` (can be moved to env).
*   **Watchdog Interval:** 30s in `resurrector.py`.
*   **Watchdog Threshold:** 3 failures.

## Debugging
*   **Logs:** Check `valh.log` for `💓 Processing Heartbeat` entries.
*   **Health Check:** Visit `http://localhost:8000/health` in a browser to verify status.
*   **Manual Trigger:** You can manually publish a `HEARTBEAT` event via code to test the agent's response.
