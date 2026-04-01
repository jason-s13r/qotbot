import asyncio
import logging
import traceback
from datetime import datetime, timezone

from qotbot.database.database import get_log_session
from qotbot.database.models.log import Log


class SQLiteHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            log_data = self.format(record)
            exc_info = (
                "".join(traceback.format_exception(*record.exc_info))
                if record.exc_info
                else None
            )

            try:
                loop = asyncio.get_running_loop()
                if not loop.is_closed():
                    loop.create_task(
                        self._async_insert_log(
                            timestamp=datetime.fromtimestamp(
                                record.created, tz=timezone.utc
                            ),
                            level=record.levelname,
                            logger=record.name,
                            message=log_data,
                            module=record.module,
                            function=record.funcName,
                            line=record.lineno,
                            exc_info=exc_info,
                        )
                    )
            except RuntimeError:
                try:
                    asyncio.run(
                        self._async_insert_log(
                            timestamp=datetime.fromtimestamp(
                                record.created, tz=timezone.utc
                            ),
                            level=record.levelname,
                            logger=record.name,
                            message=log_data,
                            module=record.module,
                            function=record.funcName,
                            line=record.lineno,
                            exc_info=exc_info,
                        )
                    )
                except RuntimeError:
                    pass
        except Exception:
            self.handleError(record)

    async def _async_insert_log(
        self,
        timestamp: datetime,
        level: str,
        logger: str,
        message: str,
        module: str | None = None,
        function: str | None = None,
        line: int | None = None,
        exc_info: str | None = None,
    ):
        async with get_log_session() as session:
            log_entry = Log(
                timestamp=timestamp,
                level=level,
                logger=logger,
                message=message,
                module=module,
                function=function,
                line=line,
                exc_info=exc_info,
            )
            session.add(log_entry)
            await session.commit()

    def close(self):
        super().close()
