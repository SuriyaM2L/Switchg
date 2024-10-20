import asyncio, re, ast, math, logging
from pyrogram.errors.exceptions.bad_request_400 import (
    MediaEmpty,
    PhotoInvalidDimensions,
    WebpageMediaEmpty,
)
from Script import script
from utils import get_shortlink, admin_filter
import pyrogram
from urllib.parse import quote
from pyrogram.client import Client
from pyrogram.types import Message
from pyrogram.errors import UserIsBlocked
from config import SPELL_FILTER
from database.connections_mdb import (
    active_connection,
    all_connections,
    delete_connection,
    if_active,
    make_active,
    make_inactive,
)
from tgconfig import (
    ADMINS,
    AUTH_CHANNEL,
    AUTH_USERS,
    CUSTOM_FILE_CAPTION,
    AUTH_GROUPS,
    P_TTI_SHOW_OFF,
    IMDB,
    PM_IMDB,
    SINGLE_BUTTON,
    PROTECT_CONTENT,
    SPELL_CHECK_REPLY,
    IMDB_TEMPLATE,
    IMDB_DELET_TIME,
    START_MESSAGE,
    PMFILTER,
    G_FILTER,
    BUTTON_LOCK,
    BUTTON_LOCK_TEXT,
    SHORT_URL,
    SHORT_API,
    SEND_FILE_PM
)

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import (
    get_size,
    is_subscribed,
    get_poster,
    search_gagala,
    temp,
    get_settings,
    save_group_settings,
)
from database.users_chats_db import db
from database.ia_filterdb import Media, get_file_details, get_search_results
from database.filters_mdb import del_all, find_filter, get_filters
from database.gfilters_mdb import find_gfilter, get_gfilters
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


FILTER_MODE = {}
G_MODE = {}
SPELL_CHECK = {}


@Client.on_message(
    filters.command("autofilter") & filters.group & filters.create(admin_filter)
)
async def fil_mod(client, message):
    mode_on = ["yes", "on", "true"]
    mode_of = ["no", "off", "false"]

    try:
        args = message.text.split(None, 1)[1].lower()
    except:
        return await message.reply("**ɪɴᴄᴏᴍᴩʟᴇᴛᴇ ᴄᴏᴍᴍᴀɴᴅ...**")

    m = await message.reply("**ꜱᴇᴛᴛɪɴɢ....**")

    if args in mode_on:
        FILTER_MODE[str(message.chat.id)] = "True"
        await m.edit("**ᴀᴜᴛᴏꜰɪʟᴛᴇʀ ᴇɴᴀʙʟᴇᴅ**")

    elif args in mode_of:
        FILTER_MODE[str(message.chat.id)] = "False"
        await m.edit("**ᴀᴜᴛᴏꜰɪʟᴛᴇʀ ᴅɪꜱᴀʙʟᴇᴅ**")
    else:
        await m.edit("ᴜꜱᴇ :- `/autofilter on` ᴏʀ `/autofilter off`")


@Client.on_message(
    filters.command("g_filter") & filters.group & filters.create(admin_filter)
)
async def g_fil_mod(client, message):
    mode_on = ["yes", "on", "true"]
    mode_of = ["no", "off", "false"]

    try:
        args = message.text.split(None, 1)[1].lower()
    except:
        return await message.reply("**ɪɴᴄᴏᴍᴩʟᴇᴛᴇ ᴄᴏᴍᴍᴀɴᴅ...**")

    m = await message.reply("**ꜱᴇᴛᴛɪɴɢ...**")

    if args in mode_on:
        G_MODE[str(message.chat.id)] = "True"
        await m.edit("**ɢʟᴏʙᴀʟ ꜰɪʟᴛᴇʀ ᴇɴᴀʙʟᴇᴅ**")

    elif args in mode_of:
        G_MODE[str(message.chat.id)] = "False"
        await m.edit("**ɢʟᴏʙᴀʟ ꜰɪʟᴛᴇʀ ᴅɪꜱᴀʙʟᴇᴅ**")
    else:
        await m.edit("ᴜꜱᴇ :- `/g_filter on` ᴏʀ `/g_filter off`")


@Client.on_callback_query(
    filters.create(lambda _, __, query: query.data.startswith("next"))
)
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(
            BUTTON_LOCK_TEXT.format(query.from_user.first_name,
                                    query=""), show_alert=True
        )
    try:
        offset = int(offset)
    except:
        offset = 0
    search = temp.GP_BUTTONS.get(key)
    if not search:
        return await query.answer(
            "Yᴏᴜ Aʀᴇ Usɪɴɢ Oɴᴇ Oғ Mʏ Oʟᴅ Mᴇssᴀɢᴇs, Pʟᴇᴀsᴇ Sᴇɴᴅ Tʜᴇ Rᴇǫᴜᴇsᴛ Aɢᴀɪɴ",
            show_alert=True,
        )

    files, n_offset, total = await get_search_results(
        search, offset=offset, filter=True
    )
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0

    if not files:
        return
    settings = await get_settings(query.message.chat.id)
    nxreq = query.from_user.id if query.from_user else 0
    if SHORT_URL and SHORT_API:
        if settings["button"]:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"[{get_size(file.file_size)}] {file.file_name}",
                                              callback_data=f"shorturl|{file.file_id}"

                    )
                ]
                for file in files
            ]
        else:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{file.file_name}",
                                              callback_data=f"shorturl|{file.file_id}"

                    ),
                    InlineKeyboardButton(
                        text=f"{get_size(file.file_size)}",
                                                callback_data=f"shorturl|{file.file_id}"

                    ),
                ]
                for file in files
            ]
    else:
        if settings["button"]:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"[{get_size(file.file_size)}] {getattr(file, 'description', '') or file.file_name}",
                        callback_data=f"files#{nxreq}#{file.file_id}",
                    )
                ]
                for file in files
            ]
        else:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{file.file_name}",
                        callback_data=f"files#{nxreq}#{file.file_id}",
                    ),
                    InlineKeyboardButton(
                        text=f"{get_size(file.file_size)}",
                        callback_data=f"files#{nxreq}#{file.file_id}",
                    ),
                ]
                for file in files
            ]

    btn.insert(0, [InlineKeyboardButton("🔗 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ 🔗", url=f"https://t.me/tgtamillinks/49")])
    if 0 < offset <= 10:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - 10
    if n_offset == 0:
        btn.append(
            [
                InlineKeyboardButton(
                    "⬅️ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"
                ),
                InlineKeyboardButton(
                    f"❄️ ᴩᴀɢᴇꜱ {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}",
                    callback_data="pages",
                ),
            ]
        )
    elif off_set is None:
        btn.append(
            [
                InlineKeyboardButton(
                    f"❄️ {(offset or 0) + 1} / {math.ceil(total / 10)}",
                    callback_data="pages",
                ),
                InlineKeyboardButton(
                    "ɴᴇxᴛ ➡️", callback_data=f"next_{req}_{key}_{n_offset}"
                ),
            ]
        )
    else:
        btn.append(
            [
                InlineKeyboardButton(
                    "⬅️ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"
                ),
                InlineKeyboardButton(
                    f"❄️ {(offset or 0) + 1} / {math.ceil(total / 10)}",
                    callback_data="pages",
                ),
                InlineKeyboardButton(
                    "ɴᴇxᴛ ➡️", callback_data=f"next_{req}_{key}_{n_offset}"
                ),
            ],
        )

    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    await query.answer()


@Client.on_callback_query(
    filters.create(lambda _, __, query: query.data.startswith("spolling"))
)
async def advantage_spoll_choker(bot, query):
    _, user, movie_ = query.data.split("#")
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer("okDa", show_alert=True)
    if movie_ == "close_spellcheck":
        return await query.message.delete()
    movies = temp.GP_SPELL.get(query.message.reply_to_message.id)
    if not movies:
        return await query.answer(
            "Yᴏᴜ Aʀᴇ Usɪɴɢ Oɴᴇ Oғ Mʏ Oʟᴅ Mᴇssᴀɢᴇs, Pʟᴇᴀsᴇ Sᴇɴᴅ Tʜᴇ Rᴇǫᴜᴇsᴛ Aɢᴀɪɴ",
            show_alert=True,
        )
    movie = movies[(int(movie_))]
    await query.answer("Checking for Movie in database...")
    k = await manual_filters(bot, query.message, text=movie)
    if k == False:
        files, offset, total_results = await get_search_results(
            movie, offset=0, filter=True
        )
        if files:
            k = (movie, files, offset, total_results)
            await auto_filter(bot, query, k)
        else:
            k = await query.message.edit("This Movie Not Found In DataBase")
            await asyncio.sleep(10)
            await k.delete()


@Client.on_message(
    filters.group & filters.text & filters.incoming & filters.incoming & filters.group
)
async def give_filter(client, message):    
    # Check if the chat is authorized
    authorized_chats = await db.get_all_authorized_chats()
    if authorized_chats and message.chat.id not in authorized_chats:
        return

    if G_FILTER:
        if G_MODE.get(str(message.chat.id)) == "False":
            return
        else:
            kd = await global_filters(client, message)
        if kd == False:
            k = await manual_filters(client, message)
            if k == False:
                if FILTER_MODE.get(str(message.chat.id)) == "False":
                    return
                else:
                    await auto_filter(client, message)
    else:
        k = await manual_filters(client, message)
        if k == False:
            if FILTER_MODE.get(str(message.chat.id)) == "False":
                return
            else:
                await auto_filter(client, message)


async def auto_filter(client: Client, msg: Message, spoll=False):
    if not getattr(client, "me", None):
        client.me = await client.get_me()

    if SEND_FILE_PM:
        from base64 import urlsafe_b64encode

        await msg.reply_text("Click the below button to continue the search in PM.",
                             reply_markup=InlineKeyboardMarkup([[
                                 InlineKeyboardButton("Click here",
                                                      url=f"https://t.me/{client.me.username}?start=search_{urlsafe_b64encode(msg.text.encode()).decode()}")
                             ]]))

        return
    if not spoll:
        message = msg
        settings = await get_settings(message.chat.id)
        if message.text.startswith("/"):
            return  # ignore commands
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if 2 < len(message.text) < 100:
            search = message.text
            files, offset, total_results = await get_search_results(
                search.lower(), offset=0, filter=True
            )
            if not files:
                if settings["spell_check"]:
                    return await advantage_spell_chok(msg)
                else:
                    return
        else:
            return
    else:
        settings = await get_settings(msg.message.chat.id)
        message = msg.message.reply_to_message  # msg will be callback query
        search, files, offset, total_results = spoll

    pre = "filep" if settings["file_secure"] else "file"
    req = message.from_user.id if message.from_user else 0
    if SEND_FILE_PM:
        chat_id = message.from_user.id
    else:
        chat_id = message.chat.id

    if SHORT_URL and SHORT_API:
        if settings["button"]:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"[{get_size(file.file_size)}] {file.file_name}",
                                              callback_data=f"shorturl|{file.file_id}"

                    )
                ]
                for file in files
            ]
        else:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{file.file_name}",
                                             callback_data=f"shorturl|{file.file_id}"

                    ),
                    InlineKeyboardButton(
                        text=f"{get_size(file.file_size)}",
                                              callback_data=f"shorturl|{file.file_id}"

                    ),
                ]
                for file in files
            ]
    else:
        if settings["button"]:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"[{get_size(file.file_size)}] {getattr(file, 'description', file.file_name)}",
                        callback_data=f"{pre}#{req}#{file.file_id}",
                    )
                ]
                for file in files
            ]
        else:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{file.file_name}",
                        callback_data=f"{pre}#{req}#{file.file_id}",
                    ),
                    InlineKeyboardButton(
                        text=f"{get_size(file.file_size)}",
                        callback_data=f"{pre}#{req}#{file.file_id}",
                    ),
                ]
                for file in files
            ]

    btn.insert(0, [InlineKeyboardButton("🔗 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ 🔗", url=f"https://t.me/tgtamillinks/49")])
    if offset != "":
        key = f"{message.chat.id}-{message.id}"
        temp.GP_BUTTONS[key] = search
        req = message.from_user.id if message.from_user else 0
        btn.append(
            [
                InlineKeyboardButton(
                    text=f"❄️ ᴩᴀɢᴇꜱ 1/{math.ceil(int(total_results) / 10)}",
                    callback_data="pages",
                ),
                InlineKeyboardButton(
                    text="➡️ ɴᴇxᴛ", callback_data=f"next_{req}_{key}_{offset}"
                ),
            ]
        )
    else:
        btn.append([InlineKeyboardButton(text="❄️ ᴩᴀɢᴇꜱ 1/1", callback_data="pages")])

    imdb = (
        await get_poster(search, file=(files[0]).file_name)
        if settings["imdb"]
        else None
    )
    TEMPLATE = settings["template"]
    if imdb:
        cap = TEMPLATE.format(
            group=message.chat.title,
            requested=message.from_user.mention,
            query=search,
            title=imdb["title"],
            votes=imdb["votes"],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb["box_office"],
            localized_title=imdb["localized_title"],
            kind=imdb["kind"],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb["release_date"],
            year=imdb["year"],
            genres=imdb["genres"],
            poster=imdb["poster"],
            plot=imdb["plot"],
            rating=imdb["rating"],
            url=imdb["url"],
            **locals(),
        )
    else:
        cap = f"Hᴇʀᴇ Is Wʜᴀᴛ I Fᴏᴜɴᴅ Fᴏʀ Yᴏᴜʀ Qᴜᴇʀʏ {search}"

    hehe = None
    if imdb and imdb.get("poster"):
        try:
            hehe = await client.send_photo(
                chat_id=chat_id,
                reply_to_message_id=None if SEND_FILE_PM else message.id,
                photo=imdb.get("poster"),
                caption=cap,
                reply_markup=InlineKeyboardMarkup(btn),
                protect_content=PROTECT_CONTENT
            )
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get("poster")
            poster = pic.replace(".jpg", "._V1_UX360.jpg")
            hehe = await client.send_photo(
                chat_id=chat_id,
                reply_to_message_id=None if SEND_FILE_PM else message.id,
                photo=poster, caption=cap, reply_markup=InlineKeyboardMarkup(btn),
                protect_content=PROTECT_CONTENT
            )
        except UserIsBlocked:
            await message.reply_text(
                text="User has Blocked Me 😔\n\nPlease Unblock me to send files in PM",
                quote=True
            )
        except Exception as e:
            logger.exception(e)
            hehe = await client.send_message(
                chat_id=chat_id,
                reply_to_message_id=None if SEND_FILE_PM else message.id,
                text=cap, reply_markup=InlineKeyboardMarkup(btn),
                protect_content=PROTECT_CONTENT
            )
    else:
        hehe = await client.send_message(
            chat_id=chat_id,
            reply_to_message_id=None if SEND_FILE_PM else message.id,
            text=cap, reply_markup=InlineKeyboardMarkup(btn),
            protect_content=PROTECT_CONTENT
        )
        

    if SEND_FILE_PM:
        await message.reply_text(
            """Check in private message,I have sent files in private message 

Private message parunga.neega keta file send paniten

👇Click This Button""",
            reply_markup=InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("🔗 Check in PM 🔗", callback_data="alert_pm")]]),
                    quote=True
        )
    await asyncio.sleep(IMDB_DELET_TIME)
    if hehe:
        await hehe.delete()
    await message.delete()

    if spoll:
        await msg.message.delete()


async def advantage_spell_chok(msg: Message):
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "",
        msg.text,
        flags=re.IGNORECASE,
    )
    query = query.strip() + " movie"
    logger.info(f"Searching for: {query}")
    g_s = await search_gagala(query)
    g_s += await search_gagala(msg.text)
    logger.info(f"Search results: {g_s}")
    
    if not g_s:
        k = await msg.reply("I Cᴏᴜʟᴅɴ'ᴛ Fɪɴᴅ Aɴʏ Mᴏᴠɪᴇ Iɴ Tʜᴀᴛ Nᴀᴍᴇ")
        await asyncio.sleep(8)
        return await k.delete()

    def extract_movie_name(result):
        patterns = [
            r'(?:.*?›.*?)?([^›]+?)\s*\(\d{4}\)',
            r'(?:.*?›.*?)?([^›]+?)\s*-\s*(?:IMDb|Wikipedia|BookMyShow)',
            r'Watch\s+([^›]+?)\s*(?:-|\|)',
            r'(?:.*?›.*?)?([^›]+?)\s*(?:Full Movie|Movie)',
            r'(?:.*?›.*?)?([^›]+?)\s*\|\s*.*?(?:Movie|Film)',
            r'(?:OFFICIAL.*?MOVIE\s*-\s*)([^›]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None

    def clean_movie_name(name):
        name = re.sub(r'^.*?›\s*', '', name)
        name = re.sub(r'^.*?(?:tt\d+|www\.[^›]+›)', '', name)
        name = re.sub(r"(\-|\(|\)|_)", " ", name)
        name = re.sub(r"\b(imdb|wikipedia|reviews|full|all|episode(s)?|film|movie|series|official|trailer|video song|videos|songs)\b", "", name, flags=re.IGNORECASE)
        name = re.sub(r'\|.*', '', name)
        name = re.sub(r'\d{4}\s*AD', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        name = re.sub(r'\s+\d{4}$', '', name)
        name = re.sub(r'(.+?)\1+', r'\1', name)
        
        invalid_entries = ['images', 'videos', 'search', 'news']
        if name.lower() in invalid_entries:
            return None
        
        return name

    def fuzzy_dedupe(names, threshold=75):
        unique_names = []
        for name in names:
            if not unique_names or all(fuzz.ratio(name, un) < threshold for un in unique_names):
                unique_names.append(name)
        return unique_names

    movie_names = []
    for result in g_s:
        movie_name = extract_movie_name(result)
        if movie_name:
            cleaned_name = clean_movie_name(movie_name)
        else:
            cleaned_name = clean_movie_name(result)
        
        if cleaned_name and len(cleaned_name) > 1:
            movie_names.append(cleaned_name)

    unique_names = fuzzy_dedupe(movie_names)
    
    if not unique_names:
        k = await msg.reply(
            "I Cᴏᴜʟᴅɴ'ᴛ Fɪɴᴅ Aɴʏᴛʜɪɴɢ Rᴇʟᴀᴛᴇᴅ Tᴏ Tʜᴀᴛ. Cʜᴇᴄᴋ Yᴏᴜʀ Sᴘᴇʟʟɪɴɢ"
        )
        await asyncio.sleep(8)
        return await k.delete()

    movielist = unique_names
    temp.GP_SPELL[msg.id] = movielist

    user = msg.from_user.id if msg.from_user else 0

    async def check_results(query, clb):
        query = query.strip()
        res = await get_file_details(query)
        if res:
            return [InlineKeyboardButton(query, callback_data=clb)]

    if SPELL_FILTER:
        filtered = await asyncio.gather(
            *[
                check_results(movie, f"spolling#{user}#{k}")
                for k, movie in enumerate(movielist)
            ]
        )
        if not filtered:
            await msg.reply("I Cᴏᴜʟᴅɴ'ᴛ Fɪɴᴅ Aɴʏᴛʜɪɴɢ Rᴇʟᴀᴛᴇᴅ Tᴏ Tʜᴀᴛ", quote=True)
            return
        btn = [list(filter(lambda x: x, filtered))]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=movie.strip(), callback_data=f"spolling#{user}#{k}"
                )
            ]
            for k, movie in enumerate(movielist)
        ]
    btn.append(
        [
            InlineKeyboardButton(
                text="Close", callback_data=f"spolling#{user}#close_spellcheck"
            )
        ]
    )
    client: Client = msg.client

    await client.send_message(
        chat_id=msg.from_user.id if msg.from_user else msg.chat.id,
        text="I Cᴏᴜʟᴅɴ'ᴛ Fɪɴᴅ Aɴʏᴛʜɪɴɢ Rᴇʟᴀᴛᴇᴅ Tᴏ Tʜᴀᴛ. Dɪᴅ Yᴏᴜ Mᴇᴀɴ Aɴʏ Oɴᴇ Oғ Tʜᴇsᴇ?",
        reply_markup=InlineKeyboardMarkup(btn),
        protect_content=PROTECT_CONTENT
    )


async def manual_filters(client, message, text=False):
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_filters(group_id)
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_filter(group_id, keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_to_message_id=reply_id,
                            )
                        else:
                            button = eval(btn)
                            await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id,
                            )
                    elif btn == "[]":
                        await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id,
                        )
                    else:
                        button = eval(btn)
                        await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id,
                        )
                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False


async def global_filters(client, message, text=False):
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_gfilters("gfilters")
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_gfilter("gfilters", keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            knd3 = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_to_message_id=reply_id,
                            )
                            await asyncio.sleep(IMDB_DELET_TIME)
                            await knd3.delete()
                            await message.delete()

                        else:
                            button = eval(btn)
                            knd2 = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id,
                            )
                            await asyncio.sleep(IMDB_DELET_TIME)
                            await knd2.delete()
                            await message.delete()

                    elif btn == "[]":
                        knd1 = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id,
                        )
                        await asyncio.sleep(IMDB_DELET_TIME)
                        await knd1.delete()
                        await message.delete()

                    else:
                        button = eval(btn)
                        knd = await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id,
                        )
                        await asyncio.sleep(IMDB_DELET_TIME)
                        await knd.delete()
                        await message.delete()

                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False
