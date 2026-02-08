# Event-Driven Architecture

## Overview
We have moved from a simple request-response model to an event-driven system. This allows agents to react to changes in the environment (like a task completing) without blocking the user.

## Components

### 1. Domain Models (`src/domain/`)
- **Task**: The core unit of work. Has status (TODO, IN_PROGRESS, DONE, etc.), priority, and dependencies.
- **Event**: A typed message containing a payload and source.

### 2. Infrastructure (`src/infrastructure/`)
- **EventBus**: A singleton pub/sub system. 
  - `publish(event)`: Fires and forgets (async).
  - `subscribe(event_type, callback)`: Listeners run in background tasks.

### 3. Services (`src/services/`)
- **TaskStore**: The source of truth for tasks.
  - CRUD operations backed by `tasks/tasks.json` (for now).
  - **Automatically publishes events** when tasks change.

## Flow
1. User asks Main Agent to "Add task".
2. Main Agent calls `task_store.add_task()`.
3. TaskStore saves to disk AND calls `event_bus.publish(TASK_CREATED)`.
4. Any subscribed agents (like PlanManager) wake up in the background to handle the event.

## Future Usage
- **PlanManagerAgent**: Will listen for `TASK_COMPLETED` to unblock dependent tasks.
- **NotificationSystem**: Will listen for `PLAN_COMPLETED` to alert the user.
