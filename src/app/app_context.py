
from infrastructure.command_bus import CommandBus
from infrastructure.event_bus import EventBus



class AppContext:
    def __init__(self):
        self.command_bus = CommandBus()
        self.event_bus = EventBus()

_app_context: AppContext | None = None

def set_app_context(ctx: AppContext) -> None:
    global _app_context
    _app_context = ctx

def get_app_context() -> AppContext:
    if _app_context is None:
        raise RuntimeError("AppContext not initialized")
    return _app_context