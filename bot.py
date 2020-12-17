import os
import sys
from discord.abc import Connectable
from discord.channel import VoiceChannel
from discord.voice_client import VoiceClient
import dotenv
import discord
import discord.utils
import discord.ext.commands
import tidalapi
import youtube_dl



dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("DISCORD_GUILD")


tidal_session = tidalapi.Session()
tidal_session.login(os.getenv("TIDAL_UNAME"), os.getenv("TIDAL_PWD"))

bot = discord.ext.commands.Bot(command_prefix=".")


async def play_tidal(voice: discord.VoiceClient, search_str: str = None) -> None:
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



@bot.command(name="disconnect", aliases=["dc"], help="Disconnect from voice")
async def disconnect(ctx: discord.ext.commands.Context) -> None:
    for voice in bot.voice_clients:
        if (voice.is_connected()):
            await voice.disconnect()



@bot.command(name="stop", aliases=["s"], help="Stop playback if currently playing")
async def stop(ctx: discord.ext.commands.Context) -> None:
    voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_channel:
        voice_channel.stop()



@bot.command(name="play", aliases=["p"], help="Play track from the parameter source")
async def play(ctx: discord.ext.commands.Context, source: str, *args) -> None:
    voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if (not voice_channel):
        await ctx.message.author.voice.channel.connect()
        voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    voice_channel.stop()

    target = ""
    for arg in args:
        target += arg + " "

    target = target[0:-1]

    if (source == "t" or source == "tidal"):
        await ctx.message.channel.send(await play_tidal(voice_channel, target))
    elif(source == "y" or source == "youtube"):
        await ctx.message.channel.send(await play_yt(voice_channel, target))
    else:
        await ctx.message.channel.send(f"Unknown source: \"{source}\"")


@bot.command(name="f", help="Pay respects.")
async def ef(ctx: discord.ext.commands.Context) -> None:
    pass


@bot.event
async def on_command_error(ctx: discord.ext.commands.Context, error, *args, **kwargs):
    await ctx.message.channel.send(f"mi a faszom ez a geci")



bot.run(TOKEN)
