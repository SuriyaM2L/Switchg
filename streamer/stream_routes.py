# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/routes.py>
# Thanks to Eyaadh <https://github.com/eyaadh>

import pyrogram
import re
import time, asyncio, json
import math
import logging
from random import choice
from streamer import utils
from pyrogram.errors import (
    FileIdInvalid,
    FileReferenceEmpty,
    FileReferenceExpired,
    FilerefUpgradeNeeded,
)

from os import getenv
import mimetypes
from aiohttp.web import Request
from typing import Union
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from base64 import b16decode
from streamer.exceptions import *
from streamer.utils.constants import work_loads, multi_clients
from database.ia_filterdb import get_file_details, decode_file_ref

from pyrogram.file_id import FileId

logger = logging.getLogger("routes")
StartTime = time.time()

routes = web.RouteTableDef()


@routes.get("/", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running",
            "uptime": utils.get_readable_time(time.time() - StartTime),
            "loads": dict(
                ("bot" + str(c + 1), l)
                for c, (_, l) in enumerate(
                    sorted(work_loads.items(), key=lambda x: x[1], reverse=True)
                )
            ),
        }
    )


@routes.get(r"/stream", allow_head=True)
async def stream_handler(request: web.Request):
    return await __stream_handler(request)


@routes.get(r"/thumb", allow_head=True)
async def stream_handler(request: web.Request):
    return await __stream_handler(request, True)


async def __stream_handler(request: web.Request, thumb=False):
    try:
        channel, messageId = None, None
        file_id = request.query.get("fileId")

        hash = request.query.get("hash")
        if hash:
            channel, message = b16decode(hash.encode()).decode().split(":")
            try:
                channel = int(channel)
            except Exception:
                pass
            messageId = int(message)
        #            print(channel, message)
        elif not file_id:
            channel = request.query.get("channel")
            try:
                channel = int(channel)
            except Exception as er:
                pass
            messageId = int(request.query.get("messageId"))
        return await media_streamer(request, channel, messageId, thumb, file_id)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:

        logger.critical(str(e), exc_info=True)
        raise web.HTTPInternalServerError(text=str(e))


class_cache = {}
fileHolder = {}


async def media_streamer(
    request: web.Request,
    channel: Union[str, int],
    message_id: int,
    thumb: bool = False,
    file_id: str = None,
):
    from tclient import tgclient as bot

    range_header = request.headers.get("Range", 0)

    index = min(work_loads, key=work_loads.get)
    if not class_cache.get(0):
        class_cache[0] = utils.ByteStreamer(bot)

    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]

    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
        logger.debug(f"Using cached ByteStreamer object for client {index}")
    else:
        logger.debug(f"Creating new ByteStreamer object for client {index}")
        tg_connect = utils.ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect

    details = None
    tagId = file_id
    if channel and message_id:
        tagId = f"{channel}:{message_id}"

    if tagId in fileHolder:
        file_id = fileHolder[tagId]
    else:
        if file_id:
            details = await get_file_details(file_id)
            if not details:
                return web.json_response({"ok": False, "message": "File not found"})
            file_id = details[0]
            if file_id["message_id"]:
                message_id = int(file_id["message_id"])
                channel = int(file_id["chat_id"])
            else:
                web.json_response({"ok": False, "message": "Invalid file_id"})
                return

        if message_id and channel:
            try:
                print(channel, message_id)
                msg = await faster_client.get_messages(
                    int(channel), message_ids=message_id
                )
                assert msg != None
            except Exception as er:
                logger.info(f"check tgbot access: {er}")
                return web.json_response({"message": str(er), "ok": False})

            logger.debug("before calling get_file_properties")

            file_id = await tg_connect.get_file_properties(channel, message_id, thumb)
            print(file_id, thumb)
            logger.debug("after calling get_file_properties")

        elif not file_id:
            return web.json_response({"ok": False, "message": "Invalid request"})
        #    if utils.get_hash(file_id.unique_id, 7) != secure_hash:
        #       logger.debug(f"Invalid hash for message with ID {message_id}")
        #      raise InvalidHash
        fileHolder[tagId] = file_id

    file_size = file_id.file_size

    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = (request.http_range.stop or file_size) - 1

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = 1024 * 1024
    until_bytes = min(until_bytes, file_size - 1)

    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1

    req_length = until_bytes - from_bytes + 1
    part_count = math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size)
    
    def on_new_fileid(fileId):
        fileHolder[tagId] = fileId

    body = tg_connect.yield_file(
        file_id,
        index,
        offset,
        first_part_cut,
        last_part_cut,
        part_count,
        chunk_size,
        channel_id=channel,
        message_id=message_id,
        on_new_fileId=on_new_fileid
    )
    mime_type = file_id.mime_type
    file_name = utils.get_name(file_id)

    print(file_name, mime_type, file_id)
    disposition = "attachment"

    if not mime_type:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    if "video/" in mime_type or "audio/" in mime_type or "/html" in mime_type:
        disposition = "inline"

    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": str(mime_type),
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(req_length),
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        },
    )


APP_AUTH_TOKEN = getenv("APP_AUTH_TOKEN", "")


def notVerified(request: Request):
    headers = request.headers
    if APP_AUTH_TOKEN and headers.get("Authorization") != APP_AUTH_TOKEN:
        return web.json_response({"ok": False, "message": "UNAUTHORIZED"})
    return


@routes.get("/messageInfo")
async def getMessage(request: Request):
    if notVerified(request):
        return

    clients = multi_clients
    bot = choice(list(clients.values()))

    channel = request.query.get("channel")
    try:
        msgId = int(request.query.get("messageId"))
    except Exception:
        return web.json_response({"ok": False, "message": "INVALID_RESPONSE"})
    try:
        channel = int(channel)
    except Exception:
        pass
    message = await bot.get_messages(chat_id=channel, message_ids=msgId)
    return web.json_response(json.loads(str(message)))
