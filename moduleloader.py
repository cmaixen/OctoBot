"""
Plugin loader from Octeon - Pinky
"""
import importlib.util
import os.path
from glob import glob
from logging import getLogger
import re
import textwrap
import html

from telegram.ext import Updater
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

LOGGER = getLogger("Octeon-Pinky")
class CorePlugin:
    def coreplug_reload(self, bot, update, user, *__):
        if user.id == settings.ADMIN:
            LOGGER.info("Reload requested.")
            update.message.reply_text("Reloading modules. ")
            self.load_all_plugins()
            return self.coreplug_list()
        else:
            return octeon.message("Access Denied.")

    def coreplug_start(self, bot, update, user, args):
        if len(args) > 0:
            if args[0] == "help" and update.message.chat.type == "private":
                return self.gen_help()
        return octeon.message("Hi! I am Octeon, %s bot with random stuff!\nTo see my commands, type: /help" % self.platform)

    def coreplug_help(self, bot, update, user, args):
        if args:
            for plugin in self.plugins:
                for command in plugin["commands"]:
                    if args[0].lower() == command["command"].lower():
                        info = {"command":args[0], "description":"Not available", "docs":"Not available"}
                        info["description"] = command["description"]
                        if command["function"].__doc__:
                            info["docs"] = html.escape(textwrap.dedent(command["function"].__doc__))
                        return octeon.message(COMMAND_INFO % info, parse_mode="HTML")
            return "I dont know this command"
        else:
            if update.message.chat.type == "private":
                return octeon.message(self.gen_help(), parse_mode="HTML")
            else:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text="List commands in PM", url="http://t.me/%s?start=help" % bot.getMe().username)]])
                return octeon.message("To prevent flood, use this command in PM", inline_keyboard=keyboard)

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
            LOGGER.info("Reload requested.")
            update.message.reply_text("Loading " + args)
            self.load_plugin(args)
            return self.coreplug_list()
        else:
            return octeon.message("Access Denied.")

class Pinky(CorePlugin):
    def __init__(self):
        self.plugins = []
        self.platform = "telegram"
        LOGGER.info("Starting Octeon-Pinky. Loading plugins.")
        self.load_all_plugins()

    def gen_help(self):
        docs = ""
        for plugin in self.plugins:
            for command in plugin["commands"]:
                if "description" in command:
                    if "hidden" in command:
                        if command["hidden"]:
                            continue
                    docs += "%s - <i>%s</i>\n" % (command["command"],
                                           command["description"])
        docs += "\nYou can find more info about command by typing after /help, like this: <pre>/help /cash</pre>"
        return docs

    def load_all_plugins(self):
        self.plugins.clear()
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

    def load_plugin(self, plugpath):
        plugname = os.path.basename(plugpath).split(".py")[0]
        try:
            spec = importlib.util.spec_from_file_location("octeon.plugin", plugpath)
            plugin = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(plugin)
        except Exception as f:
            LOGGER.warning("Plugin %s failed to init cause of %s", plugname, f)
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
                LOGGER.info("Legacy module %s loaded", plugname)
            else:
                # Working with new plugins
                self.plugins.append({
                    "state": OK,
                    "name": plugname,
                    "commands": plugin.plugin.commands,
                    "messagehandles": plugin.plugin.handlers,
                    "disabledin": []
                })
                LOGGER.info("Module %s loaded", plugname)

    def handle_command(self, update):
        for plugin in self.plugins:
            if update.message.chat.id in plugin["disabledin"]:
                continue
            else:
                for command_info in plugin["commands"]:
                    command = command_info["command"]
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
