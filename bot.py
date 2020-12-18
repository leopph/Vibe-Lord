import os
import dotenv
import discord
import discord.utils
import discord.ext.commands
import tidalapi
import youtube_dl
import contextlib
from typing import Union
from discord import VoiceClient
from discord.ext.commands import Context



dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("DISCORD_GUILD")


tidal_session = tidalapi.Session()
tidal_session.login(os.getenv("TIDAL_UNAME"), os.getenv("TIDAL_PWD"))

bot = discord.ext.commands.Bot(command_prefix=".")

voice_client: Union[None, VoiceClient] = None




async def play_tidal(voice: VoiceClient, search_str: str = None) -> None:
    track = tidal_session.search("track", search_str).tracks[0]
    voice.play(discord.FFmpegPCMAudio(tidal_session.get_track_url(track.id)))

    artists = ""
    for artist in track.artists:
        artists += artist.name + ", "
    
    return artists[0:-2] + " - " + track.name




async def play_yt(voice: VoiceClient, url: str = None, ) -> str:
    YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist':'True'}
    FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

    with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(url, download=False)
    URL = info['formats'][0]['url']

    voice.play(discord.FFmpegPCMAudio(URL, **FFMPEG_OPTIONS))

    return info["title"]




@bot.event
async def on_ready():
    print("Ready.")









@bot.command(name="stop", aliases=["s"], help="Stop playback if currently playing")
async def stop(ctx: Context) -> None:
    voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_channel:
        voice_channel.stop()




@bot.command(name="play", aliases=["p"], help="Play track from the parameter source")
async def play(ctx: discord.ext.commands.Context, source: str, *args) -> None:
    with contextlib.suppress(Exception):
        global voice_client
        voice_client = await ctx.message.author.voice.channel.connect()

    voice_client.stop()

    target = ""
    for arg in args:
        target += arg + " "

    target = target[0:-1]

    if (source == "t" or source == "tidal"):
        await ctx.message.channel.send(await play_tidal(voice_client, target))
    elif(source == "y" or source == "youtube"):
        await ctx.message.channel.send(await play_yt(voice_client, target))
    else:
        await ctx.message.channel.send(f"Unknown source: \"{source}\"")


@bot.command(name="f", help="Pay respects.")
async def ef(ctx: Context) -> None:
    await ctx.message.channel.send(ctx.message.author.name + ", I pay my respects.")




@bot.command(name="pause", help="Pause playback.")
async def pause(ctx: Context) -> None:
    global voice_client
    if (not voice_client or not voice_client.is_connected()):
        await ctx.send(f"{ctx.message.author.mention} bruh, I'm not even in voice...")

    if (not voice_client.is_playing()):
        await ctx.send(f"{ctx.message.author.mention} bruh, I'm not even playing anything...")




@bot.command(name="connect", aliases=["c"], help="Connect to voice channel")
async def connect(ctx: Context):
    global voice_client
    if (not voice_client or not voice_client.is_connected()):
        voice_client = await ctx.message.author.voice.channel.connect()
    else:
        await ctx.send(f"{ctx.message.author.mention}... Dood... I'm already here...")




@bot.command(name="disconnect", aliases=["dc"], help="Disconnect from voice channel")
async def disconnect(ctx: Context) -> None:
    global voice_client
    if voice_client and voice_client.is_connected():
        voice_client = await voice_client.disconnect()
    else:
        await ctx.send(f"{ctx.message.author.mention}... bruuuuuuh... I'm not even here!")

    


@bot.event
async def on_command_error(ctx: Context, error, *args, **kwargs):
    await ctx.message.channel.send(f"mi a faszom ez a geci\n{error}")




bot.run(TOKEN)
