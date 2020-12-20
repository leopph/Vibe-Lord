import os
import dotenv
import tidalapi
import re
from typing import Union
from discord import VoiceClient
from discord import Embed
from discord.ext.commands import Context
from discord.ext.commands import Bot
from youtube_dl import YoutubeDL
from response import Response
from songqueue import SongQueue
from song import Song




dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
URL = re.compile(r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))")

tidal_session = tidalapi.Session()
tidal_session.login(os.getenv("TIDAL_UNAME"), os.getenv("TIDAL_PWD"))

bot = Bot(command_prefix=".")

queues: dict[VoiceClient, SongQueue] = dict()




@bot.event
async def on_ready():
    print("Ready.")




@bot.event
async def on_command_error(ctx: Context, error: str) -> None:
    await ctx.send(error)




@bot.command(name="seek", help="Skip to a certain part of the current song")
async def seek(ctx: Context, seconds: int) -> None:
    if not queues[ctx.voice_client].now_playing:
        await ctx.send("There's nothing to seek, I'm not playing anything currently.")
    
    elif queues[ctx.voice_client].now_playing.length >= seconds >= 0:
        seek_opts = FFMPEG_OPTIONS.copy()
        seek_opts["before_options"] = FFMPEG_OPTIONS["before_options"] + f" -ss {seconds}"
        ctx.voice_client.source=queues[ctx.voice_client].now_playing.new_source(**seek_opts)
    
    else:
        await ctx.send("Invalid timestamp.")




@bot.command(name="nowplaying", aliases=["np"], help="Show the current song")
async def now_paying(ctx: Context) -> None:
    await ctx.send(f"Now playing: {queues[ctx.voice_client].now_playing.title}" if queues[ctx.voice_client].now_playing else f"Currently not playing anything!", embed=Embed().set_image(url=queues[ctx.voice_client].now_playing.image) if queues[ctx.voice_client].now_playing and queues[ctx.voice_client].now_playing.image else None)




@bot.command(name="queue", aliases=["q", "que", "queueue"], help="Show songs in queue")
async def show_queue(ctx: Context):
    await ctx.send("--- " + queues[ctx.voice_client].now_playing.title + " ---\n" + "\n".join([song.title for song in queues[ctx.voice_client].queue]) if queues[ctx.voice_client].now_playing else "Queue is empty.")




@bot.command(name="youtube", aliases=["y"], help="Play track from YouTube")
async def youtube(ctx: Context, *, source) -> None:
    YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist':'True', "quiet": "True"}

    with YoutubeDL(YDL_OPTIONS) as ydl:
        if URL.match(source):
            info = ydl.extract_info(source, download=False)
        else:
            info = ydl.extract_info(f"ytsearch:{source}", download=False)['entries'][0]

        title = info["artist"] + " - " + info["track"] if info["artist"] and info["track"] else info["title"]
        song = Song(title, info["duration"], info["url"], info["thumbnails"][-1]["url"])

    if ctx.message.author.voice.channel not in [client.channel for client in ctx.bot.voice_clients]:
        voice_client = await ctx.message.author.voice.channel.connect()
        queues[voice_client] = SongQueue()

    queues[ctx.voice_client].add(song)
    await ctx.send(Response.get("QUEUE").format(song.title))

    if not ctx.voice_client.is_playing():
        play_next(ctx.voice_client)




@bot.command(name="tidal", aliases=["t"], help="Play track from Tidal")
async def tidal(ctx: Context, *, source) -> None:
    track = tidal_session.search("track", source, limit=1).tracks[0]
    title = ", ".join([artist.name for artist in track.artists]) + " - " + track.name
    url = tidal_session.get_track_url(track.id)
    song = Song(title, track.duration, url, track.album.image)

    if ctx.message.author.voice.channel not in [client.channel for client in ctx.bot.voice_clients]:
        voice_client = await ctx.message.author.voice.channel.connect()
        queues[voice_client] = SongQueue()

    queues[ctx.voice_client].add(song)
    await ctx.send(Response.get("QUEUE").format(song.title))

    if not ctx.voice_client.is_playing():
        play_next(ctx.voice_client)




@bot.command(name="stop", help="Stop playback if currently playing")
async def stop(ctx: Context) -> None:
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        queues[ctx.voice_client].clear()




@bot.command(name="pause", help="Pause playback")
async def pause(ctx: Context) -> None:
    if not ctx.voice_client.is_connected():
        await ctx.send(Response.get("NOT_IN_VOICE").format(ctx.message.author.mention))

    elif not ctx.voice_client.is_playing():
        await ctx.send(Response.get("NOT_PLAYING").format(ctx.message.author.mention))

    else:
        ctx.voice_client.pause()
        await ctx.send(Response.get("PAUSE"))




@bot.command(name="resume", help="Resume playback")
async def resume(ctx: Context) -> None:
    if not ctx.voice_client.is_connected():
        await ctx.send(Response.get("NOT_IN_VOICE").format(ctx.message.author.mention))

    elif not ctx.voice_client.is_paused():
        await ctx.send(Response.get("NOT_PAUSED").format(ctx.message.author.mention))

    else:
        ctx.voice_client.resume()
        await ctx.send(Response.get("RESUME"))




@bot.command(name="connect", aliases=["c"], help="Connect to voice channel")
async def connect(ctx: Context) -> None:
    if not ctx.voice_client:
        await ctx.message.author.voice.channel.connect()
    else:
        await ctx.send(Response.get("ALREADY_IN_VOICE").format(ctx.message.author.mention))




@bot.command(name="disconnect", aliases=["dc"], help="Disconnect from voice channel")
async def disconnect(ctx: Context) -> None:
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    else:
        await ctx.send(Response.get("NOT_IN_VOICE").format(ctx.message.author.mention))




@bot.command(name="f", help="Pay respects")
async def ef(ctx: Context) -> None:
    await ctx.send(Response.get("F").format(ctx.message.author.mention))




@bot.command(name="shutdown", aliases=["sd, shtdwn"], help="Shut the bot down")
async def shutdown(ctx: Context) -> None:
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

    await ctx.send(Response.get("GOODBYE"))

    await ctx.bot.logout()




@bot.command(name="skip", help="Skip to the next song in queue")
async def skip(ctx: Context) -> None:
    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        ctx.voice_client.stop()
        await ctx.send(Response.get("SKIP"))




def play_next(voice_client: VoiceClient) -> None:
    queues[voice_client].next()

    if queues[voice_client].now_playing:      
        voice_client.play(source=queues[voice_client].now_playing.new_source(**FFMPEG_OPTIONS), after=lambda e: play_next(voice_client))




bot.run(TOKEN)
