import discord
from discord.ext import commands


class MyView(discord.ui.View):
    def __init__(self, ctx, lst):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.lst = lst
        for button in self.lst:
            self.add_item(button)
    
    async def button_change(self):
        self.clear_items()
        for button in self.lst:
            self.add_item(button)
        await self.ctx.interaction.edit_original_response(view=self)


class MyLoopButton(discord.ui.Button):
    def __init__(self):
        status = audio_status.get(self.view.ctx.guild.id)
        if status is None:
            button_style = discord.ButtonStyle.primary
            button_label = 'loop'
        elif status.loop == 0:
            button_style = discord.ButtonStyle.primary
            button_label = 'loop'
        else:
            button_style = discord.ButtonStyle.danger
            button_label = 'unloop'
        super().__init__(
            style=button_style,
            label=button_label,
        ) 

    async def callback(self, interaction: discord.Interaction):
        if await check_connect_channel(ctx=None, playing_check=False, interaction=interaction):
            return
        status = audio_status.get(interaction.guild.id)
        if self.label == 'loop':
            if status.loop:
                if status.mode == 'single':
                    await interaction.response.send_message(f'```すでに{status.now_title} をループ再生しています```', delete_after=10)
                else:
                    await interaction.response.send_message('```すでに再生リストをループ再生しています```', delete_after=10)
                return
            status.loop = 1
            if status.mode == 'single':
                await interaction.response.send_message(f'```{status.now_title} をループ再生します```', delete_after=10)
            else:
                await interaction.response.send_message('```再生リストをループ再生します```', delete_after=10)
            self.label = 'unloop'
            self.style = discord.ButtonStyle.danger
        else:
            if not status.loop:
                await interaction.response.send_message('```ループ再生していません```', delete_after=10)
                return
            status.loop = 0
            await interaction.response.send_message('```ループ解除します```', delete_after=10)
            self.label = 'loop'
            self.style = discord.ButtonStyle.primary
        await self.view.button_change()


class MyPauseButton(discord.ui.Button):
    def __init__(self):
        if self.view.ctx.guild.voice_client is None:
            button_style = discord.ButtonStyle.primary
            button_label = 'pause'
        elif self.view.ctx.guild.voice_client.is_paused():
            button_style = discord.ButtonStyle.danger
            button_label = 'resume'
        else:
            button_style = discord.ButtonStyle.primary
            button_label = 'pause'
        super().__init__(
            style=button_style,
            label=button_label,
        ) 
    
    async def callback(self, interaction: discord.Interaction):
        if self.label == 'pause':
            if await check_connect_channel(ctx=None, playing_check=True, interaction=interaction):
                return
            interaction.guild.voice_client.pause()
            status = audio_status.get(interaction.guild.id)
            await interaction.response.send_message(f"```{status.now_title} の再生を中止しました $resumeで再開可能です```", delete_after=10)
            self.label = 'resume'
            self.style = discord.ButtonStyle.danger
        else:
            if await check_connect_channel(ctx=None, playing_check=False, interaction=interaction):
                return
            elif not interaction.guild.voice_client.is_paused():
                await interaction.response.send_message("```再生を一時中断していません```", delete_after=10)
                return
            interaction.guild.voice_client.resume()
            status = audio_status.get(interaction.guild.id)
            await interaction.response.send_message(f"```{status.now_title} の再生を再開しました```")
            self.style = discord.ButtonStyle.primary
            self.label = 'pause'
        await self.view.button_change()


@bot.hybrid_command(name='controller', description='コントローラーを表示する')
async def controller(ctx: commands.Context):
    my_view = MyView(None, [MyLoopButton(), MyPauseButton()])
    my_view.ctx = ctx
    await ctx.interaction.response.send_message(view=my_view)