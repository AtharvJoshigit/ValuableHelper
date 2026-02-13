import asyncio
from src.domain.event import Event

class CommandBus:
    _instances = {}

    def __new__(cls):
        loop = asyncio.get_running_loop()
        if loop not in cls._instances:
            instance = super().__new__(cls)
            instance._queue = asyncio.Queue()
            cls._instances[loop] = instance
        return cls._instances[loop]

    # @property
    # def queue(self):
    #     # Lazy initialization ensures the Queue attaches to the CURRENT running loop
    #     if self._queue is None:
    #         self._queue = asyncio.Queue()
    #     return self._queue

    async def send(self, event: Event):
        # print(f"Event: {event.type}") # Optional logging
        await self._queue.put(event)

    async def receive(self) -> Event:
        return await self._queue.get()