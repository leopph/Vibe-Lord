import os
import dotenv
import aiohttp
import tidalapi
import re
from discord import VoiceClient, File
from discord.ext.commands import Bot, Context
from youtube_dl import YoutubeDL
from response import Response
from songqueue import SongQueue
from song import Song
from io import BytesIO




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




@bot.command(name="shuffle", help="Randomly reorder the current queue")
async def shuffle(ctx: Context) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels:
        await ctx.send(Response.get("USER_NOT_IN_VOICE"), ctx.author.mention)
        return

    if not ctx.voice_client:
        await ctx.send(Response.get("NOT_IN_VOICE"), ctx.author.mention)
        return

    if ctx.author.voice.channel != ctx.voice_client.channel:
        await ctx.send(Response.get("USER_NOT_IN_VOICE"), ctx.author.mention)
        return

    if queues[ctx.voice_client].is_empty():
        await ctx.send(Response.get("QUEUE_EMPTY"))
        return

    queues[ctx.voice_client].shuffle()
    await ctx.send(Response.get("SHUFFLE"))




@bot.command(name="seek", help="Skip to a certain part of the current song")
async def seek(ctx: Context, seconds: int) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not ctx.voice_client:
        await ctx.send(Response.get("NOT_IN_VOICE", ctx.author.mention))

    elif ctx.author.voice.channel not in [client.channel for client in ctx.bot.voice_clients]:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not queues[ctx.voice_client].now_playing:
        await ctx.send(Response.get("NOT_PLAYING"), ctx.author.mention)
    
    elif queues[ctx.voice_client].now_playing.length >= seconds >= 0:
        seek_opts = FFMPEG_OPTIONS.copy()
        seek_opts["before_options"] = FFMPEG_OPTIONS["before_options"] + f" -ss {seconds}"
        ctx.voice_client.source = queues[ctx.voice_client].now_playing.new_source(**seek_opts)
    
    else:
        await ctx.send(Response.get("BAD_TIMESTAMP", ctx.author.mention))




@bot.command(name="nowplaying", aliases=["np"], help="Show the current song")
async def now_paying(ctx: Context) -> None:
    if not ctx.voice_client:
        await ctx.send(Response.get("NOT_IN_VOICE", ctx.author.mention))

    elif queues[ctx.voice_client] is None:
        await ctx.send(Response.get("NOT_PLAYING", ctx.author.mention))

    else:
        await ctx.send(f"Now playing: {queues[ctx.voice_client].now_playing.title}", file=File(queues[ctx.voice_client].now_playing.image, "cover.jpg"))




@bot.command(name="queue", aliases=["q", "que", "queueue"], help="Show songs in queue")
async def show_queue(ctx: Context):
    if not ctx.voice_client:
        await ctx.send(Response.get("NOT_IN_VOICE", ctx.author.mention))

    elif not queues[ctx.voice_client].now_playing:
        await ctx.send(Response.get("QUEUE_EMPTY"))

    else:
        await ctx.send("--- " + queues[ctx.voice_client].now_playing.title + " ---\n" + "\n".join([str(index + 1) + ". " + song.title for index, song in enumerate(queues[ctx.voice_client].queue)]))




@bot.command(name="youtube", aliases=["y"], help="Play track from YouTube")
async def youtube(ctx: Context, *, source) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels or (ctx.voice_client and ctx.author.voice.channel != ctx.voice_client.channel):
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))
        return

    try:
        songs = set()

        YDL_OPTIONS = {"format": "bestaudio", "quiet": "True", "ignoreerrors": "True"}

        with YoutubeDL(YDL_OPTIONS) as ydl:
            if URL.match(source):
                info = ydl.extract_info(source, download=False)

                if "entries" in info:
                    for video in info["entries"]:
                        if video:
                            title = video["artist"] + " - " + video["track"] if video["artist"] and video["track"] else video["title"]
                            songs.add(Song(title, video["duration"], video["url"], await download_image(video["thumbnails"][-1]["url"])))

                else:
                    title = info["artist"] + " - " + info["track"] if info["artist"] and info["track"] else info["title"]
                    songs.add(Song(title, info["duration"], info["url"], await download_image(info["thumbnails"][-1]["url"])))

            else:
                info = ydl.extract_info(f"ytsearch:{source}", download=False)['entries'][0]
                title = info["artist"] + " - " + info["track"] if info["artist"] and info["track"] else info["title"]
                songs.add(Song(title, info["duration"], info["url"], await download_image(info["thumbnails"][-1]["url"])))

        if not ctx.voice_client:
            await ctx.message.author.voice.channel.connect()
            queues[ctx.voice_client] = SongQueue()

        for song in songs:
            queues[ctx.voice_client].add(song)

        await ctx.send(Response.get("QUEUE", ", ".join([song.title for song in songs])))

        if not ctx.voice_client.is_playing():
            play_next(ctx.voice_client)
            
    except IndexError:
        await ctx.send(Response.get("NO_RESULT", ctx.author.mention))




@bot.command(name="tidal", aliases=["t"], help="Play track from Tidal")
async def tidal(ctx: Context, *, source) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels or (ctx.voice_client and ctx.author.voice.channel != ctx.voice_client.channel):
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))
        return

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

        if not ctx.voice_client.is_playing():
            play_next(ctx.voice_client)

    except IndexError:
        await ctx.send(Response.get("NO_RESULT", ctx.author.mention))




@bot.command(name="stop", help="Stop playback if currently playing")
async def stop(ctx: Context) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not ctx.voice_client:
        await ctx.send(Response.get("NOT_IN_VOICE", ctx.author.mention))

    elif ctx.author.voice.channel not in [client.channel for client in ctx.bot.voice_clients]:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not queues[ctx.voice_client].now_playing:
        await ctx.send(Response.get("NOT_PLAYING"), ctx.author.mention)

    else:
        queues[ctx.voice_client].clear()
        ctx.voice_client.stop() # ez valamiért kipergeti a play_next-et




@bot.command(name="pause", help="Pause playback")
async def pause(ctx: Context) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not ctx.voice_client:
        await ctx.send(Response.get("NOT_IN_VOICE", ctx.author.mention))

    elif ctx.author.voice.channel not in [client.channel for client in ctx.bot.voice_clients]:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not queues[ctx.voice_client].now_playing or not ctx.voice_client.is_playing():
        await ctx.send(Response.get("NOT_PLAYING"), ctx.author.mention)

    else:
        ctx.voice_client.pause()
        await ctx.send(Response.get("PAUSE"))




@bot.command(name="resume", help="Resume playback")
async def resume(ctx: Context) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not ctx.voice_client:
        await ctx.send(Response.get("NOT_IN_VOICE", ctx.author.mention))

    elif ctx.author.voice.channel not in [client.channel for client in ctx.bot.voice_clients]:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not queues[ctx.voice_client].now_playing or not ctx.voice_client.is_paused():
        await ctx.send(Response.get("NOT_PAUSED", ctx.message.author.mention))
        
    else:
        ctx.voice_client.resume()
        await ctx.send(Response.get("RESUME"))




@bot.command(name="connect", aliases=["c"], help="Connect to voice channel")
async def connect(ctx: Context) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels or (ctx.voice_client and ctx.author.voice.channel != ctx.voice_client.channel):
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif ctx.voice_client:
        await ctx.send(Response.get("ALREADY_IN_VOICE", ctx.message.author.mention))

    else:
        await ctx.message.author.voice.channel.connect()
        queues[ctx.voice_client] = SongQueue()




@bot.command(name="disconnect", aliases=["dc"], help="Disconnect from voice channel")
async def disconnect(ctx: Context) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels or (ctx.voice_client and ctx.author.voice.channel != ctx.voice_client.channel):
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not ctx.voice_client:
        await ctx.send(Response.get("NOT_IN_VOICE", ctx.message.author.mention))

    else:
        del queues[ctx.voice_client]
        await ctx.voice_client.disconnect()




@bot.command(name="f", aliases=["F"], help="Pay respects")
async def ef(ctx: Context) -> None:
    await ctx.send(Response.get("F", ctx.message.author.mention))




@bot.command(name="shutdown", aliases=["sd, shtdwn"], help="Shut the bot down")
async def shutdown(ctx: Context) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels or (ctx.voice_client and ctx.author.voice.channel != ctx.voice_client.channel):
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))
        return

    for client in ctx.bot.voice_clients:
        await client.disconnect()

    queues.clear()

    await ctx.send(Response.get("GOODBYE"))
    await ctx.bot.logout()




@bot.command(name="skip", help="Skip to the next song in queue")
async def skip(ctx: Context) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not ctx.voice_client:
        await ctx.send(Response.get("NOT_IN_VOICE", ctx.author.mention))

    elif ctx.author.voice.channel not in [client.channel for client in ctx.bot.voice_clients]:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not queues[ctx.voice_client].now_playing:
        await ctx.send(Response.get("NOT_PLAYING"), ctx.author.mention)

    else:
        ctx.voice_client.stop()
        await ctx.send(Response.get("SKIP"))




@bot.command(name="remove", aliases=["annihilate", "r"], help="Remove song from queue")
async def remove(ctx: Context, index: int) -> None:
    if not ctx.author.voice or ctx.author.voice.channel not in ctx.guild.voice_channels:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    elif not ctx.voice_client:
        await ctx.send(Response.get("NOT_IN_VOICE", ctx.author.mention))

    elif ctx.author.voice.channel not in [client.channel for client in ctx.bot.voice_clients]:
        await ctx.send(Response.get("USER_NOT_IN_VOICE", ctx.author.mention))

    else:
        removed_song = queues[ctx.voice_client].remove(index - 1)
        
        if(removed_song):
            await ctx.send(Response.get("SONG_REMOVED", removed_song.title))
        
        else:
            await ctx.send(Response.get("BAD_INDEX", ctx.author.mention, index))

    


def play_next(voice_client: VoiceClient) -> None:
    queues[voice_client].next()

    if queues[voice_client].now_playing:      
        voice_client.play(source=queues[voice_client].now_playing.new_source(**FFMPEG_OPTIONS), after=lambda e: play_next(voice_client))


async def download_image(url: str) -> BytesIO:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return BytesIO(await response.read())




bot.run(TOKEN)
