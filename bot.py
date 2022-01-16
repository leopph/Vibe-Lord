import aiohttp
import asyncio
import dotenv
import os
import re
from datetime import datetime
from discord import VoiceClient, File
from discord.ext.commands import Bot, Context, check
from discord.ext.commands.core import is_owner
from discord.ext.commands.errors import CommandError
from exceptions import CheckFailedError
from io import BytesIO
from pathlib import Path
from responses import Responses
from song import Song
from songqueue import SongQueue
from typing import Final
from youtube_dl import YoutubeDL


dotenv.load_dotenv()

TOKEN: Final = os.getenv("DISCORD_TOKEN")
FFMPEG_OPTIONS: Final = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
URL: Final = re.compile(r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))")

bot: Final = Bot(command_prefix=".")
responses: Final = Responses(str(Path(__file__).parent.absolute()) + "/res/responses.json")
queues: Final[dict[VoiceClient, SongQueue]] = dict()
download_tasks: Final[dict[VoiceClient, list[asyncio.Task]]] = dict()


def in_guild(ctx: Context) -> bool:
    if ctx.guild is None:
        raise CheckFailedError(responses.get("DM", ctx.author.name))
    return True


def member_in_voice(ctx: Context) -> bool:
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        raise CheckFailedError(responses.get("USER_NOT_IN_VOICE", ctx.author.mention))
    return True


def bot_in_voice(ctx: Context) -> bool:
    if ctx.voice_client is None:
        raise CheckFailedError(responses.get("NOT_IN_VOICE", ctx.author.mention))
    return True


def bot_not_in_voice(ctx: Context) -> bool:
    try:
        bot_in_voice(ctx)
    except CheckFailedError:
        return True
    raise CheckFailedError(responses.get("ALREADY_IN_VOICE", ctx.message.author.mention))


def member_and_bot_in_same_voice(ctx: Context) -> bool:
    if bot_in_voice(ctx) and member_in_voice(ctx) and ctx.voice_client.channel == ctx.author.voice.channel:
        return True
    raise CheckFailedError(responses.get("DIFFERENT_VOICE_CHANNELS", ctx.author.mention, ctx.voice_client.channel.name))


def playing(ctx: Context) -> bool:
    if queues[ctx.voice_client].now_playing is None:
        raise CheckFailedError(responses.get("NOT_PLAYING", ctx.author.mention))
    return True


def member_in_voice_and_member_and_bot_in_same_voice_or_bot_not_in_voice(ctx: Context) -> bool:
    member_in_voice(ctx)
    try:
        bot_in_voice(ctx)
        return member_and_bot_in_same_voice(ctx)
    except CheckFailedError:
        try:
            bot_in_voice(ctx)
        except CheckFailedError:
            return True
        raise


def queue_not_empty(ctx: Context) -> bool:
    if queues[ctx.voice_client].is_empty():
        raise CheckFailedError(responses.get("QUEUE_EMPTY"))
    return True


def queue_not_empty_or_playing(ctx: Context) -> bool:
    try:
        return queue_not_empty(ctx)
    except CheckFailedError:
        return playing(ctx)


def paused(ctx: Context) -> bool:
    if not ctx.voice_client.is_paused():
        raise CheckFailedError(responses.get("NOT_PAUSED", ctx.message.author.mention))
    return True


def log(msg: str) -> None:
    now = datetime.now()
    date_time = now.strftime("%Y/%m/%d %H:%M:%S")
    print("[" + date_time + "] " + msg)


@bot.event
async def on_ready():
    log("Ready.")


@bot.event
async def on_command_error(ctx: Context, error: CommandError) -> None:
    if isinstance(error, CheckFailedError):
        await ctx.send(error)
        return
    log(str(error))
    await ctx.send(responses.get("UNKNOWN_ERROR"))
    

@check(queue_not_empty)
@check(member_and_bot_in_same_voice)
@check(bot_in_voice)
@check(member_in_voice)
@check(in_guild)
@bot.command(name="shuffle", help="Randomly reorder the current queue")
async def shuffle(ctx: Context) -> None:
    queues[ctx.voice_client].shuffle()
    await ctx.send(responses.get("SHUFFLE"))


@check(playing)
@check(member_and_bot_in_same_voice)
@check(bot_in_voice)
@check(member_in_voice)
@check(in_guild)
@bot.command(name="seek", help="Skip to a certain part of the current song")
async def seek(ctx: Context, seconds: int) -> None:   
    if queues[ctx.voice_client].now_playing.length >= seconds >= 0:
        seek_opts = FFMPEG_OPTIONS.copy()
        seek_opts["before_options"] = FFMPEG_OPTIONS["before_options"] + f" -ss {seconds}"
        ctx.voice_client.source = queues[ctx.voice_client].now_playing.new_source(**seek_opts)
        return
    
    await ctx.send(responses.get("BAD_TIMESTAMP", ctx.author.mention))


@check(playing)
@check(bot_in_voice)
@check(in_guild)
@bot.command(name="nowplaying", aliases=["np"], help="Show the current song")
async def now_paying(ctx: Context) -> None:
    await ctx.send(f"Now playing: {queues[ctx.voice_client].now_playing.title}", file=File(queues[ctx.voice_client].now_playing.image, "cover.jpg"))


@check(queue_not_empty_or_playing)
@check(bot_in_voice)
@check(in_guild)
@bot.command(name="queue", aliases=["q", "que", "queueue"], help="Show songs in queue")
async def show_queue(ctx: Context):
    np_symbol: Final = "🔄" if queues[ctx.voice_client].loop else "▶"
    message =   np_symbol + " " + queues[ctx.voice_client].now_playing.title + " " + np_symbol + "\n" +\
                "\n".join([str(index + 1) + ". " + song.title for index, song in enumerate(queues[ctx.voice_client].queue)])

    for sub_message in string_splitter(message, "\n", 2000):
        await ctx.send(sub_message)


@check(member_in_voice_and_member_and_bot_in_same_voice_or_bot_not_in_voice)
@check(in_guild)
@bot.command(name="play", aliases=["p", "y", "youtube"], brief="Queue track from YouTube", help="Queue a video's audio track from YouTube. Accepts direct video links, playlist links, and search queries.")
async def youtube(ctx: Context, *, source) -> None:
    def yt_results(source: str) -> dict:
        YDL_OPTS = {"format": "bestaudio", "quiet": "True", "ignoreerrors": "True"}

        with YoutubeDL(YDL_OPTS) as ydl:
            if URL.match(source):
                info = ydl.extract_info(source, download=False, process=False)

                if info is None:
                    yield None
                    return

                if "entries" in info:
                    for entry in info["entries"]:
                        yield ydl.extract_info("https://youtu.be/" + entry["url"], download=False)

                else:
                    yield ydl.extract_info(source, download=False)

            else:
                yield ydl.extract_info(f"ytsearch:{source}", download=False)['entries'][0]


    async def add_to_queue():
        try:
            for video in yt_results(source):
                if video is not None: # TODO kell else ág rendesen lekezelni az esetet, ha invalid az egész link
                    song = Song(video["title"], video["duration"], video["url"], await download_image(video["thumbnails"][-1]["url"]))

                    queues[ctx.voice_client].add(song)

                    await ctx.send(responses.get("QUEUE", song.title))

                    if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                        play_next(None, ctx.voice_client)

        except IndexError:
            await ctx.send(responses.get("NO_RESULT", ctx.author.mention))


    if not ctx.voice_client:
        await ctx.message.author.voice.channel.connect()
        queues[ctx.voice_client] = SongQueue()
        download_tasks[ctx.voice_client] = list()

    task = bot.loop.create_task(add_to_queue())
    download_tasks[ctx.voice_client].append(task)

    try:
        await task
    except asyncio.CancelledError:
        pass
    else:
        download_tasks[ctx.voice_client].remove(task)


@check(playing)
@check(member_and_bot_in_same_voice)
@check(member_in_voice)
@check(bot_in_voice)
@check(in_guild)
@bot.command(name="stop", brief="Stop music", help="Stop playback. This removes all songs from the queue, and stops background queueing processes.")
async def stop(ctx: Context) -> None:
    # Stop downloads for this queue and clear it
    stop_downloads_server(ctx.voice_client)
    queues[ctx.voice_client].clear()
    # Save loop state and turn looping off
    loop = queues[ctx.voice_client].loop
    queues[ctx.voice_client].loop = False
    # Since looping is off and the queue is empty, this will set now_playing to None
    queues[ctx.voice_client].next()
    # Restore loop state
    queues[ctx.voice_client].loop = loop
    # Now we stop playback and invoke the callback, which will not start a new song
    # because now_playing is now None and the queue is empty
    ctx.voice_client.stop()


@check(queue_not_empty)
@check(member_and_bot_in_same_voice)
@check(member_in_voice)
@check(bot_in_voice)
@check(in_guild)
@bot.command(name="clear", brief="Clear queue", help="Remove all the songs from the queue. This does not stop current playback, but stops background queueing processes.")
async def clear(ctx: Context) -> None:
    stop_downloads_server(ctx.voice_client)
    queues[ctx.voice_client].clear()
    await ctx.send(responses.get("QUEUE_CLEARED"))


@check(playing)
@check(member_and_bot_in_same_voice)
@check(member_in_voice)
@check(bot_in_voice)
@check(in_guild)
@bot.command(name="pause", help="Pause playback")
async def pause(ctx: Context) -> None:
    ctx.voice_client.pause()
    await ctx.send(responses.get("PAUSE"))


@check(paused)
@check(member_and_bot_in_same_voice)
@check(member_in_voice)
@check(bot_in_voice)
@check(in_guild)
@bot.command(name="resume", help="Resume playback")
async def resume(ctx: Context) -> None:
    ctx.voice_client.resume()
    await ctx.send(responses.get("RESUME"))


@check(member_in_voice)
@check(bot_not_in_voice)
@check(in_guild)
@bot.command(name="connect", aliases=["c"], help="Connect to voice channel")
async def connect(ctx: Context) -> None:
    await ctx.message.author.voice.channel.connect()
    queues[ctx.voice_client] = SongQueue()
    download_tasks[ctx.voice_client] = list()


@check(member_and_bot_in_same_voice)
@check(member_in_voice)
@check(bot_in_voice)
@check(in_guild)
@bot.command(name="disconnect", aliases=["dc"], brief="Disconnect from voice channel", help="Disconnect from the current voice channel. This stops all background queueing processes, and clears the server queue.")
async def disconnect(ctx: Context) -> None:
    stop_downloads_server(ctx.voice_client)
    del download_tasks[ctx.voice_client]
    del queues[ctx.voice_client]
    await ctx.voice_client.disconnect()


@bot.command(name="f", aliases=["F"], help="Pay respects")
async def ef(ctx: Context) -> None:
    await ctx.send(responses.get("F", ctx.author.mention if ctx.guild is not None else ctx.author.name))


@is_owner()
@bot.command(name="shutdown", aliases=["sd, shtdwn, exit"], help="Shut the bot down")
async def shutdown(ctx: Context) -> None:
    stop_downloads_all()
    for client in ctx.bot.voice_clients:
        await client.disconnect()

    await ctx.send(responses.get("GOODBYE"))
    await ctx.bot.logout()


@check(playing)
@check(member_and_bot_in_same_voice)
@check(member_in_voice)
@check(bot_in_voice)
@check(in_guild)
@bot.command(name="skip", brief="Skip songs in queue", help="If no arguments given, the bot skips to the next song. Otherwise, it skips the given amount of songs.")
async def skip(ctx: Context, params: str = "1") -> None:
    many = 1
    try:
        many = int(params)
    except ValueError:
        await ctx.send(responses.get("SKIP_INDEX_NOT_NUM", ctx.author.mention))
        return

    if many <= 0 or many > len(queues[ctx.voice_client].queue) + 1:
        await ctx.send(responses.get("BAD_SKIP_INDEX", ctx.author.mention))
        return

    queue = queues[ctx.voice_client]
    # Save loop state and turn looping off
    loop = queue.loop
    queue.loop = False

    # If we were originally looping, we drain all tracks
    # If not, we drain one less
    count = many if loop else many - 1
    for _ in range(count):
        queues[ctx.voice_client].next()
    
    # Restore loop state
    queue.loop = loop

    # If we're looping this will not change now_playing, so we start playing exactly the track we skipped to
    # If we're not looping, this will skip one more track before restarting playback, playing exactly the track we skipped to
    # This is because how we drained the tracks above
    ctx.voice_client.stop()
    await ctx.send(responses.get("SKIP"))


@check(queue_not_empty)
@check(member_and_bot_in_same_voice)
@check(member_in_voice)
@check(bot_in_voice)
@check(in_guild)
@bot.command(name="remove", aliases=["annihilate", "r"], help="Remove song(s) from queue")
async def remove(ctx: Context, index: int, end_index: int = None) -> None:
    if end_index is None:
        end_index = index

    removed_songs = queues[ctx.voice_client].remove(index - 1, end_index - 1)
    
    if removed_songs is None:
        await ctx.send(responses.get("BAD_REMOVE_INDICES", ctx.author.mention))
        return

    for song in removed_songs:
        await ctx.send(responses.get("SONG_REMOVED", song.title))


@check(member_and_bot_in_same_voice)
@check(member_in_voice)
@check(bot_in_voice)
@check(in_guild)
@bot.command(name="loop", help="[WIP] Check or set whether the bot is looping a track")
async def loop(ctx: Context, state: str="") -> None:
    if state == "":
        await ctx.send("Looping is currently " + ("on" if queues[ctx.voice_client].loop else "off") + ".")

    elif state.lower() == "on":
        queues[ctx.voice_client].loop = True
        await ctx.send("Looping enabled.")

    elif state.lower() == "off":
        queues[ctx.voice_client].loop = False
        await ctx.send("Looping disabled.")

    else:
        await ctx.send("Invalid argument '" + state + "'.")


def play_next(error: Exception, voice_client: VoiceClient) -> None:
    if error:
        print(error)
        return

    if voice_client not in queues:
        return

    queues[voice_client].next()
        
    if queues[voice_client].now_playing:      
        voice_client.play(source=queues[voice_client].now_playing.new_source(**FFMPEG_OPTIONS), after=lambda error: play_next(error, voice_client))


async def download_image(url: str) -> BytesIO:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return BytesIO(await response.read())


def stop_downloads_server(voice_client: VoiceClient) -> None:
    for task in download_tasks[voice_client]:
        task.cancel()
    download_tasks[voice_client].clear()


def stop_downloads_all() -> None:
    for tasks in download_tasks.values():
        for task in tasks:
            task.cancel()
    download_tasks.clear()


def string_splitter(string: str, delim: str, amount: int):
    ret = str()
    last_word = str()

    for char in string:
        last_word += char

        if char == delim:
            if len(ret + last_word) > amount:
                yield ret
                ret = last_word
            else:
                ret += last_word

            last_word = str()

    yield ret + last_word


bot.run(TOKEN)
