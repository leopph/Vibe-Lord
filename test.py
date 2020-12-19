import os
import dotenv
import tidalapi
from discord.ext.commands import Bot
from discord.ext.commands import Context
from discord.ext.commands import check
from discord.ext.commands import CommandError
from discord.ext.commands import CheckFailure


dotenv.load_dotenv()
tidal_session = tidalapi.Session()
tidal_session.login(os.getenv("TIDAL_UNAME"), os.getenv("TIDAL_PWD"))


bot = Bot(command_prefix=".")


def is_in_voice(ctx: Context) -> bool:
    return ctx.message.author in [member for channel in ctx.guild.voice_channels for member in channel.members]


@bot.event
async def on_command_error(ctx: Context, error: CommandError):
    print(error)


@bot.command()
@check(is_in_voice)
async def connect(ctx: Context) -> None:
    await ctx.message.author.voice.channel.connect()


@bot.command()
async def img(ctx: Context, *, search_str: str) -> None:
    print(type(tidal_session.search("track", search_str, limit=1).tracks[0].album.image))


@bot.command()
@check(is_in_voice)
async def disconnect(ctx: Context) -> None:
    for client in bot.voice_clients:
        if client.channel == ctx.message.author.voice.channel:
            await client.disconnect()
            return


bot.run(os.getenv("DISCORD_TOKEN"))