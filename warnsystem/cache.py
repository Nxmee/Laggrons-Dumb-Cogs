import discord
import logging
import contextlib

from typing import Mapping, Optional
from redbot.core import Config

from .abc import MixinMeta

log = logging.getLogger("laggron.warnsystem")


class MemoryCache(MixinMeta):
    """
    This class is used to store most used Config values and reduce calls for optimization.
    See Github issue #49
    """

    async def _debug_info(self) -> str:
        """
        Compare the cached data to the Config data. Text is logged (INFO) then returned.
        
        This calls a huge part of the Config database and will not load it into the cache.
        """
        config_data = await self.data.all_guilds()
        mute_roles_cached = len(self.mute_roles)
        mute_roles = sum((x for x in config_data.values() if x["mute_role"] is not None))
        guild_temp_actions_cached = len(self.temp_actions)
        guild_temp_actions = len(config_data["temporary_warns"])
        temp_actions_cached = sum(len(x) for x in self.temp_actions.values())
        temp_actions = sum((len(x["temporary_warns"]) for x in config_data.values()))
        text = (
            f"Debug info requested\n"
            f"{mute_roles_cached}/{mute_roles} mute roles loaded in cache.\n"
            f"{guild_temp_actions_cached}/{guild_temp_actions} guilds with temp actions loaded in cache.\n"
            f"{temp_actions_cached}/{temp_actions} temporary actions loaded in cache."
        )
        log.info(text)
        return text

    async def get_mute_role(self, guild: discord.Guild):
        role_id = self.mute_roles.get(guild.id)
        if role_id:
            return role_id
        role_id = await self.data.guild(guild).mute_role()
        self.mute_roles[guild.id] = role_id
        return role_id

    async def update_mute_role(self, guild: discord.Guild, role: discord.Role):
        await self.data.guild(guild).mute_role.set(role.id)
        self.mute_roles[guild.id] = role.id

    async def get_temp_action(self, guild: discord.Guild, member: Optional[discord.Member] = None):
        guild_temp_actions = self.temp_actions.get(guild.id)
        if guild_temp_actions is None:
            guild_temp_actions = await self.data.guild(guild).temporary_warns.all()
            self.temp_actions[guild.id] = guild_temp_actions
        if member is None:
            return guild_temp_actions
        return guild_temp_actions.get(member.id)

    async def add_temp_action(self, guild: discord.Guild, member: discord.Member, data: dict):
        await self.data.guild(guild).temporary_warns.set_raw(member.id, value=data)
        try:
            guild_temp_actions = self.temp_actions[guild.id]
        except KeyError:
            self.temp_actions[guild.id] = {member.id: data}
        else:
            guild_temp_actions[member.id] = data

    async def remove_temp_action(self, guild: discord.Guild, member: discord.Member):
        await self.data.guild(guild).temporary_warns.clear_raw(member.id)
        with contextlib.suppress(KeyError):
            del self.temp_actions[guild.id][member.id]

    async def bulk_remove_temp_action(self, guild: discord.Guild, members: list):
        members = [x.id for x in members]
        warns = await self.get_temp_action(guild)
        warns = {x: y for x, y in warns.items() if x not in members}
        await self.data.guild(guild).temporary_warns.set(warns)
        self.temp_actions[guild.id] = warns
