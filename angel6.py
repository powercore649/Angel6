# Builtins
import os
from sys import argv, executable, exit as sysexit

# External modules
import discord
from aioconsole import ainput
from dotenv import load_dotenv
from discord.ext import commands, tasks


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHAN_ID = os.getenv("LOGGING_CHANNEL_ID")
JL_CHAN_ID = os.getenv("JOIN_LEAVE_CHANNEL_ID")
GEN_CHAN_ID = os.getenv("GENERAL_CHANNEL_ID")
BOT_VER = "**2.4.0-Rewrite** <https://github.com/maj113/Angel6/releases/latest>"

intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("~"),
    activity=discord.Game(name="Greatest bot alive"),
    intents=intents,
)


async def set_env_var(
    env_var_name: str, prompt_text: str, force_reset_env: bool = False
):
    """
    Sets an environment variable if it is not already set or if `force_reset_env` is True.

    Parameters:
        - env_var_name (str): The name of the environment variable.
        - prompt_text (str): The text displayed when the environment variable needs to be set.
        - force_reset_env (bool): If True, reset variables even if they are set.

    Returns:
        - bool: True if the environment variable was set or reset, False otherwise.
    """
    value = os.getenv(env_var_name)
    if value is None:
        value = int(input(prompt_text))
        with open(".env", "a", encoding="utf-8") as envfile:
            envfile.write(f"\n{env_var_name}={value}")
        return True
    if value == "" or force_reset_env:
        value = int(input(prompt_text))
        with open(".env", "r+", encoding="utf-8") as envfile:
            content = envfile.read()
            changed = content.replace(f"{env_var_name}=", f"{env_var_name}={value}")
            envfile.seek(0)
            envfile.write(changed)
            envfile.truncate()
        return True
    return False


async def checkenv():
    """
    Checks the environment variables and prompts the user to set them if necessary.

    Returns:
        - bool: True if the environment variables were set or reset, False otherwise.
    """
    config_options = [
        ("LOGGING_CHANNEL_ID", "Input logging channel ID "),
        ("JOIN_LEAVE_CHANNEL_ID", "Input join/leave channel ID "),
        ("GENERAL_CHANNEL_ID", "Input general channel ID "),
    ]
    restart_bot = False
    for env_var_name, prompt_text in config_options:
        restart_bot = await set_env_var(env_var_name, prompt_text, argv[-1] == "reset")
    # We reload the environment variables so the entries are updated
    load_dotenv()
    return restart_bot


@bot.event
async def on_ready():
    """
    Executes when the bot is ready and connected to the Discord server.
    Performs setup tasks and sends a bot status message to the logging channel.
    """
    print(f"Logged in as:\n{bot.user.name}\n{bot.user.id}")

    if await checkenv():
        print("Setup complete, Rebooting")
        os.execv(executable, ["python3"] + argv)

    embed = discord.Embed(
        title="Bot Settings",
        description="Current bot settings and status",
        color=discord.Color.blurple(),
    )

    # Add information about the bot version
    embed.add_field(name="Bot Version:", value="Angel$IX " + BOT_VER, inline=False)

    # Add information about the logging channel
    log_channel = bot.get_channel(int(LOG_CHAN_ID))
    embed.add_field(
        name=f"Logging Channel: {log_channel.mention}", value="", inline=False
    )

    # Add information about the join/leave channel
    jl_channel = bot.get_channel(int(JL_CHAN_ID))
    embed.add_field(
        name=f"Join/Leave Channel: {jl_channel.mention}", value="", inline=False
    )

    # Add information about the general channel
    gen_channel = bot.get_channel(int(GEN_CHAN_ID))
    embed.add_field(
        name=f"General Channel: {gen_channel.mention}", value="", inline=False
    )

    # Add information about the API latency
    api_latency = f"{(bot.latency * 1000):.0f}ms"
    embed.add_field(name=f"API Latency: {api_latency}", value="", inline=False)

    # Get the member object for the bot creator in the guild and add it to the embed
    guild = bot.guilds[0]
    bot_member = guild.get_member(347387857574428676)
    footer_text = f"Bot made by {bot_member.name}"
    embed.set_footer(text=footer_text)

    # Send the message to the logging channel
    await log_channel.send(embed=embed)
    # await log_channel.send(CREDITS_IMAGE) URL dead
    if not asbotmain.is_running():
        await asbotmain.start()


# NextCord doesn't support recursive
bot.load_extension("cogs", recursive=True)


@bot.event
async def on_message(message):
    """
    Event handler for incoming messages.

    Prints the message content, including attachments if present.
    Then, processes the message for bot commands.

    Parameters:
    - message: The received message object.
    """
    if message.author.id != bot.user.id:
        if message.attachments:
            attachments = "\n".join(a.url for a in message.attachments)
            msgcontent = (
                f"{message.guild}/{message.channel}/{message.author.name}> "
                f"{message.content}\n{attachments}"
            )
        else:
            msgcontent = (
                f"{message.guild}/{message.channel}/{message.author.name}> "
                f"{message.content}"
            )
        print(msgcontent)
        await bot.process_commands(message)


def clsscr():
    """
    Clears the console screen using an escape sequence.
    """
    print("\033[H\033[J", end="", flush=True)


async def helperasbot():
    """
    Prints the names and IDs of text channels in the first guild.

    Retrieves the first guild from the bot instance.
    For each text channel, prints the channel name and its corresponding ID.
    """
    server = bot.guilds[0]
    text_channels = server.text_channels
    for channel in text_channels:
        print(f"    {channel.name} : {channel.id}")


@bot.command(pass_context=True)
@commands.has_permissions(ban_members=True)
async def asbot(ctx, *, arg=None):
    """start or stop the asbot function"""
    if arg not in ("start", "stop", None):
        await ctx.reply("Invalid argument. Use `start` or `stop`.")
    elif arg == "stop" and asbotmain.is_running():
        await ctx.reply("Stopped task **`asbotmain()`** successfully")
        clsscr()
        print(f"Warning: asbotmain() was stopped externally by {ctx.author} !!!")
        asbotmain.cancel()
    elif arg == "start" and not asbotmain.is_running():
        await ctx.reply("Started task **`asbotmain()`** successfully")
        print(f"Warning: asbotmain() was started externally by {ctx.author} !!!")
        asbotmain.start()
    elif not arg:
        await ctx.reply(
            embed=discord.Embed(
                title="`asbotmain()` state:"
                + f"{'**running**' if asbotmain.is_running() else '**stopped**'}",
                color=discord.Color.blurple(),
            )
        )
    else:
        await ctx.reply(
            embed=discord.Embed(
                title=f"⚠️ Warning! Cannot {arg} the asbot extension",
                description=(
                    "The extension is already"
                    f" {'**running**' if asbotmain.is_running() else '**stopped**'}"
                ),
                color=discord.Color.yellow(),
            )
        )


@tasks.loop()
async def asbotmain():
    """Send messages as a bot in a specified text channel.

    Usage:
        - Input the channel ID to start sending messages.
        - Type "show" to select a different channel.
        - Type "asbotstop" to stop sending messages.

    Prints error messages if the input is invalid or the channel is a voice channel.
    """

    chan_id_alt = await ainput("\nInput channel ID: ")
    if chan_id_alt == "show":
        clsscr()
        await helperasbot()
        return
    clsscr()
    try:
        channel1 = bot.get_channel(int(chan_id_alt))
    except ValueError:
        print("Error; Wrong ID provided or an unexpected exception occurred, try again")
        return
    if not isinstance(channel1, discord.TextChannel):
        print("Selected channel does not exist or isn't a text channel")
        return

    while True:
        message = await ainput(f"[{str(channel1).strip()}] Message: ")
        if message == "show":
            clsscr()
            await helperasbot()
            break
        if message == "asbotstop":
            asbotmain.cancel()
            clsscr()
            print("Stopped task")
            break
        try:
            await channel1.send(message)
        except discord.errors.HTTPException:
            # This is a Unicode "U+2800/Braille Pattern Blank" character
            await channel1.send("⠀")


try:
    bot.run(TOKEN)
except discord.errors.LoginFailure:
    print(
        "NO TOKEN FOUND OR WRONG TOKEN SPECIFIED,\nmake sure that the env file is"
        " named '.env' and that there is a token present"
    )
    sysexit(1)
except TypeError:
    print("Malformed Token!!!\nPlease check the DISCORD_TOKEN environment variable")
    sysexit(1)