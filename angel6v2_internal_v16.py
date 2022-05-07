from base64 import decode
from encodings import utf_8
import logging
import asyncio
import functools
import psutil
import itertools
import math
import time
import datetime
import random
from subprocess import run
import sys
import discord
from discord import __version__ as d_version
from discord.ext import commands
import cpuinfo
import youtube_dl
from async_timeout import timeout
import os
import re
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Silence useless bug reports messages
youtube_dl.utils.bug_reports_message = lambda: ''

logging.basicConfig(level=logging.ERROR)

class VoiceError(Exception):
    pass

class YTDLError(Exception):
    pass

class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio',
        'extractaudio': True,
        'audioformat': 'aac',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'source_address': '0.0.0.0',
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx: commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 1):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.stream_url = data.get('url')

    def __str__(self):
        return '**{0.title}** by **{0.uploader}**'.format(self)

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))
        
        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    @classmethod
    async def search_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        channel = ctx.channel
        loop = loop or asyncio.get_event_loop()

        cls.search_query = '%s%s:%s' % ('ytsearch', 10, ''.join(search))

        partial = functools.partial(cls.ytdl.extract_info, cls.search_query, download=False, process=False)
        info = await loop.run_in_executor(None, partial)

        cls.search = {}
        cls.search["title"] = f'Search results for:\n**{search}**'
        cls.search["type"] = 'rich'
        cls.search["color"] = 7506394
        cls.search["author"] = {'name': f'{ctx.author.name}', 'url': f'{ctx.author.avatar_url}', 'icon.url': f'{ctx.author.avatar_url}'}
        
        lst = []

        for e in info['entries']:
        #!!!TEST!!! ˇ LINE BELOW WAS COMMENTED OUT
            lst.append(f'`{info["entries"].index(e) + 1}.` {e.get("title")} **[{YTDLSource.parse_duration(int(e.get("duration")))}]**\n')
            VId = e.get('id')
            VUrl = 'https://www.youtube.com/watch?v=%s' % (VId)
            lst.append(f'`{info["entries"].index(e) + 1}.` [{e.get("title")}]({VUrl})\n')

        lst.append('\n**Type a number to make a choice, Type `cancel` to exit**')
        cls.search["description"] = "\n".join(lst)

        em = discord.Embed.from_dict(cls.search)
        await ctx.send(embed=em, delete_after=45.0)

        def check(msg):
            return msg.content.isdigit() == True and msg.channel == channel or msg.content == 'cancel' or msg.content == 'Cancel'
        
        try:
            m = await bot.wait_for('message', check=check, timeout=45.0)

        except asyncio.TimeoutError:
            rtrn = 'timeout'

        else:
            if m.content.isdigit() == True:
                sel = int(m.content)
                if 0 < sel <= 10:
                    for key, value in info.items():
                        if key == 'entries':
                            """data = value[sel - 1]"""
                            VId = value[sel - 1]['id']
                            VUrl = 'https://www.youtube.com/watch?v=%s' % (VId)
                            partial = functools.partial(cls.ytdl.extract_info, VUrl, download=False)
                            data = await loop.run_in_executor(None, partial)
                    rtrn = cls(ctx, discord.FFmpegPCMAudio(data['url'], **cls.FFMPEG_OPTIONS), data=data)
                else:
                    rtrn = 'sel_invalid'
            elif m.content == 'cancel':
                rtrn = 'cancel'
            else:
                rtrn = 'sel_invalid'
        
        return rtrn

    @staticmethod
    def parse_duration(duration: int):
        if duration > 0:
            minutes, seconds = divmod(duration, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)

            duration = []
            if days > 0:
                duration.append('{}'.format(days))
            if hours > 0:
                duration.append('{}'.format(hours))
            if minutes > 0:
                duration.append('{}'.format(minutes))
            if seconds > 0:
                duration.append('{}'.format(seconds))
            
            value = ':'.join(duration)
        
        elif duration == 0:
            value = "LIVE"
        
        return value

class Song:
    __slots__ = ('source', 'requester')

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester
    
    def create_embed(self):
        embed = (discord.Embed(title='Now playing', description='```css\n{0.source.title}\n```'.format(self), color=discord.Color.blurple())
                .add_field(name='Duration', value=self.source.duration)
                .add_field(name='Requested by', value=self.requester.mention)
                .add_field(name='Uploader', value='[{0.source.uploader}]({0.source.uploader_url})'.format(self))
                .add_field(name='URL', value='[Click]({0.source.url})'.format(self))
                .set_thumbnail(url=self.source.thumbnail)
                .set_author(name=self.requester.name, icon_url=self.requester.avatar.url))
        return embed

class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]

class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()
        self.exists = True

        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()
            self.now = None

            if self.loop == False:
                # Try to get the next song within 3 minutes.
                # If no song will be added to the queue in time,
                # the player will disconnect due to performance
                # reasons.
                try:
                    async with timeout(180):  # 3 minutes
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    self.exists = False
                    return
                
                self.current.source.volume = self._volume
                self.voice.play(self.current.source, after=self.play_next_song)
                await self.current.source.channel.send(embed=self.current.create_embed())
            
            #If the song is looped
            elif self.loop == True:
                self.now = discord.FFmpegPCMAudio(self.current.source.stream_url, **YTDLSource.FFMPEG_OPTIONS)
                self.voice.play(self.now, after=self.play_next_song)
            
            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state or not state.exists:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command can\'t be used in DM channels.')

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send('An error occurred: {}'.format(str(error)))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != bot.user.id:
            print(f"{message.guild}/{message.channel}/{message.author.name}>{message.content}")
            if message.embeds:
                print(message.embeds[0].to_dict())

    @commands.command(name='join', invoke_without_subcommand=True)
    async def _join(self, ctx: commands.Context):
        """Joins a voice channel."""

        destination = ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='summon')
    @commands.has_permissions(manage_guild=True)
    async def _summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):
        """Summons the bot to a voice channel.
        If no channel was specified, it joins your channel.
        """

        if not channel and not ctx.author.voice:
            raise VoiceError('You are neither connected to a voice channel nor specified a channel to join.')

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='leave', aliases=['disconnect'])
    @commands.has_permissions(manage_guild=True)
    async def _leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""

        if not ctx.voice_state.voice:
            return await ctx.send('Not connected to any voice channel.')

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]

    @commands.command(name='volume')
    @commands.is_owner()
    async def _volume(self, ctx: commands.Context, *, volume: int):
        """Sets the volume of the player."""

        if not ctx.voice_state.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        if 0 > volume > 100:
            return await ctx.send('Volume must be between 0 and 100')

        ctx.voice_state.volume = volume / 100
        await ctx.send('Volume of the player set to {}%'.format(volume))

    @commands.command(name='now', aliases=['current', 'playing'])
    async def _now(self, ctx: commands.Context):
        """Displays the currently playing song."""
        embed = ctx.voice_state.current.create_embed()
        await ctx.send(embed=embed)

    @commands.command(name='pause', aliases=['pa'])
    @commands.has_permissions(manage_guild=True)
    async def _pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""
        print(">>>Pause Command:")
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='resume', aliases=['re', 'res'])
    @commands.has_permissions(manage_guild=True)
    async def _resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='stop')
    @commands.has_permissions(manage_guild=True)
    async def _stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""

        ctx.voice_state.songs.clear()

        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name='skip', aliases=['s'])
    async def _skip(self, ctx: commands.Context):
        """Vote to skip a song. The requester can automatically skip.
        3 skip votes are needed for the song to be skipped.
        """

        if not ctx.voice_state.is_playing:
            return await ctx.send('Not playing any music right now...')

        voter = ctx.message.author
        if voter == ctx.voice_state.current.requester:
            await ctx.message.add_reaction('⏭')
            ctx.voice_state.skip()

        elif voter.id not in ctx.voice_state.skip_votes:
            ctx.voice_state.skip_votes.add(voter.id)
            total_votes = len(ctx.voice_state.skip_votes)

            if total_votes >= 3:
                await ctx.message.add_reaction('⏭')
                ctx.voice_state.skip()
            else:
                await ctx.send('Skip vote added, currently at **{}/3**'.format(total_votes))

        else:
            await ctx.send('You have already voted to skip this song.')

    @commands.command(name='queue')
    async def _queue(self, ctx: commands.Context, *, page: int = 1):

        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1,song)

        embed = (discord.Embed(description='**{} tracks:**\n\n{}'.format(len(ctx.voice_state.songs), queue))
                 .set_footer(text='Viewing page {}/{}'.format(page, pages)))
        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    async def _shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name='remove')
    async def _remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='loop')
    async def _loop(self, ctx: commands.Context):
        """Loops the currently playing song.
        Invoke this command again to unloop the song.
        """

        if not ctx.voice_state.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        # Inverse boolean value to loop and unloop.
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.message.add_reaction('✅')

    @commands.command(name='play', aliases=['p'])
    async def _play(self, ctx: commands.Context, *, search: str):
        """Plays a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        """

        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
            else:
                if not ctx.voice_state.voice:
                    await ctx.invoke(self._join)

                song = Song(source)
                await ctx.voice_state.songs.put(song)
                await ctx.send('Enqueued {}'.format(str(source)))

    
    async def _search(self, ctx: commands.Context, *, search: str):
        """Searches youtube.
        It returns an imbed of the first 10 results collected from youtube.
        Then the user can choose one of the titles by typing a number
        in chat or they can cancel by typing "cancel" in chat.
        Each title in the list can be clicked as a link.
        """
        async with ctx.typing():
            try:
                source = await YTDLSource.search_source(ctx, search, loop=self.bot.loop, bot=self.bot)
            except YTDLError as e:
                await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
            else:
                if source == 'sel_invalid':
                    await ctx.send('Invalid selection')
                elif source == 'cancel':
                    await ctx.send(':white_check_mark:')
                elif source == 'timeout':
                    await ctx.send(':alarm_clock: **Time\'s up bud**')
                else:
                    if not ctx.voice_state.voice:
                        await ctx.invoke(self._join)

                    song = Song(source)
                    await ctx.voice_state.songs.put(song)
                    await ctx.send('Enqueued {}'.format(str(source)))
            
    @_join.before_invoke
    @_play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('Bot is already in a voice channel.')

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='~', intents=intents)
status = ['Jamming out to music!', 'Eating!', 'Sleeping!']
bot.add_cog(Music(bot))
   
def restart_program():
    python = sys.executable
    os.execl(python, python, * sys.argv)

@bot.command()
@commands.has_permissions(kick_members=True)
async def restart(ctx):
    """restarts the bot"""
    await ctx.message.delete()
    message = await ctx.send(" Restarting, please allow 5 seconds for this. ")
    restart_program()

@bot.command()
async def ping(ctx):
    """shows the ping"""
    await ctx.send(f'Here {(bot.latency * 1000)} ms')

@bot.event
async def on_ready():
    print('Logged in as:\n{0.user.name}\n{0.user.id}'.format(bot))
    await bot.change_presence(activity=discord.Game(name="Mutinys Official Bot"))
    channel = bot.get_channel(965773534876012564)
    #specifies Ascii art location for bootup message
    file = open(r"Ascii1.txt", "rt")
    content = file.read()
    file.close()
    await channel.send(content)

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(965773521206779955)
    embed = discord.Embed(colour=16777, description=f"{member.mention} joined, Total Members: {len(list(member.guild.members))}")
    embed.set_thumbnail(url=f"{member.avatar.url}")
    embed.set_footer(text=f"{member.guild}", icon_url=f"{member.guild.icon.url}")
    await channel.send(embed=embed)
    mbed = discord.Embed(
        colour = (discord.Colour.blurple()),
        title = 'Glad you could find us!',
        description =f"yo! im Mutinys Personal Bot, proceed to <#965773524516106310> to talk:)")
    await member.send(embed=mbed)

@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(965773521206779955)
    embed = discord.Embed(colour=16777, description=f"{member.mention} Left us, Total Members: {len(list(member.guild.members))}")
    embed.set_thumbnail(url=f"{member.avatar.url}")
    embed.set_footer(text=f"{member.guild}", icon_url=f"{member.guild.icon.url}")
    await channel.send(embed=embed)


@bot.command()
async def users(ctx,):
    """shows total amount of members"""
    guild = ctx.guild
    members = 0
    for member in guild.members:
        members+=1
    a=ctx.guild.member_count
    b=discord.Embed(title=f"Total members in {ctx.guild.name}",description=a,color=discord.Color((0xffff00)))
    await ctx.send(embed=b)

@bot.command()
async def av(ctx, *,  avamember : discord.Member=None):
    """grabs users avatar"""
    if avamember is None:
        avamember = ctx.author
        userAvatarUrl = avamember.avatar.url
        await ctx.send(userAvatarUrl)
        await ctx.send("^^")
    else:
        userAvatarUrl = avamember.avatar.url
        await ctx.send(userAvatarUrl)
        await ctx.send("^^")

@bot.command(description="Gets info about the user")
async def userinfo(ctx, *, user : discord.Member=None): # b'\xfc'
    if user is None:
        user = ctx.author      
    date_format = "%a, %d %b %Y %I:%M %p"
    embed = discord.Embed(color=0xdfa3ff, description=user.mention)
    embed.set_author(name=str(user), icon_url=user.avatar.url)
    embed.set_thumbnail(url=user.avatar.url)
    embed.add_field(name="Joined", value=user.joined_at.strftime(date_format))
    members = sorted(ctx.guild.members, key=lambda m: m.joined_at)
    embed.add_field(name="Join position", value=str(members.index(user)+1))
    embed.add_field(name="Registered", value=user.created_at.strftime(date_format))
    embed.add_field(name="ID", value=user.id, inline=True)
    if len(user.roles) > 1:
        role_string = ' '.join([r.mention for r in user.roles][1:])
        embed.add_field(name="Roles [{}]".format(len(user.roles)-1), value=role_string, inline=False)
    perm_string = ', '.join([str(p[0]).replace("_", " ").title() for p in user.guild_permissions if p[1]])
    embed.add_field(name="Guild permissions", value=perm_string, inline=False)
    return await ctx.send(embed=embed)

@bot.command(description="sends our invite or gateways invite lol")
async def serverinfo(ctx):
    """displays server information"""
    name = str(ctx.guild.name)
    description = "Official Mutiny server"
    launch = "7/7/21"
    owner = str(ctx.guild.owner)
    id = str(ctx.guild.id)
    region = str(ctx.guild.region)
    memberCount = str(ctx.guild.member_count)

    icon = str(ctx.guild.icon.url)
    invite ="none"
    embed = discord.Embed(
        title=name + "<3",
        description=description,
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=icon)
    embed.add_field(name="Owner", value=owner, inline=True)
    embed.add_field(name="Server ID", value=id, inline=True)
    embed.add_field(name="Region", value=region, inline=True)
    embed.add_field(name="Member Count", value=memberCount, inline=True)
    embed.add_field(name="Invite",value=invite, inline=True)
    embed.add_field(name="Launch Date", value=launch, inline=True)
    await ctx.send(embed=embed)

@bot.command(description="Mutes the specified user.")
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member: discord.Member, *, reason=None):
    """mutes a user"""
    embed=discord.Embed(title="Muted", description=f"{member.mention} was muted for {reason}")
    guild = ctx.guild
    mutedRole = discord.utils.get(guild.roles, name="Muted")
    if member.top_role >= ctx.author.top_role:
        await ctx.send(f"Nice try, ayo {member.mention}, {ctx.author.mention} just tried muting you")
        return
    if not mutedRole:
        mutedRole = await guild.create_role(name="Muted")

        for channel in guild.channels:
            await channel.set_permissions(mutedRole, speak=False, send_messages=False, read_message_history=True, read_messages=True)

    await member.add_roles(mutedRole, reason=reason)
    await ctx.send(embed=embed)
    await member.send(f"You were muted for {reason}")

@bot.command()
@commands.has_permissions(kick_members =True)
async def kick(ctx, member : discord.Member, *, reason=None):
    """kicks a user"""
    await member.kick(reason=reason)

    if member.top_role >= ctx.author.top_role:
        await ctx.send(f"Yo, you can only kick members lower than yourself lmao ")
        return
    await member.kick()
    embed = discord.Embed(title="kicked", description=f"{member.mention} was kicked out for {reason}")
    await ctx.channel.send(embed=embed)

start_time = time.time()

@bot.command(pass_context=True)
async def uptime(ctx):
        """shows bot uptime"""
        current_time = time.time()
        difference = int(round(current_time - start_time))
        text = str(datetime.timedelta(seconds=difference))
        embed = discord.Embed(colour=0xc8dc6c)
        embed.add_field(name="Uptime", value=text)
        embed.set_footer(text="Angel$IX")
        try:
            await ctx.send(embed=embed)
        except discord.HTTPException:
            await ctx.send("Current uptime: " + text)

@bot.command()
@commands.has_permissions(kick_members =True)
async def unmute(ctx, member: discord.Member):
    """unmutes a user"""
    mutedRole = discord.utils.get(ctx.guild.roles, name="Muted")

    await member.remove_roles(mutedRole)
    await ctx.send(f"Unmuted {member.mention}")
    await member.send(f'Unmuted in {ctx.guild.name} welcome back')

meminfo = psutil.Process(os.getpid())
totmem = psutil.virtual_memory().total / float(1024 ** 2)  
mem = meminfo.memory_info()[0] / float(2 ** 20) 
ytdlfunc = run("youtube-dl --version", shell=True, capture_output=True).stdout.decode('ascii')

@bot.command() 
async def stats(ctx):
    """shows bot stats"""
    bedem = discord.Embed(title = 'System Resource Usage', description = 'See bot host statistics.')
    bedem.add_field(name = "Angel$IX version", value = "**v16**", inline = False)
    bedem.add_field(name = 'CPU Usage', value = f'{psutil.cpu_percent()}%', inline = False)
    bedem.add_field(name = 'Total Memory', value = f'{totmem:.0f}MB', inline = False)
    bedem.add_field(name = 'Memory Usage', value = f'{mem:.0f}MB', inline = False)
    bedem.add_field(name = 'CPU name', value = cpuinfo.get_cpu_info()['brand_raw'], inline = False)
    bedem.add_field(name = 'Discord.py Version', value = d_version, inline = False)
    bedem.add_field(name = 'Python Version', value = sys.version, inline = False)
    bedem.add_field(name = 'YTdl Version', value = ytdlfunc.strip(), inline = False)
    await ctx.send(embed = bedem)

@bot.command()
@commands.has_permissions(ban_members =True)
async def ban(ctx, member : discord.Member, *, reason=None):
    """bans the specified user"""
    if  member.top_role >= ctx.author.top_role:
        await ctx.send(f"Yo, you can only bean members lower than yourself lmao ")
        return
    else:
        await member.ban(reason=reason)
        await member.ban()
        embed = discord.Embed(title="bye lol", description=f"{member.mention} got banned: {reason} ")
        await ctx.channel.send(embed=embed)

@bot.command()
@commands.has_permissions(ban_members =True)   
async def unban(ctx, id: int) :
    """unbans a user"""
    user = await bot.fetch_user(id)
    await ctx.guild.unban(user)
    await ctx.send(f'{user} has been unbanned')
        
        


@bot.command()
@commands.has_permissions(ban_members =True)
async def wipe(ctx, amount=0):
    """wipes x amount of messages"""
    await ctx.channel.purge(limit=amount)
    await ctx.channel.send(f"Cleanup Complete.")

@bot.command()
#this command does nothing 
async def crisis(ctx):
   """Underground Nuclear Code"""
   embed = discord.Embed(title="Last Resort", description="Failsafe activated. purging.")
   await ctx.channel.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx, member : discord.Member, *, reason=None):
    """warns a user"""
    embed2 =discord.Embed(title="Warned🗡️", description=f"You were warned for {reason}")
    embed =discord.Embed(title="Warned", description=f"{member.mention} was warned for {reason}")
    await ctx.channel.send (embed=embed)
    await member.send(embed=embed2)



@bot.command()
async def invites(ctx, user = None):
    """checks how many inivtes user has sent"""
    if user == None:
        totalInvites = 0
        for i in await ctx.guild.invites():
            if i.inviter == ctx.author:
                totalInvites += i.uses
        await ctx.send(f"You've invited {totalInvites} member{'' if totalInvites == 1 else 's'} to the server!")
    else:
        totalInvites = 0
        for i in await ctx.guild.invites():
            member = ctx.message.guild.get_member_named(user)
            if i.inviter == member:
                totalInvites += i.uses
        await ctx.send(f"{member} has invited {totalInvites} member{'' if totalInvites == 1 else 's'} to the server!")

@bot.command()
async def IQ(ctx):
    """Average IQ of Mutiny"""
    embed=discord.Embed(title="Average Mutiny IQ", description=f"{random.randint(-10, 130 )}")
    await ctx.send(embed=embed)

@bot.command('roll')
async def roll(ctx,*args):
    """Rolls a dice in user specified format"""
    args = "".join(args)
    
    print("args is:" + str(args))
    
    # sanitize input - remove trailing spaces
    args=args.strip()

    args=args.replace(' ', '')

    if args == 'help':
        await ctx.send("`~roll` - rolls a 6 sided dice\n"\
                        "`~roll 4` - rolls a 4 sided dice\n"\
                        "`~roll 2d6` - rolls two 6-sided dice\n"\
                        )
        return
        
    diceToRoll=1
    numberOfSides=6

    if args:
        try:
            (diceToRoll,numberOfSides)=parseInput(args)
        except:
            await ctx.send('I didn''t understand your input: `' + args + '`.\n try `~roll help` for supported options')
            return
    
    await ctx.send('Rolling `' + str(diceToRoll) + '` dice with `' + str(numberOfSides) + '` sides')

    results = []
    
    for _ in range(0, diceToRoll):
        print('rolling a ' + str(numberOfSides) + ' sided dice')
        results.insert(0, '['+str(rolladice(numberOfSides))+']')

    resultString = ',  '.join(results)
    
    await ctx.send('Results: ' + resultString)

def parseInput(input):
    split=input.split('d')

    # remove empty items
    split=[x for x in split if x]

    if len(split) == 1:
        diceToRoll = 1
        sidedDice = int(split[0])
    elif len(split) == 2:
        diceToRoll = int(split[0])
        sidedDice = int(split[1])

    if diceToRoll > 100:
        raise Exception('too many dice')
    
    if sidedDice > 100000000:
        raise Exception('too many sides')

    return diceToRoll, sidedDice

def rolladice(sides):
    return random.randint(1, sides)

@bot.command()
async def credit(ctx):
    """Displays who created and maintained the bot"""
    file = open(r"Ascii1.txt", "rt")
    content = file.read()
    file.close()
    await ctx.send(content)
    embed=discord.Embed(title="Hosted/Made by: ! ! Gregg#8032, Maintained by: MayTheChicken#1623", description="ask them anything! 24/7\n Feel free to add them as a friend")
    await ctx.send(embed=embed)

@bot.command(pass_context=True)
@commands.has_permissions(ban_members=True)
async def role(ctx, user: discord.Member, role: discord.Role):
        """Gives user a role"""
        await user.add_roles(role)
        await ctx.send(f"{user.name} has been given: {role.name}")
        
@bot.command(pass_context=True)
@commands.has_permissions(ban_members=True)
async def rmrole(ctx, user: discord.Member, role: discord.Role):
        """takes  users role away"""
        await user.remove_roles(role)
        await ctx.send(f"{user.name} was removed from role: {role.name}")


bot.run(TOKEN)                                      
