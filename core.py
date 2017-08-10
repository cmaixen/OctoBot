"""
Octeon Core
"""
import importlib.util
import os.path
from glob import glob
from logging import getLogger
import re
import textwrap
import html

from telegram.ext import Updater, CommandHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import octeon
import settings
from constants import ERROR, OK

COMMAND_INFO = """
%(command)s
Description: <i>%(description)s</i>
Additional info and examples:
<i>%(docs)s</i>
"""

class DefaultPlugin:
    def coreplug_reload(self, bot, update, user, *__):
        if user.id == settings.ADMIN:
            self.logger.info("Reload requested.")
            update.message.reply_text("Reloading modules. ")
            self.load_all_plugins()
            return self.coreplug_list()
        else:
            return octeon.message("Access Denied.")

    def coreplug_start(*_, **__):
        raise RuntimeError

    def coreplug_help(*_, **__):
        raise RuntimeError

    def coreplug_list(self, *_):
        message = []
        for plugin in self.plugins:
            txt = ''
            if plugin["state"] == OK:
                txt += "✅"
            else:
                txt += "⛔"
            txt += plugin["name"]
            message.append(txt)
        message = sorted(message)
        message.reverse()
        return octeon.message("\n".join(message))

    def coreplug_load(self, bot, update, user, args):
        args = " ".join(args)
        if user.id == settings.ADMIN:
            self.logger.info("Reload requested.")
            update.message.reply_text("Loading " + args)
            self.load_plugin(args)
            return self.coreplug_list()
        else:
            return octeon.message("Access Denied.")

class OcteonCore(DefaultPlugin):
    def __init__(self):
        self.logger = getLogger("Octeon-Core")
        self.plugins = []
        self.disabled = []
        self.platform = "N/A"
        self.logger.info("Starting Octeon-Core. Loading plugins.")
        self.load_all_plugins()

    def gen_help(self):
        raise RuntimeError

    def create_command_handler(self, command, function):
        raise RuntimeError

    def load_all_plugins(self):
        self.plugins.clear()
        if 0 in self.dispatcher.handlers:
            for handle in self.dispatcher.handlers[0]:
                if isinstance(handle, CommandHandler):
                    self.dispatcher.remove_handler(handle)
        for filename in glob("plugins/*.py"):
            self.load_plugin(filename)
        self.plugins.append({
            "state": OK,
            "name": "Octeon Core Plugin",
            "commands": [{"command": "/start", "function": self.coreplug_start},
                         {"command": "//plugins", "function": self.coreplug_list},
                         {"command": "/help", "function": self.coreplug_help},
                         {"command": "//reload", "function": self.coreplug_reload},
                         {"command": "//pluginload", "function": self.coreplug_load}],
            "messagehandles": [],
            "disabledin": []
        })
        self.logger.info("Adding handlers")
        for plugin in self.plugins:
            for command in plugin["commands"]:
                self.create_command_handler(command["command"], command["function"])

    def load_plugin(self, plugpath):
        plugname = os.path.basename(plugpath).split(".py")[0]
        try:
            spec = importlib.util.spec_from_file_location("octeon.plugin", plugpath)
            plugin = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(plugin)
        except Exception as f:
            self.logger.warning("Plugin %s failed to init cause of %s", plugname, f)
            self.plugins.append({
                "state": ERROR,
                "name": plugname,
                "commands": [],
                "disabledin": []
            })
        else:
            try:
                plugin.PLUGINVERSION
            except AttributeError:
                # Working with outdated plugins.
                self.plugins.append({
                    "state": OK,
                    "name": plugname,
                    "commands": plugin.COMMANDS,
                    "messagehandles": [],
                    "disabledin": []
                })
                self.logger.info("Legacy module %s loaded", plugname)
            else:
                # Working with new plugins
                self.plugins.append({
                    "state": OK,
                    "name": plugname,
                    "commands": plugin.plugin.commands,
                    "messagehandles": plugin.plugin.handlers,
                    "disabledin": []
                })
                self.logger.info("Module %s loaded", plugname)

    def handle_command(self, update):
        for plugin in self.plugins:
            if update.message.chat.id in plugin["disabledin"]:
                continue
            else:
                for command_info in plugin["commands"]:
                    command = command_info["command"]
                    if command.endswith("/"):
                        function = command_info["function"]
                        state_only_command = update.message.text == command or update.message.text.startswith(
                            command + " ")
                        state_word_swap = len(update.message.text.split(
                            "/")) > 2 and update.message.text.startswith(command)
                        state_mention_command = update.message.text.startswith(command + "@")
                        if state_only_command or state_word_swap or state_mention_command:
                            return function

    def handle_inline(self, update):
        for plugin in self.plugins:
            for command_info in plugin["commands"]:
                command = command_info["command"]
                function = command_info["function"]
                if update.inline_query.query.startswith(command):
                    return function, command

    def handle_message(self, update):
        handlers = []
        for plugin in self.plugins:
            if "messagehandles" in plugin:
                for message_info in plugin["messagehandles"]:
                    if re.match(message_info["regex"], update.message.text):
                        handlers.append(message_info["function"])
        return handlers