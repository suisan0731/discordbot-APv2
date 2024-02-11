import discord
import asyncio
import yt_dlp
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)
discord.opus.load_opus('libopus/lib/libopus.so')

TOKEN = os.environ['TOKEN']

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': './audio/%(extractor)s-%(id)s-%(title)s.%(ext)s',

    #ファイルの名前に$や空白文字を含めない
    'restrictfilenames': True,

    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,

    #出力系のオプション
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,

    #URL検索が有効でない場合の検索方法
    'default_search': 'ytsearch',

    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn',
}


class AudioQueue(asyncio.Queue):

    def __init__(self):
        super().__init__(100)
        self.playing_now = None

    def __getitem__(self, idx):
        return self._queue[idx]

    def reset(self):
        self._queue.clear()


class AudioStatus:

    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        self.mode = 'single'
        self.loop = 0
        self.now_title = None
        self.now_filename = None
        self.queue = AudioQueue()
        self.playing = asyncio.Event()
        asyncio.create_task(self.playing_task())

    async def add_audio(self, url):
        if not self.ctx.interaction.response.is_done():
            await self.ctx.interaction.response.defer()

        #urlかkeywordの検索に対応した処理
        with yt_dlp.YoutubeDL(ytdl_format_options) as ydl:
            res = ydl.extract_info(url)
            try:
                title = res['entries'][0]['title']
                filename = ydl.prepare_filename(res['entries'][0])
            except KeyError:
                title = res['title']
                filename = ydl.prepare_filename(res)

        if self.mode == 'list':
            if not self.ctx.interaction.response.is_done():
                await self.ctx.interaction.followup.send(f'```{title} を再生リストに追加しました```')
            else:
                await self.ctx.send(f'```{title} を再生リストに追加しました```')
        elif self.ctx.guild.voice_client.is_playing():
            self.ctx.guild.voice_client.stop()
        await self.queue.put([filename, title])

    async def playing_task(self):
        while True:
            self.playing.clear()
            try:
                filename, title = await asyncio.wait_for(self.queue.get(), timeout=300)
            except asyncio.TimeoutError:
                asyncio.create_task(self.leave())
            self.now_title = title
            self.now_filename = filename
            src = discord.FFmpegPCMAudio(self.now_filename, **ffmpeg_options, executable="ffmpeg-6.1-amd64-static/ffmpeg")
            src_adj = discord.PCMVolumeTransformer(src, volume=0.1)
            self.ctx.guild.voice_client.play(src_adj, after=self.play_next)
            if not self.ctx.interaction.response.is_done():
                await self.ctx.interaction.followup.send(f'```{self.now_title} を再生します```')
            else:
                await self.ctx.send(f'```{self.now_title} を再生します```')
            await self.playing.wait()
            if self.loop == 1:
                await self.queue.put([self.now_filename, self.now_title])
    
    def play_next(self, err=None):
        self.playing.set()

    async def leave(self):
        self.queue.reset()
        if self.ctx.guild.voice_client:
            await self.ctx.guild.voice_client.disconnect()

    async def stop(self):
        self.queue.reset()
        self.loop = 0
        self.ctx.guild.voice_client.stop()


audio_status = dict()
  
async def check_connect_channel(ctx: commands.Context, playing_check: bool, interaction: discord.Interaction=None):
    if interaction is None:
        if ctx.author.voice is None:
            await ctx.interaction.response.send_message('```あなたはボイスチャンネルに接続していません```')
            return 1
        elif ctx.guild.voice_client is None:
            await ctx.interaction.response.send_message('```Botがボイスチャンネルに接続していません```')
            return 1
        elif ctx.guild.voice_client.channel != ctx.author.voice.channel:
            await ctx.interaction.response.send_message('```Botと同じボイスチャンネルに接続する必要があります```')
            return 1
        if playing_check:
            if not ctx.guild.voice_client.is_playing():
                await ctx.interaction.response.send_message('```音楽を再生していません```')
                return 1
    else:
        if interaction.user.voice is None:
            await interaction.response.send_message('```あなたはボイスチャンネルに接続していません```')
            return 1
        elif interaction.guild.voice_client is None:
            await interaction.response.send_message('```Botがボイスチャンネルに接続していません```')
            return 1
        elif interaction.guild.voice_client.channel != interaction.user.voice.channel:
            await interaction.response.send_message('```Botと同じボイスチャンネルに接続する必要があります```')
            return 1
        if playing_check:
            if not interaction.guild.voice_client.is_playing():
                await interaction.response.send_message('```音楽を再生していません```')
                return 1
    return 0

@bot.hybrid_command(name='join', description='コマンドを打ったユーザが参加しているボイスチャンネルに参加する。')
async def join(ctx: commands.Context):
    if ctx.author.voice is None:
        await ctx.interaction.response.send_message("```あなたはボイスチャンネルに接続していません```")
        return
    elif ctx.guild.voice_client is not None and ctx.guild.voice_client.channel == ctx.author.voice.channel:
        await ctx.interaction.response.send_message(f'```すでに {ctx.author.voice.channel.name} チャンネルに参加しています```')
        return
    elif ctx.guild.voice_client is not None and ctx.guild.voice_client.channel != ctx.author.voice.channel:
        await ctx.guild.voice_client.disconnect()
    await ctx.author.voice.channel.connect()
    await ctx.interaction.response.send_message(f'```{ctx.author.voice.channel.name} チャンネルに接続しました```')
    audio_status[ctx.guild.id] = AudioStatus(ctx)

@bot.hybrid_command(name='leave', description='ボイスチャンネルから退出する。')
async def leave(ctx: commands.Context):
    status = audio_status.get(ctx.guild.id)
    if await check_connect_channel(ctx, False):
        return
    await status.leave()
    await ctx.interaction.response.send_message(f'```{ctx.author.voice.channel.name} チャンネルを退出しました```')
    del audio_status[ctx.guild.id]

@bot.hybrid_command(name='mode', description='再生リストモードかシングルモードかを指定する。初期値はsingle。')
@discord.app_commands.choices(
    mode = [
        discord.app_commands.Choice(name="single",value="single"),
        discord.app_commands.Choice(name="list",value="list"),
    ]
)
async def mode(ctx: commands.Context, mode: str='single'):
    status = audio_status.get(ctx.guild.id)
    if await check_connect_channel(ctx, False):
      return
    elif status.mode == mode:
      await ctx.interaction.response.send_message(f'```すでに{status.mode} モードです```')
    elif mode in ['single', 'list']:
      status.mode = mode
      if ctx.guild.voice_client.is_playing:
        await status.stop()
      await ctx.interaction.response.send_message(f'```{status.mode} モードに切り替えました```')
    else:
      await ctx.interaction.response.send_message('```コマンドが不正です```')


@bot.hybrid_command(name='play', description='YouTubeの音楽を再生する。URLかキーワードで指定。singleモード: 今の曲を停止し指定した曲を再生。listモード: 再生リストに追加。')
async def play(ctx: commands.Context, url_or_keyword: str):
    status = audio_status.get(ctx.guild.id)
    if status is None or ctx.guild.voice_client.channel != ctx.author.voice.channel:
        await ctx.invoke(join)
        status = audio_status.get(ctx.guild.id)
    status.ctx = ctx
    await status.add_audio(url_or_keyword)

@bot.hybrid_command(name='pause', description='音楽を一時中断する。/resumeで再開可能。')
async def pause(ctx: commands.Context):
    if await check_connect_channel(ctx, True):
      return
    ctx.guild.voice_client.pause()
    status = audio_status.get(ctx.guild.id)
    await ctx.interaction.response.send_message(f'``` {status.now_title} の再生を中止しました /resumeで再開可能です```')

@bot.hybrid_command(name='resume', description='/pauseした音楽を再開する。')
async def resume(ctx: commands.Context):
    if await check_connect_channel(ctx, False):
        return
    elif not ctx.guild.voice_client.is_paused():
        await ctx.interaction.response.send_message("```再生を一時中断していません```")
        return
    ctx.guild.voice_client.resume()
    status = audio_status.get(ctx.guild.id)
    await ctx.interaction.response.send_message(f"```{status.now_title} の再生を再開しました```")

@bot.hybrid_command(name='stop', description='音楽を停止する。再開はできない。')
async def stop(ctx: commands.Context):
    if await check_connect_channel(ctx, True):
        return
    status = audio_status.get(ctx.guild.id)
    await status.stop()
    await ctx.interaction.response.send_message("```再生を中止しました```")

@bot.hybrid_command(name='next', description='listモードの場合、今の曲をスキップし、再生リスト中の次の曲を再生する。')
async def next(ctx: commands.Context):
    if await check_connect_channel(ctx, True):
      return
    status = audio_status.get(ctx.guild.id)
    if status.mode == 'single':
      await ctx.interaction.response.send_message("```シングルモードです```")
      return
    ctx.guild.voice_client.stop()

@bot.hybrid_command(name='loop', description='ループ再生する。singleモード: 1曲をループ。listモード: 再生リストをループ。')
async def loop(ctx: commands.Context):
    if await check_connect_channel(ctx, False):
      return
    status = audio_status.get(ctx.guild.id)
    if status.loop:
      if status.mode == 'single':
        await ctx.interaction.response.send_message(f'```すでに{status.now_title} をループ再生しています```')
      else:
        await ctx.interaction.response.send_message('```すでに再生リストをループ再生しています```')
      return
    status.loop = 1
    if status.mode == 'single':
      await ctx.interaction.response.send_message(f'```{status.now_title} をループ再生します```')
    else:
      await ctx.interaction.response.send_message('```再生リストをループ再生します```')

@bot.hybrid_command(name='unloop', description='ループを停止する。')
async def unloop(ctx: commands.Context):
    if await check_connect_channel(ctx, False):
      return 
    status = audio_status.get(ctx.guild.id)
    if not status.loop:
      await ctx.interaction.response.send_message('```ループ再生していません```')
      return
    status.loop = 0
    await ctx.interaction.response.send_message('```ループ解除します```')

@bot.event
async def setup_hook():
   await bot.tree.sync()
   if os.path.exists("./audio/*"):
       os.remove("./audio/*")

bot.run(TOKEN)