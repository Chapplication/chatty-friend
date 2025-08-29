from typing import Callable, Any
import asyncio
from chatty_config import NUM_INCOMING_AUDIO_BUFFERS

class AsyncManager:
    """ Context for an async task.  manages an input queue for incoming work, an output queue for results that go to the next worker and
    a command queue for external control of the task.  Passed to the task as a parameter when kicked off"""
    def __init__(self, name: str, task_function: Callable, input_q: asyncio.Queue[bytes] = None, kwargs: dict = {}):
        self.name = name
        self.task_function = task_function

        # management commands to the task
        self.command_q :asyncio.Queue[str] = asyncio.Queue()

        # events raised from the task
        self.event_q :asyncio.Queue[str] = asyncio.Queue()

        # input and output buffers.  Create the output queue but use an
        # incoming input queue from another manager if provided.
        # override buffer size for speaker to handle long incoming audio streams
        self.output_q :asyncio.Queue[Any] = asyncio.Queue(maxsize=100 if name != "speaker" else NUM_INCOMING_AUDIO_BUFFERS)
        self.input_q :asyncio.Queue[Any] = input_q if input_q else asyncio.Queue(maxsize=2000)

        # allow arbitrary kwargs
        self.kwargs = kwargs
        for k,v in kwargs.items():
            setattr(self, k, v)

    def start(self, master_state):
        # start the task
        self.master_state = master_state
        self.task = asyncio.create_task(self.task_function(self, **self.kwargs))

    async def wait_for_done(self):
        await self.task

    async def wait_and_dispatch(self) -> list[tuple[str, Any]]:
        # wait on the input queue and the command queue.  return the first one that completes.
        command_task = asyncio.create_task(self.command_q.get())
        input_task = asyncio.create_task(self.input_q.get())

        # Wait for the first task to complete (i.e., get an item from either queue)
        done, pending = await asyncio.wait(
            [command_task, input_task],
            return_when=asyncio.FIRST_COMPLETED, 
            timeout = 1
        )

        # Process the result from the completed task
        results = []
        for task in done:
            task_exception = task.exception()
            if task_exception:
                print(f"❌ Error in {self.name} queue: {task_exception}")

            if task is command_task:
                results.append(("command", task.result()))
            elif task is input_task:
                results.append(("input", task.result()))

        # close unused waits
        for task in pending:
            task.cancel()

        return results

