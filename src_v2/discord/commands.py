import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger
from typing import cast
from src_v2.memory.manager import memory_manager
from src_v2.core.character import character_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.evolution.trust import trust_manager
from src_v2.config.settings import settings

class CharacterCommands(app_commands.Group):
    def __init__(self):
        # Dynamic name based on the bot (e.g., "elena", "marcus")
        name = settings.DISCORD_BOT_NAME.lower() if settings.DISCORD_BOT_NAME else "bot"
        super().__init__(name=name, description=f"Commands for {name}")

    @app_commands.command(name="memory_wipe", description="Wipe your data (Memory, Facts, Trust, Preferences)")
    @app_commands.describe(scope="What to wipe: 'all' (default), 'memory', 'facts', 'preferences', 'trust'")
    @app_commands.choices(scope=[
        app_commands.Choice(name="All Data", value="all"),
        app_commands.Choice(name="Conversation Memory Only", value="memory"),
        app_commands.Choice(name="Facts Only", value="facts"),
        app_commands.Choice(name="Preferences Only", value="preferences"),
        app_commands.Choice(name="Trust & Relationship", value="trust")
    ])
    async def memory_wipe(self, interaction: discord.Interaction, scope: str = "all"):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id = str(interaction.user.id)
            character_name = settings.DISCORD_BOT_NAME or "default"
            
            messages = []

            # 1. Wipe Memory (Vector + Chat History)
            if scope in ["all", "memory"]:
                await memory_manager.clear_memory(user_id, character_name)
                messages.append("Conversation memory cleared.")

            # 2. Wipe Facts (Knowledge Graph)
            if scope in ["all", "facts"]:
                await knowledge_manager.clear_user_knowledge(user_id)
                messages.append("Personal facts cleared.")

            # 3. Wipe Preferences & Trust (includes relationship level, traits, insights)
            if scope in ["all", "preferences", "trust"]:
                await trust_manager.clear_user_preferences(user_id, character_name)
                messages.append("Trust score, relationship level, preferences, and insights cleared.")
            
            response = f"**Wipe Complete for {character_name}:**\n" + "\n".join([f"✅ {m}" for m in messages])
            await interaction.followup.send(response, ephemeral=True)
        except Exception as e:
            logger.error(f"Error wiping data: {e}")
            await interaction.followup.send("Failed to wipe data.", ephemeral=True)

    @app_commands.command(name="profile", description="Show what the bot knows about you (Facts & Preferences)")
    async def profile(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id = str(interaction.user.id)
            character_name = settings.DISCORD_BOT_NAME or "default"
            
            # 1. Get Facts (Global)
            facts = await knowledge_manager.get_user_knowledge(user_id, limit=20)
            if not facts:
                facts = "No specific facts stored yet."
            else:
                # Format facts nicely
                facts = "\n".join([f"• {f}" for f in facts.split("\n")])

            # 2. Get Preferences & Trust (Character Specific)
            relationship = await trust_manager.get_relationship_level(user_id, character_name)
            prefs = relationship.get("preferences", {})
            trust_score = relationship.get("trust_score", 0)
            level_label = relationship.get("level_label", "Stranger")
            
            prefs_text = "No specific preferences set."
            if prefs:
                prefs_text = "\n".join([f"• **{k}**: {v}" for k, v in prefs.items()])

            # Build Response
            embed = discord.Embed(title=f"User Profile: {interaction.user.display_name}", color=0x00ff00)
            embed.add_field(name="🧠 Global Facts (Shared)", value=facts, inline=False)
            embed.add_field(name=f"🤝 Relationship ({character_name})", value=f"Level: {level_label} (Trust: {trust_score})", inline=False)
            embed.add_field(name="⚙️ Preferences", value=prefs_text, inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
            await interaction.followup.send("Failed to retrieve profile.", ephemeral=True)

    @app_commands.command(name="debug", description="Show debug information")
    async def debug(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            character_name = settings.DISCORD_BOT_NAME or "default"
            char = character_manager.get_character(character_name)
            
            info = f"**Bot Identity:** {character_name}\n"
            if char:
                info += f"**Loaded Character:** {char.name}\n"
            else:
                info += "**Loaded Character:** None (Error)\n"
                
            info += f"**Vision Enabled:** {settings.LLM_SUPPORTS_VISION}\n"
            # Check if voice is configured
            voice_enabled = bool(settings.ELEVENLABS_API_KEY)
            info += f"**Voice Enabled:** {voice_enabled}\n"
            
            await interaction.followup.send(info, ephemeral=True)
        except Exception as e:
            logger.error(f"Error getting debug info: {e}")
            await interaction.followup.send("Failed to get debug info.", ephemeral=True)

    @app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return

        # Cast user to Member to access voice state
        member = cast(discord.Member, interaction.user)
        
        if not member.voice or not member.voice.channel:
            await interaction.followup.send("You are not in a voice channel.", ephemeral=True)
            return
            
        channel = member.voice.channel
        # Ensure channel is a VoiceChannel (not StageChannel for now, unless supported)
        if not isinstance(channel, discord.VoiceChannel):
             await interaction.followup.send("I can only join standard voice channels.", ephemeral=True)
             return

        try:
            # Use VoiceManager
            from src_v2.discord.voice import VoiceManager
            # Cast client to Bot as VoiceManager expects Bot
            bot = cast(commands.Bot, interaction.client)
            vm = VoiceManager(bot)
            await vm.join_channel(channel)
            await interaction.followup.send(f"Joined {channel.name}!", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to join voice: {e}")
            await interaction.followup.send("Failed to join voice channel.", ephemeral=True)

    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return

        if not interaction.guild.voice_client:
            await interaction.followup.send("I am not in a voice channel.", ephemeral=True)
            return
            
        try:
            from src_v2.discord.voice import VoiceManager
            # Cast client to Bot
            bot = cast(commands.Bot, interaction.client)
            vm = VoiceManager(bot)
            await vm.leave_channel(interaction.guild)
            await interaction.followup.send("Left voice channel.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to leave voice: {e}")
            await interaction.followup.send("Failed to leave voice channel.", ephemeral=True)

    @app_commands.command(name="configure", description="Configure bot behavior")
    @app_commands.describe(
        setting="The setting to configure",
        value="The value to set"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="Verbosity (Length)", value="verbosity"),
        app_commands.Choice(name="Style (Tone)", value="style")
    ])
    async def configure(self, interaction: discord.Interaction, setting: str, value: str):
        """
        Configures a specific setting for the bot.
        For verbosity, valid values are: short, medium, long, dynamic.
        For style, valid values are: casual, formal, matching.
        """
        await interaction.response.defer(ephemeral=True)
        
        user_id = str(interaction.user.id)
        character_name = settings.DISCORD_BOT_NAME or "default"
        
        # Validate values
        if setting == "verbosity":
            if value.lower() not in ["short", "medium", "long", "dynamic"]:
                await interaction.followup.send("Invalid value for verbosity. Use: short, medium, long, dynamic", ephemeral=True)
                return
        elif setting == "style":
             if value.lower() not in ["casual", "formal", "matching"]:
                await interaction.followup.send("Invalid value for style. Use: casual, formal, matching", ephemeral=True)
                return

        try:
            from src_v2.evolution.trust import trust_manager
            await trust_manager.update_preference(user_id, character_name, setting, value.lower())
            await interaction.followup.send(f"Updated **{setting}** to **{value}**.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to update preference: {e}")
            await interaction.followup.send("Failed to update configuration.", ephemeral=True)

    @app_commands.command(name="stats_footer", description="Toggle stats footer on/off")
    @app_commands.describe(enabled="Enable or disable the stats footer")
    @app_commands.choices(enabled=[
        app_commands.Choice(name="Enable", value="true"),
        app_commands.Choice(name="Disable", value="false")
    ])
    async def stats_footer(self, interaction: discord.Interaction, enabled: str):
        """
        Toggles the stats footer display for this user.
        The footer shows relationship metrics, memory stats, and performance info.
        """
        await interaction.response.defer(ephemeral=True)
        
        user_id = str(interaction.user.id)
        character_name = settings.DISCORD_BOT_NAME or "default"
        
        try:
            from src_v2.utils.stats_footer import stats_footer
            is_enabled = enabled.lower() == "true"
            await stats_footer.toggle_for_user(user_id, character_name, is_enabled)
            
            status = "enabled" if is_enabled else "disabled"
            await interaction.followup.send(f"Stats footer **{status}**.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to toggle stats footer: {e}")
            await interaction.followup.send("Failed to toggle stats footer.", ephemeral=True)

class WhisperCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register the dynamic group
        self.bot.tree.add_command(CharacterCommands())

async def setup(bot: commands.Bot):
    await bot.add_cog(WhisperCommands(bot))
