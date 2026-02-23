import logging
from domain.event import Event, EventType
from app.app_context import get_app_context
from infrastructure.websocket_manager import get_websocket_manager
from services.response_manager import ResponseManager

logger = logging.getLogger(__name__)

class ObservabilityService:
    """
    Broadcasts system events to the frontend via WebSockets and 
    updates the Telegram status dashboard.
    """

    def __init__(self):
        self._event_bus = None
        self._ws_manager = None
        self._response_manager = None
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

    @property
    def response_manager(self):
        """Lazy load response manager to avoid circular imports"""
        if self._response_manager is None:
            # This assumes ResponseManager is accessible via some global or context
            # For now, we'll try to get it from the app context if registered, 
            # or we might need to pass it in.
            from app.app_context import get_app_context
            # Assuming MainAgent or similar registered it
            pass 
        return self._response_manager

    def set_response_manager(self, manager):
        self._response_manager = manager

    # ---------- Lifecycle ----------

    def start(self):
        if self._started:
            return
        self._subscribe_events()
        self._started = True
        logger.info("ObservabilityService started")

    # ---------- Subscriptions ----------

    def _subscribe_events(self):
        self.event_bus.subscribe(EventType.TOOL_EXECUTION_STARTED, self._handle_tool_start)
        self.event_bus.subscribe(EventType.TOOL_EXECUTION_COMPLETED, self._handle_tool_complete)
        self.event_bus.subscribe(EventType.TOOL_EXECUTION_FAILED, self._handle_tool_failed)
        self.event_bus.subscribe(EventType.TASK_CREATED, self._handle_task_event)
        self.event_bus.subscribe(EventType.TASK_STATUS_CHANGED, self._handle_task_event)

    # ---------- Handlers ----------

    async def _handle_tool_start(self, event: Event):
        agent_id = event.payload.get("agent_id")
        tool_name = event.payload.get("tool_name")
        args = event.payload.get("arguments")
        
        # 1. WebUI Update
        await self.ws_manager.broadcast({
            "type": "tool_execution_started",
            "payload": {"agent_id": agent_id, "tool_name": tool_name, "arguments": args}
        })

        # 2. Telegram Dashboard Update
        if self._response_manager and agent_id and "chat_" in str(agent_id):
            try:
                chat_id = int(str(agent_id).split("_")[-1])
                await self._response_manager.update_status(chat_id, f"🔧 Using {tool_name}...", "telegram")
            except Exception as e:
                logger.error(f"Failed to update telegram status from observability: {e}")

    async def _handle_tool_complete(self, event: Event):
        agent_id = event.payload.get("agent_id")
        tool_name = event.payload.get("tool_name")
        
        # 1. WebUI Update
        await self.ws_manager.broadcast({
            "type": "tool_execution_completed",
            "payload": {"agent_id": agent_id, "tool_name": tool_name}
        })

        # 2. Telegram Dashboard Update
        if self._response_manager and agent_id and "chat_" in str(agent_id):
            try:
                chat_id = int(str(agent_id).split("_")[-1])
                await self._response_manager.update_status(chat_id, "🤔 Thinking...", "telegram")
            except Exception as e:
                logger.error(f"Failed to update telegram status from observability: {e}")

    async def _handle_tool_failed(self, event: Event):
        agent_id = event.payload.get("agent_id")
        tool_name = event.payload.get("tool_name")
        error = event.payload.get("error")

        # 1. WebUI Update
        await self.ws_manager.broadcast({
            "type": "tool_execution_failed",
            "payload": {"agent_id": agent_id, "tool_name": tool_name, "error": error}
        })

        # 2. Telegram Dashboard Update
        if self._response_manager and agent_id and "chat_" in str(agent_id):
            try:
                chat_id = int(str(agent_id).split("_")[-1])
                await self._response_manager.update_status(chat_id, f"❌ {tool_name} failed", "telegram")
            except Exception as e:
                logger.error(f"Failed to update telegram status from observability: {e}")

    async def _handle_task_event(self, event: Event):
        await self.ws_manager.broadcast({
            "type": "log",
            "level": "info",
            "source": "TaskManager",
            "message": f"📋 {event.type}: {event.payload.get('task_id')}",
        })
