import logging
from domain.event import Event, EventType
from app.app_context import get_app_context
from infrastructure.websocket_manager import get_websocket_manager

logger = logging.getLogger(__name__)

class ObservabilityService:
    """
    Broadcasts system events to the frontend via WebSockets.
    Uses lazy initialization to avoid startup-order issues.
    """

    def __init__(self):
        self._event_bus = None
        self._ws_manager = None
        self._started = False
        logger.info("ObservabilityService created (lazy)")

    # ---------- Lazy dependencies ----------

    @property
    def event_bus(self):
        if self._event_bus is None:
            self._event_bus = get_app_context().event_bus
        return self._event_bus

    @property
    def ws_manager(self):
        if self._ws_manager is None:
            self._ws_manager = get_websocket_manager()
        return self._ws_manager

    # ---------- Lifecycle ----------

    def start(self):
        """
        Explicit startup hook.
        Safe to call multiple times.
        """
        if self._started:
            return

        self._subscribe_events()
        self._started = True
        logger.info("ObservabilityService started")

    # ---------- Subscriptions ----------

    def _subscribe_events(self):
        self.event_bus.subscribe(
            EventType.TOOL_EXECUTION_STARTED, self._handle_tool_start
        )
        self.event_bus.subscribe(
            EventType.TOOL_EXECUTION_COMPLETED, self._handle_tool_complete
        )
        self.event_bus.subscribe(
            EventType.TOOL_EXECUTION_FAILED, self._handle_tool_failed
        )
        self.event_bus.subscribe(
            EventType.TASK_CREATED, self._handle_task_event
        )
        self.event_bus.subscribe(
            EventType.TASK_STATUS_CHANGED, self._handle_task_event
        )

    # ---------- Handlers ----------

    async def _handle_tool_start(self, event: Event):
        # logger.info(f"👀 ObservabilityService: Received START event for {event.payload.get('tool_name')}")
        
        # 1. Send specific event for UI State Machine (Face reaction)
        await self.ws_manager.broadcast({
            "type": "tool_execution_started",
            "payload": {
                "agent_id": event.payload.get("agent_id"),
                "tool_name": event.payload.get("tool_name"),
                "arguments": event.payload.get("arguments")
            }
        })

        # 2. Send log entry for the console/history
        await self.ws_manager.broadcast({
            "type": "log",
            "level": "info",
            "source": "ToolExecutor",
            "agent_id": event.payload.get("agent_id"),
            "message": f"🛠️ Executing {event.payload.get('tool_name')}...",
            "details": event.payload.get("arguments"),
        })

    async def _handle_tool_complete(self, event: Event):
        # 1. State update
        await self.ws_manager.broadcast({
            "type": "tool_execution_completed",
            "payload": {
                "agent_id": event.payload.get("agent_id"),
                "tool_name": event.payload.get("tool_name"),
                "result": event.payload.get("result")
            }
        })

        # 2. Log update
        await self.ws_manager.broadcast({
            "type": "log",
            "level": "success",
            "source": "ToolExecutor",
            "agent_id": event.payload.get("agent_id"),
            "message": f"✅ {event.payload.get('tool_name')} finished.",
            "details": event.payload.get("result"),
        })

    async def _handle_tool_failed(self, event: Event):
        # 1. State update
        await self.ws_manager.broadcast({
            "type": "tool_execution_failed",
            "payload": {
                "agent_id": event.payload.get("agent_id"),
                "tool_name": event.payload.get("tool_name"),
                "error": event.payload.get("error")
            }
        })

        # 2. Log update
        await self.ws_manager.broadcast({
            "type": "log",
            "level": "error",
            "source": "ToolExecutor",
            "agent_id": event.payload.get("agent_id"),
            "message": f"❌ {event.payload.get('tool_name')} failed.",
            "details": event.payload.get("error"),
        })

    async def _handle_task_event(self, event: Event):
        await self.ws_manager.broadcast({
            "type": "log",
            "level": "info",
            "source": "TaskManager",
            "agent_id": event.payload.get("agent_id"),
            "message": f"📋 {event.type}: {event.payload.get('task_id')}",
            "details": event.payload,
        })
