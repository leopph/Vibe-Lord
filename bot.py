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
import random




class Response:
    RESPONSES: dict[str, list[str]] =\
    {
        "BAD_SOURCE":
            [
                "{0}, you fucking moron, there is no \"{1}\" source option!",
                "Dood..., {0}... \"{1}\" is not even a source option!",
                "{0}... this is really cringe... but... ur retarded. \"{1}\" is not a valid source option..."
            ],

        "QUEUE":
            [
                "Alrighty mate, {0} is in queue!",
                "As you wish bruh, {0} coming up!",
                "{0} is a great choice, chief! I'll play it for you ASAP.",
                "Sure thing dude, imma queue {0} for ya!",
                "A big bag of {0} is on the way!",
                "Immeasurable amounts of {0}, on the premises!"
            ],

        "NOT_IN_VOICE":
            [
                "{0}... Come on... I'm not even in voice...",
                "{0}... bruh... Seriously? I AM NOT IN A VOICE CHANNEL! HELLO!",
                "Help! I can't fulfill {0}'s wish, because I'm not in a voice channel!",
                "My dear Lord, another moron! {0}, mate, am I in any voice channel? No! See a problem with that?"
            ],

        "ALREADY_IN_VOICE":
            [
                "{0}... mah man... Have you eyes? I'M ALREADY IN A VOICE CHANNEL!",
                "Mayday, mayday! We have a problem! {0} wants me to join, but I'm already here!",
                "{0}, I regret to inform you that I am unable to fulfill your wish, as I am ALREADY IN THE FUCKING VOICE CHANNEL!",
            ],
        
        "NOT_PLAYING":
            [
                "{0}... bruuuh... I'm not even playing anything!",
                "Okay, {0}. I get it. Really. But since I'm not playing anything, I just can't do that. Sorry.",
                "Right. Look, {0}. We have to talk. I. AM. NOT. PLAYING. A. SINGLE. THING. RIGHT. NOW. OK?"
            ],

        "PAUSE":
            [
                "Alrighty, I paused this shit for ya.",
                "Understandable. Have a nice pause.",
                "Paused.",
                "Pausing!",
                "Ah. The sweetness of temporary silence.",
            ],

        "NOT_PAUSED":
            [
                "{0}, you fucking cringe, I'm not paused!",
                "Alright, {0}. I have something to tell you. I'M NOT PAUSED.",
                "Hey, {0}! Have you ears? I AM NOT PAUSED!",
                "Okay, {0}. Sure. But I currently am not in the state of being paused."
            ],

        "RESUME":
            [
                "Resuming!",
                "Resumed.",
                "Finally! I hate silence!",
                "Well. That's it for silence...",
                "Alright, laddies, buckle up! We're resuming!"
            ],

        "F":
            [
                "{0}, I pay my respects to you.",
                "Pressing F to pay respect to {0}.",
                "What a sad day. Let's pay our respects to {0}!",
                "Respects to {0} I pay."
            ],

        "GOODBYE":
            [
                "Goodbye, fellas!",
                "See you around!",
                "Imma head out now.",
                "I'm leaving you guys. Sorry.",
                "Oh. My mom called. I gotta go home. Cya!",
            ],

        "SKIP":
            [
                "Skipping.",
                "Skipped!",
                "Finally! I hated that!",
                "Yea, I don't like that either.",
                "Oh no! That was my favorite!"
            ]
    }


    @staticmethod
    def get(cat: str) -> str:
        if cat not in Response.RESPONSES:
            raise Exception

        return random.choice(Response.RESPONSES[cat])




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
