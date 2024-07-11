import math
import asyncio
import logging
import time
from typing import Dict, Union
from pyrogram import Client, utils, raw
from .constants import work_loads
from .file_properties import get_file_ids
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid
from streamer.exceptions import FIleNotFound
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.errors import (
    FilerefUpgradeNeeded,
    FileReferenceEmpty,
    FileReferenceInvalid,
    FileReferenceExpired,
    FileIdInvalid,
)

logger = logging.getLogger("streamer")


class ByteStreamer:
    def __init__(self, client: Client):
        """A custom class that holds the cache of a specific client and class functions.
        attributes:
            client: the client that the cache is for.
            cached_file_ids: a dict of cached file IDs.
            cached_file_properties: a dict of cached file properties.

        functions:
            generate_file_properties: returns the properties for a media of a specific message contained in Tuple.
            generate_media_session: returns the media session for the DC that contains the media file.
            yield_file: yield a file from telegram servers for streaming.

        This is a modified version of the <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/telegram/utils/custom_download.py>
        Thanks to Eyaadh <https://github.com/eyaadh>
        """
        self.clean_timer = 30 * 60
        self.client: Client = client
        self.cached_file_ids: Dict[int, FileId] = {}
        asyncio.create_task(self.clean_cache())

    async def get_file_properties(
        self, channel: str, message_id: int, thumb: bool = False
    ) -> FileId:
        """
        Returns the properties of a media of a specific message in a FIleId class.
        if the properties are cached, then it'll return the cached results.
        or it'll generate the properties from the Message ID and cache them.
        """
        tag = "thumb" if thumb else "file"
        if not self.cached_file_ids.get(channel):
            self.cached_file_ids[channel] = {}
        if not self.cached_file_ids[channel].get(message_id, {}).get(tag):
            await self.generate_file_properties(channel, message_id, thumb=thumb)
            logger.debug(f"Cached file properties for message with ID {message_id}")
        return self.cached_file_ids[channel][message_id][tag]

    async def generate_file_properties(
        self, channel: str, message_id: int, thumb: bool = False
    ) -> FileId:
        """
        Generates the properties of a media file on a specific message.
        returns ths properties in a FIleId class.
        """
        file_id = await get_file_ids(self.client, channel, message_id, thumb=thumb)
        logger.debug(
            f"Generated file ID and Unique ID for message with ID {message_id}"
        )
        if not file_id:
            logger.debug(f"Message with ID {message_id} not found")

            raise FIleNotFound
        if not self.cached_file_ids.get(channel):
            self.cached_file_ids[channel] = {}
        if not self.cached_file_ids[channel].get(message_id):
            self.cached_file_ids[channel][message_id] = {}
        tag = "thumb" if thumb else "file"
        self.cached_file_ids[channel][message_id][tag] = file_id
        logger.debug(f"Cached media message with ID {message_id}")
        return self.cached_file_ids[channel][message_id][tag]

    async def generate_media_session(self, client: Client, file_id: FileId) -> Session:
        """
        Generates the media session for the DC that contains the media file.
        This is required for getting the bytes from Telegram servers.
        """
        dc_id = getattr(file_id, "dc_id", None)
        media_session = client.media_sessions.get(dc_id, None)

        if media_session is None:
            if dc_id != await client.storage.dc_id():
                media_session = Session(
                    client,
                    dc_id,
                    await Auth(
                        client, dc_id, await client.storage.test_mode()
                    ).create(),
                    await client.storage.test_mode(),
                    is_media=True,
                )
                await media_session.start()

                for _ in range(6):
                    exported_auth = await client.invoke(
                        raw.functions.auth.ExportAuthorization(dc_id=dc_id)
                    )

                    try:
                        await media_session.invoke(
                            raw.functions.auth.ImportAuthorization(
                                id=exported_auth.id, bytes=exported_auth.bytes
                            )
                        )
                        break
                    except AuthBytesInvalid:
                        logger.debug(f"Invalid authorization bytes for DC {dc_id}")
                        continue
                else:
                    await media_session.stop()
                    raise AuthBytesInvalid
            else:
                media_session = Session(
                    client,
                    dc_id,
                    await client.storage.auth_key(),
                    await client.storage.test_mode(),
                    is_media=True,
                )
                await media_session.start()
            logger.debug(f"Created media session for DC {dc_id}")
            client.media_sessions[dc_id] = media_session
        else:
            logger.debug(f"Using cached media session for DC {dc_id}")
        return media_session

    @staticmethod
    async def get_location(
        file_id: FileId,
    ) -> Union[
        raw.types.InputPhotoFileLocation,
        raw.types.InputDocumentFileLocation,
        raw.types.InputPeerPhotoFileLocation,
    ]:
        """
        Returns the file location for the media file.
        """
        file_type = file_id.file_type

        if file_type == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id, access_hash=file_id.chat_access_hash
                )
            else:
                if file_id.chat_access_hash == 0:
                    peer = raw.types.InputPeerChat(chat_id=-file_id.chat_id)
                else:
                    peer = raw.types.InputPeerChannel(
                        channel_id=utils.get_channel_id(file_id.chat_id),
                        access_hash=file_id.chat_access_hash,
                    )

            location = raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
            )
        elif file_type == FileType.PHOTO:
            location = raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        else:
            location = raw.types.InputDocumentFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        return location

    async def yield_file(
        self,
        file_id: FileId,
        index: int,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
        chunk_size: int,
        channel_id: int = None,
        message_id: int = None,
        on_new_fileId = None
    ) -> Union[str, None]:       
        """
        Custom generator that yields the bytes of the media file.
        Modded from <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/telegram/utils/custom_download.py#L20>
        Thanks to Eyaadh <https://github.com/eyaadh>
        """
        client = self.client
        work_loads[index] += 1
        logger.debug(f"Starting to yielding file with client {index}.")
        try:
            media_session = await self.generate_media_session(client, file_id)
        except (
            FilerefUpgradeNeeded,
            FileReferenceEmpty,
            FileReferenceInvalid,
            FileIdInvalid,
            FileReferenceExpired
        ) as er:
            logger.exception(er)
            media_session = await self.generate_media_session(client, file_id)
            try:
                # print(channel, message_id)
                msg = await self.client.get_messages(
                    int(channel_id), message_ids=message_id
                )
                assert msg != None
            except Exception as er:
                logger.info(f"check tgbot access: {er}")
                work_loads[index] -= 1
                yield None

            logger.debug("before calling get_file_properties")

            file_id = await self.get_file_properties(channel_id, message_id, False)
            if on_new_fileId:
                on_new_fileId(file_id)

        current_part = 1
        location = await self.get_location(file_id)

        try:
            r = await media_session.invoke(
                raw.functions.upload.GetFile(
                    location=location, offset=offset, limit=chunk_size
                ),
            )
            if isinstance(r, raw.types.upload.File):
                while True:
                    chunk = r.bytes
                    if not chunk:
                        break
                    elif part_count == 1:
                        yield chunk[first_part_cut:last_part_cut]
                    elif current_part == 1:
                        yield chunk[first_part_cut:]
                    elif current_part == part_count:
                        yield chunk[:last_part_cut]
                    else:
                        yield chunk

                    current_part += 1
                    offset += chunk_size

                    if current_part > part_count:
                        break

                    r = await media_session.invoke(
                        raw.functions.upload.GetFile(
                            location=location, offset=offset, limit=chunk_size
                        ),
                    )
        except (TimeoutError, AttributeError):
            pass
        finally:
            logger.debug(f"Finished yielding file with {current_part} parts.")
            work_loads[index] -= 1

    async def clean_cache(self) -> None:
        """
        function to clean the cache to reduce memory usage
        """
        while True:
            await asyncio.sleep(self.clean_timer)
            self.cached_file_ids.clear()
            logger.debug("Cleaned the cache")
