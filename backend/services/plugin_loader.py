"""
CHIMERA v2 Plugin Loader
Discovers, loads, validates, and registers strategy plugins.
"""

import logging
from typing import Dict, Optional

from plugins.base import BasePlugin
from plugins.marks_rule_1 import MarksRule1Plugin
import database as db

logger = logging.getLogger(__name__)


class PluginLoader:
    """Manages loading and registration of strategy plugins."""

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}

    @property
    def plugins(self) -> Dict[str, BasePlugin]:
        return self._plugins.copy()

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """Get a loaded plugin by ID."""
        return self._plugins.get(plugin_id)

    async def load_all(self):
        """Load and register all available plugins."""
        logger.info("Loading plugins...")

        # Built-in plugins
        builtins = [
            MarksRule1Plugin(),
        ]

        for plugin in builtins:
            try:
                self._plugins[plugin.get_id()] = plugin

                # Register in database
                metadata = plugin.get_metadata()
                await db.upsert_plugin(metadata)

                logger.info(
                    f"  Loaded: {plugin.get_name()} v{plugin.get_version()} "
                    f"[{plugin.get_id()}]"
                )
            except Exception as e:
                logger.error(f"  Failed to load plugin {plugin.get_id()}: {e}")

        logger.info(f"Loaded {len(self._plugins)} plugin(s)")

    async def get_active_plugins(self) -> list[BasePlugin]:
        """Get plugins that are enabled, sorted by priority."""
        db_plugins = await db.get_plugins()
        active = []

        for p in db_plugins:
            if p.get("enabled"):
                plugin = self._plugins.get(p["id"])
                if plugin:
                    active.append(plugin)

        return active

    async def reload(self):
        """Reload all plugins (re-read configs, etc.)."""
        self._plugins.clear()
        await self.load_all()


# Singleton
plugin_loader = PluginLoader()
