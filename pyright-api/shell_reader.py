"""This utility was sourced from scarletcafe in their [Jishaku](https://github.com/scarletcafe/jishaku) repository, it's license can be found below.

MIT License

Copyright (c) 2024 Devon (scarletcafe) R

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import re
import subprocess
import sys
import time
from typing import IO, TYPE_CHECKING, Any, ParamSpec, Self, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")
P = ParamSpec("P")


SHELL = os.getenv("SHELL") or "/bin/bash"
WINDOWS = sys.platform == "win32"


def background_reader(stream: IO[bytes], loop: asyncio.AbstractEventLoop, callback: Callable[[bytes], Any]) -> None:
    """
    Reads a stream and forwards each line to an async callback.
    """

    for line in iter(stream.readline, b""):
        loop.call_soon_threadsafe(loop.create_task, callback(line))


class ShellReader:
    """
    A class that passively reads from a shell and buffers results for read.

    Example
    -------

    .. code:: python3

        # reader should be in a with statement to ensure it is properly closed
        with ShellReader('echo one; sleep 5; echo two') as reader:
            # prints 'one', then 'two' after 5 seconds
            async for x in reader:
                print(x)
    """

    def __init__(
        self, code: str, /, *, timeout: int = 120, loop: asyncio.AbstractEventLoop | None = None, escape_ansi: bool = True
    ) -> None:
        if WINDOWS:
            # Check for powershell
            if pathlib.Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe").exists():
                sequence = ["powershell", code]
                self.ps1 = "PS >"
                self.highlight = "powershell"
            else:
                sequence = ["cmd", "/c", code]
                self.ps1 = "cmd >"
                self.highlight = "cmd"
            # Windows doesn't use ANSI codes
            self.escape_ansi = True

            self.process = subprocess.Popen(  # pylint: disable=consider-using-with
                sequence, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            self.stdin = self.process.stdin
            self.stdout = self.process.stdout
        else:
            import pty  # pylint: disable=import-outside-toplevel

            sequence = [SHELL, "-c", code]
            self.ps1 = "$"
            self.highlight = "ansi"
            self.escape_ansi = escape_ansi

            master_in, slave_in = pty.openpty()
            self.process = subprocess.Popen(  # pylint: disable=consider-using-with
                sequence, stdin=slave_in, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.stdin = os.fdopen(master_in, "wb")
            self.stdout = self.process.stdout

        self.close_code = None

        self.loop = loop or asyncio.get_event_loop()
        self.timeout = timeout

        assert self.stdout
        self.stdout_task = self.make_reader_task(self.stdout, self.stdout_handler) if self.process.stdout else None
        self.stderr_task = self.make_reader_task(self.process.stderr, self.stderr_handler) if self.process.stderr else None

        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=250)

    @property
    def closed(self) -> bool:
        """
        Are both tasks done, indicating there is no more to read?
        """

        return (not self.stdout_task or self.stdout_task.done()) and (not self.stderr_task or self.stderr_task.done())

    async def executor_wrapper(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """
        Call wrapper for stream reader.
        """

        return await asyncio.to_thread(func, *args, **kwargs)

    def make_reader_task(self, stream: IO[bytes], callback: Callable[[bytes], Any]) -> asyncio.Task[None]:
        """
        Create a reader executor task for a stream.
        """

        return self.loop.create_task(self.executor_wrapper(background_reader, stream, self.loop, callback))

    ANSI_ESCAPE_CODE = re.compile(r"\x1b\[\??(\d*)(?:([ABCDEFGJKSThilmnsu])|;(\d+)([fH]))")

    def clean_bytes(self, line: bytes) -> str:
        """
        Cleans a byte sequence of shell directives and decodes it.
        """

        text = line.decode("utf-8").replace("\r", "").strip("\n")

        def sub(group: re.Match[str]) -> str:
            return group.group(0) if group.group(2) == "m" and not self.escape_ansi else ""

        return self.ANSI_ESCAPE_CODE.sub(sub, text).replace("``", "`\u200b`").strip("\n")

    async def stdout_handler(self, line: bytes) -> None:
        """
        Handler for this class for stdout.
        """

        await self.queue.put(self.clean_bytes(line))

    async def stderr_handler(self, line: bytes) -> None:
        """
        Handler for this class for stderr.
        """

        await self.queue.put(self.clean_bytes(b"[stderr] " + line))

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: Any) -> None:
        self.process.kill()
        self.process.terminate()
        self.close_code = self.process.wait(timeout=0.5)

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> str:
        last_output = time.perf_counter()

        while not self.closed or not self.queue.empty():
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=1)
            except TimeoutError as exception:
                if time.perf_counter() - last_output >= self.timeout:
                    raise exception
            else:
                last_output = time.perf_counter()
                return item

        raise StopAsyncIteration()

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> str:
        try:
            item = self.queue.get_nowait()
        except asyncio.QueueEmpty as exception:
            raise StopIteration() from exception

        return item
