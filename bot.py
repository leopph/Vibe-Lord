import os
import dotenv
import discord
import discord.utils
import discord.ext.commands
import tidalapi
import youtube_dl
from typing import Union
from discord import VoiceClient
from discord.ext.commands import Context
from queue import Queue
from response import Response




dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("DISCORD_GUILD")

tidal_session = tidalapi.Session()
tidal_session.login(os.getenv("TIDAL_UNAME"), os.getenv("TIDAL_PWD"))

bot = discord.ext.commands.Bot(command_prefix=".")

voice_client: Union[VoiceClient, None] = None

queue: Queue[tuple[str, discord.FFmpegPCMAudio]] = Queue()




@bot.event
async def on_ready():
    print("Ready.")




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
    await ctx.send(Response.get("QUEUE").format(tmp[0]))

    if not voice_client.is_playing():
        play_next(ctx)




@bot.command(name="stop", aliases=["s"], help="Stop playback if currently playing")
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




@bot.command(name="f", help="Pay respects.")
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

    


@bot.event
async def on_command_error(ctx: Context, error: str) -> None:
    await ctx.send(error)




def play_next(ctx: Context) -> None:
    if not queue.empty():
        global voice_client
        song = queue.get()
        voice_client.play(source=song[1], after=lambda e: play_next(ctx))




def play_tidal(search_str: str = "") -> tuple[str, discord.FFmpegPCMAudio]:
    FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
    track = tidal_session.search("track", search_str, limit=1).tracks[0]

    title = ", ".join([artist.name for artist in track.artists]) + " - " + track.name

    url = tidal_session.get_track_url(track.id)

    audio_source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)

    return (title, audio_source)




def play_yt(source: str = "", ) -> tuple[str, discord.FFmpegPCMAudio]:
    YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist':'True', "quiet": "True"}
    FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

    with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(f"ytsearch:{source}", download=False)['entries'][0]
        audio_source = discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS)
        return (info["title"], audio_source)




bot.run(TOKEN)
