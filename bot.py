import os
from discord.ext.commands.core import is_owner
from discord.ext.commands.errors import CommandError
import dotenv
import aiohttp
import tidalapi
import re
from discord import VoiceClient, File, voice_client
from discord.ext.commands import Bot, Context, check
from youtube_dl import YoutubeDL
from response import Response
from songqueue import SongQueue
from song import Song
from io import BytesIO
from exceptions import InvalidCommandConditionError




dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
URL = re.compile(r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))")

tidal_session = tidalapi.Session()
tidal_session.login(os.getenv("TIDAL_UNAME"), os.getenv("TIDAL_PWD"))

bot = Bot(command_prefix=".")

queues: dict[VoiceClient, SongQueue] = dict()




def user_in_voice():
    def predicate(ctx: Context) -> bool:
        if (ctx.author.voice is None
            or ctx.author.voice.channel not in ctx.guild.voice_channels
                or (ctx.voice_client is not None and ctx.voice_client.channel != ctx.author.voice.channel)):
            raise InvalidCommandConditionError(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))
        return True
    return check(predicate)

def bot_in_voice():
    def predicate(ctx: Context) -> bool:
        if ctx.voice_client is None:
            raise InvalidCommandConditionError(Response.get("NOT_IN_VOICE", ctx.author.mention))
        return True
    return check(predicate)

def bot_not_in_voice():
    def predicate(ctx: Context) -> bool:
        if ctx.voice_client is not None:
            raise InvalidCommandConditionError(Response.get("ALREADY_IN_VOICE", ctx.message.author.mention))
        return True
    return check(predicate)

def playing():
    def predicate(ctx: Context) -> bool:
        if ctx.voice_client not in queues or queues[ctx.voice_client].now_playing is None:
            raise InvalidCommandConditionError(Response.get("NOT_PLAYING", ctx.author.mention))
        return True
    return check(predicate)

def queue_not_empty():
    def predicate(ctx: Context) -> bool:
        if ctx.voice_client not in queues or queues[ctx.voice_client].is_empty():
            raise InvalidCommandConditionError(Response.get("QUEUE_EMPTY"))
        return True
    return check(predicate)

def queue_not_empty_or_playing():
    def predicate(ctx: Context) -> bool:
        if ctx.voice_client not in queues or (queues[ctx.voice_client].is_empty() and queues[ctx.voice_client].now_playing is None):
            raise InvalidCommandConditionError(Response.get("QUEUE_EMPTY"))
        return True
    return check(predicate)

def paused():
    def predicate(ctx: Context) -> bool:
        if ctx.voice_client is None or not ctx.voice_client.is_paused():
            raise InvalidCommandConditionError(Response.get("NOT_PAUSED", ctx.message.author.mention))
        return True
    return check(predicate)




@bot.event
async def on_ready():
    print("Ready.")




@bot.event
async def on_command_error(ctx: Context, error: CommandError) -> None:
    await ctx.send(error)




@user_in_voice()
@bot_in_voice()
@queue_not_empty()
@bot.command(name="shuffle", help="Randomly reorder the current queue")
async def shuffle(ctx: Context) -> None:
    queues[ctx.voice_client].shuffle()
    await ctx.send(Response.get("SHUFFLE"))




@user_in_voice()
@bot_in_voice()
@playing()
@bot.command(name="seek", help="Skip to a certain part of the current song")
async def seek(ctx: Context, seconds: int) -> None:   
    if queues[ctx.voice_client].now_playing.length >= seconds >= 0:
        seek_opts = FFMPEG_OPTIONS.copy()
        seek_opts["before_options"] = FFMPEG_OPTIONS["before_options"] + f" -ss {seconds}"
        ctx.voice_client.source = queues[ctx.voice_client].now_playing.new_source(**seek_opts)
        return
    
    await ctx.send(Response.get("BAD_TIMESTAMP", ctx.author.mention))




@bot_in_voice()
@playing()
@bot.command(name="nowplaying", aliases=["np"], help="Show the current song")
async def now_paying(ctx: Context) -> None:
    await ctx.send(f"Now playing: {queues[ctx.voice_client].now_playing.title}", file=File(queues[ctx.voice_client].now_playing.image, "cover.jpg"))




@bot_in_voice()
@queue_not_empty_or_playing()
@bot.command(name="queue", aliases=["q", "que", "queueue"], help="Show songs in queue")
async def show_queue(ctx: Context):
    await ctx.send("--- " + queues[ctx.voice_client].now_playing.title + " ---\n" + "\n".join([str(index + 1) + ". " + song.title for index, song in enumerate(queues[ctx.voice_client].queue)]))




@user_in_voice()
@bot.command(name="youtube", aliases=["y"], help="Queue track from YouTube")
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


    if not ctx.voice_client:
        await ctx.message.author.voice.channel.connect()
        queues[ctx.voice_client] = SongQueue()


    try:
        for video in yt_results(source):
            if video is not None: # TODO kell else ág rendesen lekezelni az esetet, ha invalid az egész link
                title = video["artist"] + " - " + video["track"] if video["artist"] and video["track"] else video["title"]
                song = Song(title, video["duration"], video["url"], await download_image(video["thumbnails"][-1]["url"]))

                queues[ctx.voice_client].add(song)

                await ctx.send(Response.get("QUEUE", song.title))

                if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                    play_next(None, ctx.voice_client)

        
    except IndexError:
        await ctx.send(Response.get("NO_RESULT", ctx.author.mention))




@user_in_voice()
@bot.command(name="tidal", aliases=["t"], help="Queue track from Tidal")
async def tidal(ctx: Context, *, source) -> None:
    try:
        track = tidal_session.search("track", source, limit=1).tracks[0]
        title = ", ".join([artist.name for artist in track.artists]) + " - " + track.name
        url = tidal_session.get_track_url(track.id)
        song = Song(title, track.duration, url, await download_image(track.album.image))

        if not ctx.voice_client:
            await ctx.message.author.voice.channel.connect()
            queues[ctx.voice_client] = SongQueue()

        queues[ctx.voice_client].add(song)
        await ctx.send(Response.get("QUEUE", song.title))

        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            play_next(None, ctx.voice_client)

    except IndexError:
        await ctx.send(Response.get("NO_RESULT", ctx.author.mention))




@user_in_voice()
@bot_in_voice()
@playing()
@bot.command(name="stop", help="Stop playback and clear queue")
async def stop(ctx: Context) -> None:
    queues[ctx.voice_client].clear()
    ctx.voice_client.stop()




@user_in_voice()
@bot_in_voice()
@queue_not_empty()
@bot.command(name="clear", brief="Clear queue", help="Remove all the songs from the queue. This does not stop current playback.")
async def clear(ctx: Context) -> None:
    queues[ctx.voice_client].clear()




@user_in_voice()
@bot_in_voice()
@playing()
@bot.command(name="pause", help="Pause playback")
async def pause(ctx: Context) -> None:
    ctx.voice_client.pause()
    await ctx.send(Response.get("PAUSE"))




@user_in_voice()
@bot_in_voice()
@paused()
@bot.command(name="resume", help="Resume playback")
async def resume(ctx: Context) -> None:
    ctx.voice_client.resume()
    await ctx.send(Response.get("RESUME"))




@user_in_voice()
@bot_not_in_voice()
@bot.command(name="connect", aliases=["c"], help="Connect to voice channel")
async def connect(ctx: Context) -> None:
    await ctx.message.author.voice.channel.connect()
    queues[ctx.voice_client] = SongQueue()




@user_in_voice()
@bot_in_voice()
@bot.command(name="disconnect", aliases=["dc"], help="Disconnect from voice channel")
async def disconnect(ctx: Context) -> None:
    del queues[ctx.voice_client]
    await ctx.voice_client.disconnect()




@bot.command(name="f", aliases=["F"], help="Pay respects")
async def ef(ctx: Context) -> None:
    await ctx.send(Response.get("F", ctx.message.author.mention))




@is_owner()
@bot.command(name="shutdown", aliases=["sd, shtdwn"], help="Shut the bot down")
async def shutdown(ctx: Context) -> None:   
    for client in ctx.bot.voice_clients:
        await client.disconnect()

    await ctx.send(Response.get("GOODBYE"))
    await ctx.bot.logout()




@user_in_voice()
@bot_in_voice()
@playing()
@bot.command(name="skip", brief="Skip songs in queue", help="If no arguments given, the bot skips to the next song. Otherwise, it skips the given amount of songs.")
async def skip(ctx: Context, many: int = 1) -> None:
    if many <= 0 or many > len(queues[ctx.voice_client].queue) + 1:
        await ctx.send(Response.get("BAD_SKIP_REQUEST", ctx.author.mention))
        return
    
    for i in range(many-1):
        queues[ctx.voice_client].remove(0, 0)

    ctx.voice_client.stop()
    await ctx.send(Response.get("SKIP"))




@user_in_voice()
@bot_in_voice()
@queue_not_empty()
@bot.command(name="remove", aliases=["annihilate", "r"], help="Remove song(s) from queue")
async def remove(ctx: Context, index: int, end_index: int = None) -> None:
    if end_index is None:
        end_index = index

    removed_songs = queues[ctx.voice_client].remove(index - 1, end_index - 1)
    
    if removed_songs is None:
        await ctx.send(Response.get("BAD_DELETE_REQUEST", ctx.author.mention))
        return

    for song in removed_songs:
        await ctx.send(Response.get("SONG_REMOVED", song.title))
    
        

    


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




bot.run(TOKEN)
