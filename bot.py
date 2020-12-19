import os
import dotenv
import tidalapi
import youtube_dl
import re
from typing import Union
from queue import Queue
from discord import VoiceClient
from discord import Embed
from discord.ext.commands import Context
from discord.ext.commands import Bot
from response import Response
from song import Song




dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
URL = re.compile(r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))")

tidal_session = tidalapi.Session()
tidal_session.login(os.getenv("TIDAL_UNAME"), os.getenv("TIDAL_PWD"))

bot = Bot(command_prefix=".")

voice_client: Union[VoiceClient, None] = None

queue: Queue[Song] = Queue()
current_song: Union[Song, None] = None




@bot.event
async def on_ready():
    print("Ready.")


@bot.event
async def on_command_error(ctx: Context, error: str) -> None:
    await ctx.send("oof")




@bot.command(name="seek", help="Skip to a certain part of the current song")
async def seek(ctx: Context, seconds: int) -> None:
    if not current_song:
        await ctx.send("There's nothing to seek, I'm not playing anything currently.")
    
    elif current_song.length >= seconds >= 0:
        seek_opts = FFMPEG_OPTIONS.copy()
        seek_opts["before_options"] = FFMPEG_OPTIONS["before_options"] + f" -ss {seconds}"
        voice_client.source=current_song.new_source(**seek_opts)
    
    else:
        await ctx.send("Invalid timestamp.")




@bot.command(name="nowplaying", aliases=["np"], help="Show the current song")
async def now_paying(ctx: Context) -> None:
    await ctx.send(f"Now playing: {current_song.title}" if current_song else f"Currently not playing anything!", embed=Embed().set_image(url=current_song.image) if current_song.image else None)




@bot.command(name="queue", aliases=["q", "que", "queueue"], help="Show songs in queue")
async def show_queue(ctx: Context):
    await ctx.send("--- " + current_song.title + " ---\n" + "\n".join([song.title for song in queue.queue]) if current_song else "Queue is empty.")




@bot.command(name="play", aliases=["p"], help="Play track from the parameter source")
async def queue_new_song(ctx: Context, source: str, *args) -> None:
    global voice_client

    if not voice_client or not voice_client.is_connected():
        voice_client = await ctx.message.author.voice.channel.connect()

    target = " ".join(args)

    tmp = None

    if source == "t" or source == "tidal":
        tmp = play_tidal(target)

    elif source == "y" or source == "youtube":
        tmp = play_yt(target)

    else:
        await ctx.send(Response.get("BAD_SOURCE").format(ctx.message.author.mention, source))
        return

    queue.put(tmp)
    await ctx.send(Response.get("QUEUE").format(tmp.title))

    if not voice_client.is_playing():
        play_next()




@bot.command(name="stop", help="Stop playback if currently playing")
async def stop(ctx: Context) -> None:
    global voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        queue.queue.clear()




@bot.command(name="pause", help="Pause playback")
async def pause(ctx: Context) -> None:
    global voice_client

    if not voice_client or not voice_client.is_connected():
        await ctx.send(Response.get("NOT_IN_VOICE").format(ctx.message.author.mention))

    elif not voice_client.is_playing():
        await ctx.send(Response.get("NOT_PLAYING").format(ctx.message.author.mention))

    else:
        voice_client.pause()
        await ctx.send(Response.get("PAUSE"))




@bot.command(name="resume", help="Resume playback")
async def resume(ctx: Context) -> None:
    global voice_client

    if not voice_client or not voice_client.is_connected():
        await ctx.send(Response.get("NOT_IN_VOICE").format(ctx.message.author.mention))

    elif not voice_client.is_paused():
        await ctx.send(Response.get("NOT_PAUSED").format(ctx.message.author.mention))

    else:
        voice_client.resume()
        await ctx.send(Response.get("RESUME"))




@bot.command(name="connect", aliases=["c"], help="Connect to voice channel")
async def connect(ctx: Context) -> None:
    global voice_client

    if not voice_client or not voice_client.is_connected():
        voice_client = await ctx.message.author.voice.channel.connect()
    else:
        await ctx.send(Response.get("ALREADY_IN_VOICE").format(ctx.message.author.mention))




@bot.command(name="disconnect", aliases=["dc"], help="Disconnect from voice channel")
async def disconnect(ctx: Context) -> None:
    global voice_client

    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send(Response.get("NOT_IN_VOICE").format(ctx.message.author.mention))




@bot.command(name="f", help="Pay respects")
async def ef(ctx: Context) -> None:
    await ctx.send(Response.get("F").format(ctx.message.author.mention))




@bot.command(name="shutdown", aliases=["sd, shtdwn"], help="Shut the bot down")
async def shutdown(ctx: Context) -> None:
    global voice_client

    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()

    await ctx.send(Response.get("GOODBYE"))

    await bot.logout()




@bot.command(name="skip", help="Skip to the next song in queue")
async def skip(ctx: Context) -> None:
    global voice_client
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        voice_client.stop()
        await ctx.send(Response.get("SKIP"))




def play_next() -> None:
    global current_song

    if not queue.empty():
        global voice_client
        current_song = queue.get()
        voice_client.play(source=current_song.new_source(**FFMPEG_OPTIONS), after=lambda e: play_next())
    
    else:
        current_song = None




def play_tidal(search_str: str = "") -> Song:
    track = tidal_session.search("track", search_str, limit=1).tracks[0]
    title = ", ".join([artist.name for artist in track.artists]) + " - " + track.name
    url = tidal_session.get_track_url(track.id)

    return Song(title, track.duration, url, track.album.image)




def play_yt(source: str = "", ) -> Song:
    YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist':'True', "quiet": "True"}

    with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
        if URL.match(source):
            info = ydl.extract_info(source, download=False)
            print("url match")
        else:
            info = ydl.extract_info(f"ytsearch:{source}", download=False)['entries'][0]

        title = info["artist"] + " - " + info["track"] if info["artist"] and info["track"] else info["title"]
        return Song(title, info["duration"], info["url"], info["thumbnails"][-1]["url"])




bot.run(TOKEN)
