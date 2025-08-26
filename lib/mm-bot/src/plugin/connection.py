import asyncio
import logging
from plugin.requests.base_request import BaseRequest
from plugin.responses.base_response import BaseResponse
from plugin.request_parser import RequestParser
from plugin.response_builder import ResponseBuilder
from plugin.responses.error import ErrorResponse


class PluginConnection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer
        self._tm_account_id = ""

    def identifier(self) -> str:
        return self._tm_account_id

    async def read_command(self) -> bool:
        send_error = False

        try:
            buffer = (await self._reader.readline()).decode()
            if not buffer or not buffer.strip():
                return True

            read_length = int(buffer)
            if read_length <= 0:
                logging.info(
                    f"Invalid command received from {self._writer.transport.get_extra_info('peername')}. Disconnecting."
                )
                send_error = True
                return True

            byte_buffer = await asyncio.wait_for(
                self._reader.readexactly(read_length), 610
            )
            buffer = byte_buffer.decode()

            request: BaseRequest = RequestParser().from_buffer(buffer)
            if not request:
                logging.info(
                    f"Unable to parse command from {self._writer.transport.get_extra_info('peername')}. Disconnecting."
                )
                send_error = True
                return True

            self._tm_account_id = request.identifier()

            builder = ResponseBuilder()
            response: BaseResponse = await builder.build_response(request)
            await self.send_command(response)

            return False

        except asyncio.TimeoutError as timeout_exception:
            logging.exception(
                f"Reading command from {self._writer.transport.get_extra_info('peername')} timed out",
                timeout_exception,
            )
            send_error = True
            return True

        except Exception as e:
            logging.exception(
                f"An exception occurred processing command for {self._writer.transport.get_extra_info('peername')}",
                e,
            )
            send_error = True
            return True

        finally:
            if send_error:
                await self.try_send_error()

    async def send_command(self, command: BaseResponse):
        self._writer.write(b"%d\n" % command.length())
        self._writer.write(command.encode())
        await self._writer.drain()

    async def try_send_error(
        self, error_message: str = "An error occurred processing request"
    ):
        try:
            error = ErrorResponse(error_message, False)
            await self.send_command(error)
        except Exception:
            pass
