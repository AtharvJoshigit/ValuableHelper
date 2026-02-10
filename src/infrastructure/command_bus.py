import asyncio
from src.domain.event import Event

class CommandBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Do NOT create asyncio.Queue() here. 
            # It will bind to the wrong loop (or no loop) on import.
            cls._instance._queue = None 
        return cls._instance

    @property
    def queue(self):
        # Lazy initialization ensures the Queue attaches to the CURRENT running loop
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue

    async def send(self, event: Event):
        # print(f"Event: {event.type}") # Optional logging
        await self.queue.put(event)

    async def receive(self) -> Event:
        return await self.queue.get()