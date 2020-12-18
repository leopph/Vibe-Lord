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
        await ctx.send(f"{ctx.message.author.mention}, you fucking moron, there is no \"{source}\" source option!")
        return

    queue.put(tmp)
    await ctx.send(f"{ctx.message.author.mention} sure thing mate, Imma queue {tmp[0]} for ya!")

    if not voice_client.is_playing():
        play_next(ctx)




@bot.command(name="stop", aliases=["s"], help="Stop playback if currently playing")
async def stop(ctx: Context) -> None:
    voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_channel:
        voice_channel.stop()
        queue.queue.clear()




@bot.command(name="pause", help="Pause playback")
async def pause(ctx: Context) -> None:
    global voice_client

    if not voice_client or not voice_client.is_connected():
        await ctx.send(f"{ctx.message.author.mention} bruh, I'm not even in voice...")

    elif not voice_client.is_playing():
        await ctx.send(f"{ctx.message.author.mention} bruh, I'm not even playing anything...")

    else:
        voice_client.pause()
        await ctx.send(f"Alrighty, {ctx.message.author.mention}, I paused this shit for ya.")




@bot.command(name="resume", help="Resume playback")
async def resume(ctx: Context) -> None:
    global voice_client

    if not voice_client or not voice_client.is_connected():
        await ctx.send(f"{ctx.message.author.mention} bruh, I'm not even in voice...")

    elif not voice_client.is_paused():
        await ctx.send(f"{ctx.message.author.mention} you fucking cringe, I'm not paused!")

    else:
        voice_client.resume()
        await ctx.send(f"{ctx.message.author.mention} On it, chief. Resuming playback.")




@bot.command(name="connect", aliases=["c"], help="Connect to voice channel")
async def connect(ctx: Context) -> None:
    global voice_client

    if not voice_client or not voice_client.is_connected():
        voice_client = await ctx.message.author.voice.channel.connect()
    else:
        await ctx.send(f"{ctx.message.author.mention}... Dood... I'm already here...")




@bot.command(name="disconnect", aliases=["dc"], help="Disconnect from voice channel")
async def disconnect(ctx: Context) -> None:
    global voice_client

    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send(f"{ctx.message.author.mention}... bruuuuuuh... I'm not even here!")




@bot.command(name="f", help="Pay respects.")
async def ef(ctx: Context) -> None:
    await ctx.send(f"{ctx.message.author.mention}, I pay my respects.")




@bot.command(name="shutdown", aliases=["sd, shtdwn"], help="Shut the bot down")
async def shutdown(ctx: Context) -> None:
    global voice_client

    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()

    await ctx.send("Goodbye fellas!")

    await bot.logout()




@bot.command(name="skip", help="Skip to the next song in queue")
async def skip(ctx: Context) -> None:
    global voice_client
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        voice_client.stop()
        await ctx.send(f"Okay {ctx.message.author.name}, skipping.")

    


@bot.event
async def on_command_error(ctx: Context, error: str) -> None:
    await ctx.send(error)




def play_next(ctx: Context) -> None:
    if not queue.empty():
        global voice_client
        song = queue.get()
        voice_client.play(source=song[1], after=lambda e: play_next(ctx))




def play_tidal(search_str: str = "") -> tuple[str, discord.FFmpegPCMAudio]:
    track = tidal_session.search("track", search_str, limit=1).tracks[0]

    title = ", ".join([artist.name for artist in track.artists]) + " - " + track.name

    url = tidal_session.get_track_url(track.id)

    audio_source = discord.FFmpegPCMAudio(url)

    return (title, audio_source)




def play_yt(source: str = "", ) -> tuple[str, discord.FFmpegPCMAudio]:
    YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist':'True'}
    FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

    with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(f"ytsearch:{source}", download=False)['entries'][0]
        audio_source = discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS)
        return (info["title"], audio_source)




bot.run(TOKEN)
