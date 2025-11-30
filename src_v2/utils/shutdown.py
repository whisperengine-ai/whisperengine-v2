import signal
import asyncio
from loguru import logger
from typing import List, Callable, Awaitable, Optional

class GracefulShutdown:
    def __init__(self):
        self.shutdown_event: Optional[asyncio.Event] = None
        self._cleanup_tasks: List[Callable[[], Awaitable[None]]] = []
        self._signal_received = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, sig, frame):
        """Handle shutdown signals in a thread-safe manner."""
        if self._signal_received:
            # Second signal - force exit
            logger.warning("Second shutdown signal received, forcing exit...")
            import sys
            sys.exit(1)
        
        self._signal_received = True
        logger.info(f"Received shutdown signal: {signal.Signals(sig).name}")
        
        # Schedule the shutdown event to be set in the event loop
        if self.shutdown_event:
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self.shutdown_event.set)
            except RuntimeError:
                # No running loop - we'll catch this in wait_for_shutdown_signal
                pass

    def add_cleanup_task(self, task: Callable[[], Awaitable[None]]):
        """Add an async cleanup task to be run on shutdown."""
        self._cleanup_tasks.append(task)

    async def wait_for_shutdown_signal(self):
        """Wait until a shutdown signal is received."""
        # Create the event in the current running loop context
        if self.shutdown_event is None:
            self.shutdown_event = asyncio.Event()
        
        # Check if signal was already received before we started waiting
        if self._signal_received:
            self.shutdown_event.set()
        
        await self.shutdown_event.wait()
        logger.info("Shutdown signal received. Starting cleanup...")
        await self._execute_cleanup()

    async def _execute_cleanup(self):
        """Execute all registered cleanup tasks."""
        if not self._cleanup_tasks:
            logger.info("No cleanup tasks registered.")
            return

        logger.info(f"Executing {len(self._cleanup_tasks)} cleanup tasks...")
        
        results = await asyncio.gather(
            *[task() for task in self._cleanup_tasks], 
            return_exceptions=True
        )
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Cleanup task {i+1} failed: {result}")
            else:
                logger.info(f"Cleanup task {i+1} completed successfully.")
        
        logger.info("Cleanup completed.")

# Global instance
shutdown_handler = GracefulShutdown()
