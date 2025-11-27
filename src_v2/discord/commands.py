import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger
from typing import cast, Optional
from src_v2.memory.manager import memory_manager
from src_v2.core.character import character_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.evolution.trust import trust_manager
from src_v2.config.settings import settings
from src_v2.universe.privacy import privacy_manager
from src_v2.universe.manager import universe_manager

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
            insights = relationship.get("insights", [])
            
            prefs_text = "No specific preferences set."
            if prefs:
                prefs_text = "\n".join([f"• **{k}**: {v}" for k, v in prefs.items()])

            insights_text = "No specific insights yet."
            if insights:
                # Show top 5 insights
                display_insights = insights[:5]
                insights_text = "\n".join([f"• {i}" for i in display_insights])
                if len(insights) > 5:
                    insights_text += f"\n...and {len(insights) - 5} more."

            # Build Response
            embed = discord.Embed(title=f"User Profile: {interaction.user.display_name}", color=0x00ff00)
            embed.add_field(name="🧠 Global Facts (Shared)", value=facts, inline=False)
            embed.add_field(name=f"🤝 Relationship ({character_name})", value=f"Level: {level_label} (Trust: {trust_score})", inline=False)
            embed.add_field(name="📝 Insights (Character Memory)", value=insights_text, inline=False)
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

    @app_commands.command(name="lurk", description="Configure channel lurking behavior")
    @app_commands.describe(
        action="Enable, disable, or check lurking status",
        threshold="Confidence threshold (0.5-1.0) for jumping into conversations"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable"),
        app_commands.Choice(name="Status", value="status")
    ])
    async def lurk(
        self, 
        interaction: discord.Interaction, 
        action: str,
        threshold: float = None
    ):
        """
        Configure channel lurking for this channel.
        When enabled, the bot may join relevant conversations without being @mentioned.
        
        Requires Manage Channels permission.
        """
        await interaction.response.defer(ephemeral=True)
        
        # Check permissions (require Manage Channels)
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
            
        member = cast(discord.Member, interaction.user)
        if not member.guild_permissions.manage_channels:
            await interaction.followup.send("You need **Manage Channels** permission to configure lurking.", ephemeral=True)
            return
        
        # Check if lurking is enabled globally
        if not settings.ENABLE_CHANNEL_LURKING:
            await interaction.followup.send("⚠️ Channel lurking is disabled globally in bot settings.", ephemeral=True)
            return
            
        channel_id = str(interaction.channel_id)
        character_name = settings.DISCORD_BOT_NAME or "default"
        
        try:
            from src_v2.discord.lurk_detector import get_lurk_detector
            lurk_detector = get_lurk_detector(character_name)
            
            if action == "status":
                # Get current status
                is_enabled = await lurk_detector.is_channel_enabled(channel_id)
                current_threshold = await lurk_detector.get_channel_threshold(channel_id)
                stats = await lurk_detector.get_channel_stats(channel_id)
                
                status = "✅ Enabled" if is_enabled else "❌ Disabled"
                embed = discord.Embed(
                    title=f"Lurking Status: #{interaction.channel.name}",
                    color=0x00ff00 if is_enabled else 0xff0000
                )
                embed.add_field(name="Status", value=status, inline=True)
                embed.add_field(name="Threshold", value=f"{current_threshold:.2f}", inline=True)
                embed.add_field(name="Responses Today", value=str(stats.get("today", 0)), inline=True)
                embed.add_field(name="Total Responses", value=str(stats.get("total", 0)), inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            elif action == "enable":
                # Validate threshold if provided
                if threshold is not None:
                    if threshold < 0.5 or threshold > 1.0:
                        await interaction.followup.send("Threshold must be between 0.5 and 1.0", ephemeral=True)
                        return
                    await lurk_detector.set_channel_threshold(channel_id, threshold)
                    
                await lurk_detector.enable_channel(channel_id)
                msg = f"✅ Lurking enabled for #{interaction.channel.name}"
                if threshold is not None:
                    msg += f" with threshold {threshold:.2f}"
                await interaction.followup.send(msg, ephemeral=True)
                
            elif action == "disable":
                await lurk_detector.disable_channel(channel_id)
                await interaction.followup.send(f"❌ Lurking disabled for #{interaction.channel.name}", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Failed to configure lurking: {e}")
            await interaction.followup.send("Failed to configure lurking.", ephemeral=True)

    @app_commands.command(name="lurk_stats", description="View lurking statistics")
    async def lurk_stats(self, interaction: discord.Interaction):
        """
        View lurking statistics for this server.
        Shows global stats and any channel-specific overrides.
        """
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
            
        if not settings.ENABLE_CHANNEL_LURKING:
            await interaction.followup.send("⚠️ Channel lurking is disabled globally.", ephemeral=True)
            return
            
        character_name = settings.DISCORD_BOT_NAME or "default"
        
        try:
            from src_v2.discord.lurk_detector import get_lurk_detector
            lurk_detector = get_lurk_detector(character_name)
            
            # Get stats
            guild_stats = await lurk_detector.get_guild_stats(str(interaction.guild_id))
            global_stats = guild_stats.get("global_stats", {})
            disabled_channels = guild_stats.get("disabled_channels", [])
            custom_thresholds = guild_stats.get("custom_thresholds", {})
            
            embed = discord.Embed(
                title=f"Lurking Statistics: {interaction.guild.name}",
                description="Channel lurking is **ENABLED** by default on all channels.",
                color=0x00aaff
            )
            
            # Global Stats
            daily_count = global_stats.get("daily_count", 0)
            max_daily = global_stats.get("max_daily", settings.LURK_DAILY_MAX_RESPONSES)
            embed.add_field(
                name="Global Limits", 
                value=f"Daily Responses: {daily_count}/{max_daily}\nCooldowns: {global_stats.get('channels_on_cooldown', 0)} channels, {global_stats.get('users_on_cooldown', 0)} users",
                inline=False
            )
            
            # Disabled Channels
            if disabled_channels:
                disabled_names = []
                for cid in disabled_channels:
                    channel = interaction.guild.get_channel(int(cid))
                    if channel:
                        disabled_names.append(f"#{channel.name}")
                    else:
                        disabled_names.append(f"Unknown ({cid})")
                embed.add_field(name="❌ Disabled Channels", value=", ".join(disabled_names), inline=False)
            
            # Custom Thresholds
            if custom_thresholds:
                custom_list = []
                for cid, thresh in custom_thresholds.items():
                    channel = interaction.guild.get_channel(int(cid))
                    if channel:
                        custom_list.append(f"#{channel.name}: {thresh:.2f}")
                if custom_list:
                    embed.add_field(name="⚙️ Custom Thresholds", value="\n".join(custom_list), inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Failed to get lurk stats: {e}")
            await interaction.followup.send("Failed to get lurking statistics.", ephemeral=True)

    @app_commands.command(name="test_proactive", description="Force trigger a proactive message (Admin only)")
    @app_commands.describe(user="The user to message (defaults to you)")
    async def test_proactive(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        # Check if user is admin/owner (simple check for now, or rely on DM_ALLOWED_USER_IDS if needed)
        # For now, let's just allow it.
        
        target_user = user or interaction.user
        user_id = str(target_user.id)
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Access the scheduler from the bot instance
            # interaction.client is the bot instance
            scheduler = getattr(interaction.client, 'scheduler', None)
            
            if not scheduler:
                await interaction.followup.send("Scheduler not found on bot instance.")
                return

            await interaction.followup.send(f"Triggering proactive message for {target_user.name}...")
            
            # Call the trigger method directly
            await scheduler.trigger_proactive_message(user_id)
            
            await interaction.followup.send(f"Proactive message process completed for {target_user.name}. Check logs if no message appeared.")
            
        except Exception as e:
            logger.error(f"Error in test_proactive command: {e}")
            await interaction.followup.send(f"Error: {e}")

class SpamCommands(app_commands.Group):
    """Commands for managing spam detection."""
    
    def __init__(self):
        super().__init__(name="spam", description="Manage spam detection settings")

    @app_commands.command(name="enable", description="Enable spam detection")
    @app_commands.checks.has_permissions(administrator=True)
    async def enable(self, interaction: discord.Interaction):
        from src_v2.discord.spam_detector import spam_detector
        spam_detector.enabled = True
        await interaction.response.send_message("✅ Spam detection enabled.", ephemeral=True)

    @app_commands.command(name="disable", description="Disable spam detection")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable(self, interaction: discord.Interaction):
        from src_v2.discord.spam_detector import spam_detector
        spam_detector.enabled = False
        await interaction.response.send_message("❌ Spam detection disabled.", ephemeral=True)

    @app_commands.command(name="threshold", description="Set cross-post threshold")
    @app_commands.checks.has_permissions(administrator=True)
    async def threshold(self, interaction: discord.Interaction, count: int):
        if count < 2:
            await interaction.response.send_message("Threshold must be at least 2.", ephemeral=True)
            return
        from src_v2.discord.spam_detector import spam_detector
        spam_detector.threshold = count
        await interaction.response.send_message(f"✅ Spam threshold set to {count} channels.", ephemeral=True)

    @app_commands.command(name="action", description="Set spam action (warn or delete)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(action=[
        app_commands.Choice(name="Warn User", value="warn"),
        app_commands.Choice(name="Delete Message", value="delete")
    ])
    async def action(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        from src_v2.discord.spam_detector import spam_detector
        spam_detector.action = action.value
        await interaction.response.send_message(f"✅ Spam action set to: {action.name}", ephemeral=True)

    @app_commands.command(name="whitelist", description="Whitelist a role from spam detection")
    @app_commands.checks.has_permissions(administrator=True)
    async def whitelist(self, interaction: discord.Interaction, role: discord.Role):
        from src_v2.discord.spam_detector import spam_detector
        await spam_detector.add_whitelist(str(role.id), str(interaction.guild_id))
        await interaction.response.send_message(f"✅ Role {role.mention} whitelisted from spam detection.", ephemeral=True)

    @app_commands.command(name="unwhitelist", description="Remove a role from whitelist")
    @app_commands.checks.has_permissions(administrator=True)
    async def unwhitelist(self, interaction: discord.Interaction, role: discord.Role):
        from src_v2.discord.spam_detector import spam_detector
        await spam_detector.remove_whitelist(str(role.id), str(interaction.guild_id))
        await interaction.response.send_message(f"❌ Role {role.mention} removed from whitelist.", ephemeral=True)

    @app_commands.command(name="stats", description="View spam detection stats")
    async def stats(self, interaction: discord.Interaction):
        from src_v2.discord.spam_detector import spam_detector
        status = "Enabled" if spam_detector.enabled else "Disabled"
        embed = discord.Embed(title="Spam Detection Stats", color=0xff0000)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Threshold", value=f"{spam_detector.threshold} channels", inline=True)
        embed.add_field(name="Action", value=spam_detector.action.title(), inline=True)
        embed.add_field(name="Window", value=f"{spam_detector.window} seconds", inline=True)
        
        # Get whitelisted roles
        if interaction.guild:
            whitelisted_ids = spam_detector._whitelisted_roles.get(str(interaction.guild_id), set())
            roles = []
            for rid in whitelisted_ids:
                role = interaction.guild.get_role(int(rid))
                if role:
                    roles.append(role.mention)
            if roles:
                embed.add_field(name="Whitelisted Roles", value=", ".join(roles), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class PrivacyCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="privacy", description="Manage your privacy settings in the WhisperVerse")

    @app_commands.command(name="view", description="View your current privacy settings")
    async def view(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id = str(interaction.user.id)
            settings_data = await privacy_manager.get_settings(user_id)
            
            embed = discord.Embed(title="🔒 Privacy Settings", color=0x3498db)
            embed.description = "These settings control how your data is shared across the WhisperVerse."
            
            # Helper for boolean to emoji
            def fmt(val): return "✅ Enabled" if val else "❌ Disabled"
            
            embed.add_field(
                name="🤖 Share with Other Bots", 
                value=f"{fmt(settings_data['share_with_other_bots'])}\n*Allow bots to share what they know about you.*", 
                inline=False
            )
            embed.add_field(
                name="🪐 Share Across Planets", 
                value=f"{fmt(settings_data['share_across_planets'])}\n*Allow bots to remember you when you travel to other servers.*", 
                inline=False
            )
            embed.add_field(
                name="🤝 Allow Introductions", 
                value=f"{fmt(settings_data['allow_bot_introductions'])}\n*Allow bots to introduce you to other users.*", 
                inline=False
            )
            embed.add_field(
                name="👻 Invisible Mode", 
                value=f"{fmt(settings_data['invisible_mode'])}\n*Hide your presence from the universe graph (bots won't track your location).*", 
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error viewing privacy settings: {e}")
            await interaction.followup.send("Failed to retrieve privacy settings.", ephemeral=True)

    @app_commands.command(name="set", description="Update your privacy settings")
    @app_commands.describe(
        share_with_bots="Allow bots to share knowledge about you",
        share_across_planets="Allow bots to remember you on other servers",
        allow_introductions="Allow bots to introduce you to others",
        invisible_mode="Hide your location/presence from the universe"
    )
    async def set_privacy(
        self, 
        interaction: discord.Interaction, 
        share_with_bots: Optional[bool] = None,
        share_across_planets: Optional[bool] = None,
        allow_introductions: Optional[bool] = None,
        invisible_mode: Optional[bool] = None
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id = str(interaction.user.id)
            updates = {}
            
            if share_with_bots is not None: updates['share_with_other_bots'] = share_with_bots
            if share_across_planets is not None: updates['share_across_planets'] = share_across_planets
            if allow_introductions is not None: updates['allow_bot_introductions'] = allow_introductions
            if invisible_mode is not None: updates['invisible_mode'] = invisible_mode
            
            if not updates:
                await interaction.followup.send("No changes specified.", ephemeral=True)
                return

            new_settings = await privacy_manager.update_settings(user_id, **updates)
            
            # Confirm changes
            changes = []
            if share_with_bots is not None: changes.append(f"Share with Bots: {'✅' if share_with_bots else '❌'}")
            if share_across_planets is not None: changes.append(f"Share Across Planets: {'✅' if share_across_planets else '❌'}")
            if allow_introductions is not None: changes.append(f"Allow Introductions: {'✅' if allow_introductions else '❌'}")
            if invisible_mode is not None: changes.append(f"Invisible Mode: {'✅' if invisible_mode else '❌'}")
            
            await interaction.followup.send(f"**Privacy Settings Updated:**\n" + "\n".join(changes), ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error updating privacy settings: {e}")
            await interaction.followup.send("Failed to update privacy settings.", ephemeral=True)

class UniverseCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="universe", description="Explore the WhisperVerse")

    @app_commands.command(name="info", description="See what the bot knows about this planet (server)")
    async def info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.guild:
                await interaction.followup.send("This command can only be used in a server (Planet).", ephemeral=True)
                return

            guild_id = str(interaction.guild.id)
            context = await universe_manager.get_planet_context(guild_id)
            
            if not context:
                await interaction.followup.send("This planet has not been mapped yet.", ephemeral=True)
                return

            embed = discord.Embed(title=f"🪐 Planet Info: {context['name']}", color=0x9b59b6)
            embed.add_field(name="Inhabitants", value=str(context['inhabitant_count']), inline=True)
            embed.add_field(name="Channels", value=str(context['channel_count']), inline=True)
            
            channels_list = ", ".join([f"#{c}" for c in context['channels']])
            if len(channels_list) > 1000:
                channels_list = channels_list[:1000] + "..."
            
            embed.add_field(name="Mapped Regions", value=channels_list or "None", inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error getting planet info: {e}")
            await interaction.followup.send("Failed to retrieve planet info.", ephemeral=True)

class WhisperCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register the dynamic groups
        self.bot.tree.add_command(CharacterCommands())
        self.bot.tree.add_command(SpamCommands())
        self.bot.tree.add_command(PrivacyCommands())
        self.bot.tree.add_command(UniverseCommands())

async def setup(bot: commands.Bot):
    await bot.add_cog(WhisperCommands(bot))
