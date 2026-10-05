from .provider import Supplier
from .socket_ import _Socket
from .context import _Context, MagicKey
from .route import Blueprint
from .msg import ResponseMessage, RequestMessage
from logging import Logger

def log(logger: Logger, message: RequestMessage, res:ResponseMessage):
    logger.info(f"{message.cmd} - {res.status_code}")

async def process_msg(blueprint: Blueprint, context: _Context, socket: _Socket, logger: Logger, supplier: Supplier):
    await context.refresh()

    message = await socket.receive()

    context.short[MagicKey("message")] = message

    res = await blueprint.get_chain(message.cmd)(context, supplier, message)

    await socket.response(res)

    log(logger, message, res)