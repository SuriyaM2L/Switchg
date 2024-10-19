from client import app, hasJoined
from swibots import *
import requests
from swdatabase.ia_filterdb import getMovie, get_file_details
from database.ia_filterdb import (
    get_file_details as get_tg_file_details,
    get_search_results,
)
from guessit import guessit
from base64 import b16decode, b16encode

from config import DISABLE_FORCE, STREAM_URL
from common import SW_COMMUNITY, DOMAIN, SW_USERNAME


def humanbytes(size):
    if not size:
        return "0 B"
    for unit in ["", "K", "M", "G", "T"]:
        if size < 1024:
            break
        size /= 1024
    if isinstance(size, int):
        size = f"{size}{unit}B"
    elif isinstance(size, float):
        size = f"{size:.2f}{unit}B"
    return size


async def showJoinPage(ctx: BotContext[CallbackQueryEvent]):
    if not DISABLE_FORCE and not await hasJoined(ctx.event.action_by_id):
        comps = [
            Text(
                f"🤖 Please join below community in order to use this bot!",
                TextSize.SMALL,
            ),
            Button("Join Community", url=f"https://iswitch.click/{SW_COMMUNITY}"),
            Spacer(y=20),
            Text("After joining, reopen the app to perform any action!"),
        ]
        await ctx.event.answer(
            callback=AppPage(
                components=comps,
            )
        )
        return False
    return True


@app.on_callback_query(regexp("blk"))
async def onFile(ctx: BotContext[CallbackQueryEvent]):
    m = ctx.event.callback_data.split("_")
    try:
        fileId = int(m[-1])
    except Exception:
        return
    file = await ctx.get_media(fileId)
    if file:
        file.id = 0
        await ctx.event.message.send(
            f"*{file.description}*",
            media_info=file,
            inline_markup=InlineMarkup(
                [[InlineKeyboardButton("*Download Now*", url=file.url)]]
            ),
        )
        await ctx.event.answer("File sent to PM!", show_alert=True)


@app.on_command("stream")
async def streamFile(ctx: BotContext[CommandEvent]):
    fileId = ctx.event.params
    if not fileId:
        await ctx.event.message.reply_text("Invalid file id!")
        return
    files = await get_file_details(fileId)
    if not files:
        await ctx.event.message.reply_text("File not found!")
        return
    file = files[0]
    m = await ctx.event.message.reply_text(
        f"*[{humanbytes(file.file_size)}] {file.description or file.file_name}*\n\nClick below button to stream file!",
        inline_markup=InlineMarkup(
            [[InlineKeyboardButton("Open Stream", callback_data=f"vfile|{fileId}")]]
        ),
    )


@app.on_callback_query(regexp("vfile"))
async def showFile(ctx: BotContext[CallbackQueryEvent], fileId=None):
    if not fileId:
        fileId = ctx.event.callback_data.split("|")[-1]
    if not await showJoinPage(ctx):
        return
#     print(fileId)
    details = await get_file_details(int(fileId))
    if not details:
        tgfiledetails = await get_tg_file_details(fileId)
        if not tgfiledetails:
            await ctx.event.answer("File not found", show_alert=True)
            return
        await streamTgFile(ctx, fileId)
        return
    details = details[0]
    iData = {}
    if details.imdb_id:
        iData = await getMovie(
            details.imdb_id, type="tv" if details.tv_show else "movie"
        )
    #       print(iData)
    #    print(details)
    comps = []
    if details.description.endswith((".mkv", ".mp4", ".webm")):
        comps.append(
            VideoPlayer(
                details.file_url,
                title=details.movie_name or details.description or details.file_name,
            )
        )
    elif details.description.endswith((".jpeg", ".jpg", ".png")):
        comps.append(Image(url=details.file_url))
    # else:
    #     comps.append(Text(details.movie_name or details.description, TextSize.SMALL))
    if iD := iData.get("overview"):
        comps.append(Text(iD))
    if iD := iData.get("vote_average"):
        comps.append(Text(f"*Rating:* {iD} ⭐"))
    if iD := details.file_size:
        comps.append(Text(f"*File Size:* {humanbytes(iD)}"))
    if iD := iData.get("release_date"):
        comps.append(Text(f"*Released on:* {iD}"))
    if iD := iData.get("status"):
        comps.append(Text(f"*Status:* {iD}"))
    comps.append(Text(f"*File Name:* {details.description or details.file_name}"))
    comps.append(
        ButtonGroup(
            [
                Button("Get File", callback_data=f"blk_{fileId}"),
                ShareButton(
                    "Share file",
                    share_text=f"{DOMAIN}/chat/{ctx.user.user_name}?stream={fileId}&is_preview=false",
                ),
            ]
        ),
    )
    comps.append(
        Button(
            text="Download Now",
            url=details.file_url,
        )
    )
    await ctx.event.answer(
        callback=AppPage(
            components=comps,
        ),
        new_page=True,
    )


async def makeListTiles(query="", max=25):
    results, _, __ = await get_search_results(query, max_results=max)
    gV = []
    for file in results:
        details = guessit(getattr(file, "description", None) or file.file_name)
        gV.append(
            ListTile(
                getattr(file, "movie_name", None)
                or details.get("title")
                or getattr(file, "description", None)
                or file.file_name,
                title_extra=(
                    f"Episode {file.episode_id}"
                    if (
                        getattr(file, "tv_show", None)
                        and getattr(file, "episode_id", None)
                    )
                    else (
                        f"EP {details.get('episode', '')} | {details.get('episode_title', '')}".strip()
                        if details.get("episode")
                        else (
                            " | ".join(details.get("other"))
                            if isinstance(details.get("other"), list)
                            else details.get("other", "")
                        )
                    )
                ),
                thumb=(
                    file.thumbnail
                    if getattr(file, "thumbnail", None)
                    else (
                        file.file_url
                        if hasattr(file, "description")
                        and file.description.endswith((".jpg", ".png", ".jpeg"))
                        else (
                            app.user.imageurl
                            if app.user.imageurl.endswith((".jpg", ".png", ".jpeg"))
                            else "https://media.istockphoto.com/id/1147544810/vector/no-thumbnail-image-vector-graphic.jpg?s=612x612&w=0&k=20&c=2-ScbybM7bUYw-nptQXyKKjwRHKQZ9fEIwoWmZG9Zyg="
                        )
                    )
                ),
                description=f"File Size: {humanbytes(file.file_size)}"
                + (f" | {details['year']}" if details.get("year") else ""),
                callback_data=(
                    f"vfile|{file.file_id}"
                    if hasattr(file, "description")
                    else f"tgstream|{file.file_id}"
                ),
            )
        )
    return gV


def splitList(lis, part):
    nList = []
    while lis:
        nList.append(lis[:part])
        lis = lis[part:]
    return nList


@app.on_callback_query(regexp("srch"))
async def onHome(ctx: BotContext[CallbackQueryEvent]):
    if not await showJoinPage(ctx):
        return
    comps = [SearchBar("Search files", callback_data="srch")]
    index = 1
    query = ctx.event.details.search_query
    if "|" in ctx.event.callback_data:
        query, index = ctx.event.callback_data.split("|")[1:]
        index = int(index)

    if query:
        gV = await makeListTiles(query, 80)
        if gV:
            BOXES = splitList(gV, 10)
            try:
                gV = BOXES[index - 1]
            except:
                gV = gV[0]
        if gV:
            comps.append(Text(f"*Results for {query}*", TextSize.SMALL))
            comps.append(ListView(options=gV, view_type=ListViewType.LARGE))
            bts = []
            if index > 1:
                bts.append(Button("Back", callback_data=f"srch|{query}|{index-1}"))
            if index < len(BOXES):
                bts.append(Button("Next", callback_data=f"srch|{query}|{index+1}"))
            comps.append(ButtonGroup(bts))
        else:
            comps.append(Text(f"No results found for {query}!", TextSize.SMALL))
    await ctx.event.answer(callback=AppPage(components=comps), new_page=not query)


@app.on_callback_query(regexp("Home"))
async def onHome(ctx: BotContext[CallbackQueryEvent]):
    if not await showJoinPage(ctx):
        return
    comps = [SearchHolder("Search files..", callback_data="srch")]
    gv = await makeListTiles(max=50)
    if gv:
        comps.append(Text("Recently Uploaded", TextSize.SMALL))
        comps.append(ListView(gv, ListViewType.LARGE))
    await ctx.event.answer(callback=AppPage(components=comps))


@app.on_callback_query(regexp("stream_"))
async def streamTgFile(ctx: BotContext[CallbackQueryEvent], fileId=None):
    if not await showJoinPage(ctx):
        return
    if fileId:
        tgd = await get_tg_file_details(fileId)
        file = tgd[0]
        channel = file["chat_id"]
        messageId = file["message_id"]
        hash = b16encode(f"{channel}:{messageId}".encode()).decode()
    else:
        hash = ctx.event.callback_data.split("_")[-1]
        channel, messageId = b16decode(hash.encode()).decode().split(":")
    try:
        message = requests.get(F"{STREAM_URL}/messageInfo?channel={channel}&messageId={messageId}").json()
        message['id']
    except Exception as er:
        await ctx.event.answer(callback=AppPage(components=[Text(f"ERROR: {er}")]))
        return
    fileName = ''
    for type in ["photo", "video", "document", "audio"]:
        if message.get(type):
            fileName = message[type].get("file_name")
            if fileName:
                break
    url = f"{STREAM_URL}/stream?hash={hash}"
    comps = [
        VideoPlayer(url=url, title=fileName),
        ButtonGroup(
            [
                ShareButton(
                    "Share",
                    share_text=f"{DOMAIN}/{SW_USERNAME}:{ctx.event.callback_data}",
                ),
                Button("Download", url=url),
            ]
        ),
    ]
    await ctx.event.answer(callback=AppPage(components=comps), new_page=True)


@app.on_callback_query(regexp("tgstream"))
async def ontstream(ctx: BotContext[CallbackQueryEvent]):
    fileId = ctx.event.callback_data.split("|")[-1]
    await streamTgFile(ctx, fileId)


@app.on_command("getfile")
async def onCommand(ctx: BotContext[CommandEvent]):
    m = ctx.event.message
    param = ctx.event.params
    if not param:
        await m.send("Invalid file id!")
        return
    from database.ia_filterdb import get_file_details

    details = await get_file_details(param)
    file = details[0]
    encodeId = f"{file['chat_id']}:{file['message_id']}"

    hash = b16encode(encodeId.encode()).decode()
    url = f"{STREAM_URL}/stream?hash={hash}"

    await m.reply_text(
        f"""*Here is your file*\n\nFile Name: {file.file_name}""",
        inline_markup=InlineMarkup(
            [
                [
                    InlineKeyboardButton("Stream", url=url),
                    InlineKeyboardButton("Download", url=url),
                ]
            ]
        ),
    )
