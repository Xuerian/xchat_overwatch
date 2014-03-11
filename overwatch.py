__module_name__ = "overwatch-mode"
__module_version__ = "0.6"
__module_description__ = "Provides channel groups which share message logs"

option_defaults = {
    # Focus group on load
    "focus_on_load": False,
    # Hide repeated channel names
    "hide_inline_channel": True,
    # Replace repeated channel with
    "inline_channel_prefix": "| ",
    # Shorten repeated nicks
    # "truncate_nick_inline": False,
    # "truncate_nick_length": 4,
    # Color channels like heXchat's colored nicks
    "colored_channel_names": True,
    "channel_colors": [19, 20, 22, 24, 25, 26, 27, 28, 29],
    # Update target based on time since last action
    "auto_target": True,
    # Action to take with target
    "auto_target_action": "clear",  # clear, update
    # Seconds to wait after sending message before auto-updating
    "auto_target_delay": 10,
    "auto_target_delay_empty": 5,
    # Retain target after sending message
    "keep_target": False,
    # Message grouping
    "group_messages": False,
    # Buffer time in seconds
    "nick_buffer_focused": 2,
    "nick_buffer_unfocused": 6,
    "chan_buffer_focused": 3,
    "chan_buffer_unfocused": 10,
}


# TODO: Improve tab completion (It doesn't feel natural sometimes)
# TODO: Reduce overlaps in channel coloring? Might not be worth it due to low optimal channel number.
# This conflicts with hexchat's color = len(nick) % len(colors)
# TODO: Shortcuts (Reply to last hilight, send to last channel, clear to channel name, focus last channel)
# TODO: Right click menu in channel (Focus channel, remove channel, add channel)
# TODO: Sort autocomplete lists based off last time instead of merging lists?
# TODO: Buffer chat to collapse nick spam and to lower channel context switching

import xchat
from time import time
import re
from collections import deque, defaultdict
from functools import partial  # Magic
import os
import json
from pprint import pprint

MOD_SHIFT = 1
MOD_CTRL = 4
MOD_ALT = 8

SHIFT = 0xFFE1
TAB = 0xFF09
LEFT_TAB = 0xFE20
ENTER = 0xFF0D
BACKSPACE = 0xFF08

# Standardize file location
configdir = xchat.get_info("configdir")
if not configdir:  # For xchat
    configdir = xchat.get_info("xchatdir")

padding = ["", "", ""]  # Prevents format from complaining on short events

events_decoded = {}  # Event strings decoded with channel marker added

# Extracting nicks
re_nick = re.compile(r"^(\x03[\d]+)?(.+?)$")

# Channel text patterns
pattern_channel_visible = "\003{1}\010(\010{0}\010)\010\017 "
pattern_channel_hidden = "\003{1}\010({0})\010{2}\017"


# Wrapper for contexts
class xbuffer:
    def __init__(self, name, is_server=True):
        self.name = name
        self.is_server = is_server
        self.acquire_context()

    def acquire_context(self):
        self.context = xchat.find_context(server=self.name)
        if not self.context:
            xchat.find_context().set()
            if self.is_server:
                xchat.command('newserver -noconnect "{}"'.format(self.name))
            else:
                xchat.command('query "{}"'.format(self.name))
            self.context = xchat.find_context(server=self.name)

    def focus(self):
        self.context.set()
        self.context.command("gui focus")

    def get_input(self):
        return self.context.get_info("inputbox")

    def get_input_cursor(self):
        return self.context.get_prefs("state_cursor")

    def set_input(self, value, move_cursor=True):
        self.context.command("settext " + value)
        if move_cursor:
            self.set_input_cursor(len(value))

    def set_input_cursor(self, pos):
        self.context.command("setcursor " + str(pos))

    def rename(self, name):
        self.name = name
        self.context.command("close")
        del self.context
        self.acquire_context()

    def close(self):
        self.context.command("close")


def jsonify_structure(struct):
    if isinstance(struct, dict):
        return {k:jsonify_structure(struct[k]) for k in struct}
    if isinstance(struct, set) or isinstance(struct, list):
        return [jsonify_structure(x) for x in struct]
    return struct


# Write a structure (dict, list, set) to a file in JSON
def json_file_write(path, name, struct):
    if not os.path.exists(path):
        os.makedirs(path)
    with open(os.path.join(path, name), "w") as f:
        json.dump(struct, f, indent=2, sort_keys=True)


# Read a object in from a JSON file
def json_file_read(path, name):
    try:
        with open(os.path.join(path, name), "r") as f:
            return json.load(f)
    except:
        return False

configdir_script = os.path.join(configdir, "addons", "config")


registered_channels = {}
registered_groups = {}


def cmd(stuff):
    xchat.command(stuff)


def menu_add(path, command=None, pos=None):
    if command:
        body = '"{}" "{}"'.format(path, command)
    else:
        body = '"{}"'.format(path)
    if pos:
        cmd("MENU -p{} ADD {}".format(pos, body))
    else:
        cmd("MENU ADD "+body)


def menu_del(path):
    cmd('MENU DEL "{}"'.format(path))


# Group registration
def register_group(group, save=True):
    registered_groups[group.name] = group
    if save:
        group_settings_save()


def unregister_group(group):
    registered_groups.pop(group.name)
    group_settings_save()


# Channel registration
def register_group_channel(network, channel, group, save=True):
    l = registered_channels.setdefault(network, {}).setdefault(channel, [])
    if group not in l:
        l.append(group)
    if save:
        group_settings_save()


def unregister_group_channel(network, channel, group):
    registered_channels[network][channel].remove(group)
    group_settings_save()


# Find groups registered for given channel
def registered_channel_groups(network, channel):
    if network in registered_channels and channel in registered_channels[network]:
        return iter(registered_channels[network][channel])


# Save group settings to file
def group_settings_save():
    json = []
    for name, group in registered_groups.items():
        json.append({"name": name, "channels": group.channels, "options": group.options})
    json_file_write(configdir_script, "overwatch-mode.json", json)


# Load group settings from file and reinitialize
def groups_load_from_settings():
    json = json_file_read(configdir_script, "overwatch-mode.json")
    if isinstance(json, list):
        for group in json:
                channel_group(group["name"], group)


# Colorize string according to XChat's formula
def xchat_color_string(string, colors):
    return colors[len(string) % len(colors)]


class channel_group:
    def __init__(self, group_name, save_data={}):
        # Initialize buffer
        self.buffer = xbuffer(group_name)
        self.name = group_name
        # Initialize various values (SINCE APPARENTLY VALUES ARE STATIC NOT DEFAULT WHAT)
        self.channel_current = None
        self.channel_previous = None
        self.auto_list = deque()
        self.auto_type = None
        self.auto_first = False
        self.recent_users = {}
        self.recent_channels = {}
        self.chanrefs = {}
        self.backrefs = {}
        self.last_action = time()

        # Apply saved options
        if "options" in save_data:
            self.options = save_data["options"]
        else:
            self.options = {}
        # Add new options
        for k, v in option_defaults.items():
            if k not in self.options:
                self.options[k] = v

        # Load channel list
        self.channels = {}
        if "channels" in save_data:
            for network, channels in save_data["channels"].items():
                for channel in channels:
                    self.add_channel(network, channel, False)

        # Save if not already loading
        register_group(self, "options" not in save_data)

        # Create menu items
        self.menu_update()

        self.channels_update()

        # Focus
        if self.options["focus_on_load"]:
            self.buffer.focus()

    # Simple joined output
    def _print(self, *args):
        self.buffer.context.prnt(', '.join(str(x) for x in args))

    # Add recieved channel messages to buffer
    def on_chat_message(self, network, channel, event, nick, nick_color, args, word, word_eol):
        # Colorize channel name
        if self.options["colored_channel_names"]:
            channel_color = xchat_color_string(channel, self.options["channel_colors"])
        else:
            channel_color = self.options["channel_colors"][0]

        # Inline successive channels
        if self.options["hide_inline_channel"] and self.channel_current == (network, channel):
            channel_text = pattern_channel_hidden.format(channel, channel_color, self.options["inline_channel_prefix"])
        else:
            channel_text = pattern_channel_visible.format(channel, channel_color)

        # Add to buffer
        self.buffer.context.prnt(events_decoded[event].format(channel_text, word[0], *args))

        # Recents
        chanref = self.backrefs[(network, channel)]
        self.recent_channels[chanref] = now = time()
        self.recent_users.setdefault((network, channel), {})[nick] = now

        # Update prompt
        if self.options["auto_target"]:
            line = self.buffer.get_input().strip()
            if now - self.last_action > self.options["auto_target_delay"] or (not line and now - self.last_action > self.options["auto_target_delay_empty"]):
                if not line or (line in self.chanrefs and line != chanref):
                    action = self.options["auto_target_action"]
                    if action == "clear":
                        self.buffer.set_input("")
                    elif action == "update":
                        self.buffer.set_input(chanref + " ")
                    self.auto_clear()

        # Update state
        self.channel_previous = self.channel_current
        self.channel_current = (network, channel)

    def auto_list_channels(self, search=""):
        self.auto_list.clear()
        self.auto_type = 1
        # Rest of channels
        chans = [k for k in self.recent_channels if k.startswith(search)]
        chans.sort(key=lambda k: self.recent_channels[k], reverse=True)
        self.auto_list.extend(chans)

    def auto_list_users(self, network, channel, search=""):
        self.auto_list.clear()
        self.auto_type = 2
        p = re.compile(re.escape(search), re.I)
        # Recently seen nicks from this channel
        if (network, channel) in self.recent_users:
            recent = [k for k in self.recent_users[(network, channel)] if bool(p.match(k))]
            recent.sort(reverse=True, key=lambda k: self.recent_users[(network, channel)][k])
        else:
            recent = []
        # Get rest of nicks from target channel
        channel_context = xchat.find_context(network, channel)
        if channel_context:
            channel_context.get_info("channel")  # Without a get_info call, get_list fails
            full = [x.nick for x in channel_context.get_list("users") if bool(p.match(x.nick)) and x.nick not in recent]
            full.sort()
            self.auto_list.extend(recent + full)
        else:
            self.auto_list.extend(recent)

    def auto_list_rotate(self, mod, current=""):
        if current and len(self.auto_list) > 1:
            while 1:
                self.auto_list.rotate(mod)
                if current != self.auto_list[0]:
                    break
        else:
            self.auto_list.rotate(mod)

    def auto_clear(self):
        if not self.auto_first:
            self.auto_first = True
            self.auto_list.clear()
            self.auto_type = None

    # Handle key presses in window
    def on_key_press(self, key, modifiers):
        if key == TAB or key == LEFT_TAB:
            text = self.buffer.get_input().strip()
            word = text.split(" ", 1)
            num = len(word)
            if num == 2:
                (line, nick) = text.rsplit(" ", 1)

            # Generate autocomplete list
            if self.auto_first:
                if num == 1:
                    # Tab to next channel
                    if word[0] in self.chanrefs:
                        self.auto_list_channels()
                        self.auto_first = False
                    # Complete channel name
                    elif word[0] and not word[0].startswith("#"):
                        self.auto_list_channels("#" + word[0])
                    # Search partial chanel
                    else:
                        self.auto_list_channels(word[0])
                # Search nick
                elif num == 2:
                    self.auto_list_users(self.chanrefs[word[0]][0], self.chanrefs[word[0]][1], nick)

            if self.auto_list:
                # Rotate to next
                if not self.auto_first:
                    # Shift-tab
                    if modifiers == 1:
                        mod = 1
                    # Tab or something else?
                    else:
                        mod = -1
                    self.auto_list_rotate(mod, self.auto_type == 1 and word[0] or nick)
                # Complete channel
                if self.auto_type == 1:
                    self.buffer.set_input(self.auto_list[0] + " " + (num > 1 and word[1] or ""))
                # Complete nick
                else:
                    self.buffer.set_input("%s %s%s " % (line, self.auto_list[0], xchat.get_prefs("completion_suffix")))
                self.auto_first = False

            return xchat.EAT_ALL

        elif key != SHIFT:
            self.auto_first = True
            self.last_action = time()
            self.auto_clear()
        return xchat.EAT_NONE

    # Handle command/message sends in window
    def on_command(self, word, word_eol):
        if not word or not word[0].startswith("#"):
            if self.channel_current:
                # Add missing channel prefix
                line = self.channel_current[1] + " " + word_eol[0]
                self.buffer.set_input(line)
        elif len(word) > 1:
            context = xchat.find_context(channel=word[0])
            # Send message and restore channel prefix
            if context:
                if word[1].startswith("/"):
                    command = word[1][1:]
                    if len(word) > 2:
                        context.command(command + " " + word_eol[2])
                    else:
                        context.command(command)

                else:
                    context.command("msg " + word_eol[0])
                self.buffer.set_input(word[0] + " ")
            else:
                # No valid target channel
                self._print("Error: Target channel %s not found" % word[0])
        return xchat.EAT_ALL

    # Set option from string
    def set_option(self, key, value):
        if not self.options[key]:
            self._print("Could not set option", "{0} is not a valid option".format(key))
        for t in [bool, str, list]:
            if isinstance(self.options[key], t):
                self.options[key] = t(value)
        self._print("{0} set to {1}".format(key, self.options[key]))
        self.menu_update()

    # def has_channel(self, channel, network=False)

    # Add a channel to group
    def add_channel(self, network, channel, save=True):
        l = self.channels.setdefault(network, [])
        if channel not in l:
            l.append(channel)
        register_group_channel(network, channel, self, save)
        if save:
            self.menu_update()
            self.channels_update()

    # Remove a channel from group
    def remove_channel(self, network, channel):
        self.channels[network].remove(channel)
        if len(self.channels[network]) == 0:
            del self.channels[network]
        unregister_group_channel(network, channel, self)
        self.menu_update()
        self.channels_update()

    def menu_clear(self):
        menu_del("Overwatch/"+self.name)

    def menu_item(self, path, command=None, network="", channel=""):
        path = '"Overwatch/{name}/'+path+'"'
        if command:
            path += ' "'+command+'"'
        cmd("MENU ADD "+path.format(name=self.name, net=network, chan=channel))

    # [re]Build menu
    def menu_update(self):
        self.menu_clear()
        # Main menu
        menu_add("Overwatch/"+self.name)
        self.menu_item("Remove group", "ov group_remove {name}")
        self.menu_item("-")
        for network in self.channels:
            for channel in self.channels[network]:
                self.menu_item("Remove {chan} ({net})", "ov channel_remove {net}??{chan}??{name}", network, channel)
        self.menu_item("-")
        for x in xchat.get_list("channels"):
            if x.type == 2 and (x.network not in self.channels or x.channel not in self.channels[x.network]):
                self.menu_item("Add {chan} ({net})", "ov channel_add {net}??{chan}??{name}", x.network, x.channel)

    # Update all channel lists
    def channels_update(self):
        self.chanrefs.clear()
        self.backrefs.clear()
        self.recent_channels.clear()
        self.auto_clear()
        for network in self.channels:
            for channel in self.channels[network]:
                if xchat.find_context(network, channel):
                    if channel not in self.chanrefs:
                        key = channel
                    else:
                        suffix = network[0]
                        while self.chanrefs[channel][0].startswith(suffix):
                            suffix += network[len(suffix)]
                        key = channel+":"+suffix
                    self.chanrefs[key] = (network, channel)
                    self.backrefs[(network, channel)] = key
        # Cheating
        tmp = sorted(self.chanrefs.keys(), reverse=True)
        for k in tmp:
            self.recent_channels[k] = time() - (50 - len(self.recent_channels))

    # Rename group
    def rename(self, name):
        self.menu_clear()
        unregister_group(self)
        self.buffer.rename(name)
        self.name = name
        register_group(self)
        self.menu_update()
        self.buffer.focus()

    # Remove and clean up group
    def remove(self):
        self.menu_clear()
        unregister_group(self)
        self.buffer.close()


# xchat to python escape map
escapes = {
    "%B": "\002",
    "%C": "\003",
    "%R": "\026",
    "%O": "\017",
    "%U": "\037",
    "%H": "\010",
    "$t": "\t",
    # Replacement indexes are technically offset by one
    # since we place channel in {0}
    "$1": "{1}",
    "$2": "{2}",
    "$3": "{3}",
    "$4": "{4}",
    "$5": "{5}"
}


def decode(text):
    for k, v in escapes.items():
        text = text.replace(k, v)
    return text

# Find desired event strings
chat_events = [
    "Channel Message",
    "Channel Msg Hilight",
    "Channel Action",
    "Channel Action Hilight",
    "Your Message",
    "Your Action",
    "Private Message",
    "Private Action"
]


def compile_strings():
    global events_decoded
    # Decode strings from Text Event settings
    re_move = re.compile(r"(.+)(%C\d*)(\$t)(.*)")  # Message color code needs to be put after tab char
    next = ""
    stringfile = os.path.join(configdir, "pevents.conf")
    assert os.path.exists(stringfile), "Configuration file pevents.conf not found. You may need to use a (any) custom theme for this file to be created"

    with open(stringfile) as f:
        for line in f:
            words = line.split("=", 1)
            if words and words[0] != "\n":
                (key, value) = words
                value = value.strip()
                if key == "event_name" and value in chat_events:
                    next = value
                elif key == "event_text" and next:
                    # Add channel slot to pattern
                    decoded = decode(re_move.sub(r"\1\3\2\4", value))
                    if xchat.get_prefs("text_indent"):
                        events_decoded[next] = decoded.replace("\t", "\t{0}")
                    else:
                        events_decoded[next] = "{0}" + decoded
                    next = ""


def xchat_in_group():
    network = xchat.get_info("network")
    if network in registered_groups:
        return registered_groups[network]
    return False


def dispatch_message(word, word_eol, event):
    network, channel = xchat.get_info("network"), xchat.get_info("channel")
    # Dispatch event to each group registered for this channel
    if network in registered_channels and channel in registered_channels[network]:
        for group in registered_channels[network][channel]:
            # Extract nick and coloring
            if xchat.get_prefs("text_color_nicks"):
                (nick_color, nick) = re_nick.search(word[0]).groups("")
            else:
                nick_color, nick = "", word[0]
            args = (word[1:] + padding)
            group.on_chat_message(network, channel, event, nick, nick_color, args, word, word_eol)
    return xchat.EAT_NONE


def dispatch_key(word, word_eol, userdata):
    group = xchat_in_group()
    if group:
        return group.on_key_press(int(word[0]), int(word[1]))


def dispatch_command(word, word_eol, userdata):
    group = xchat_in_group()
    if group:
        return group.on_command(word, word_eol)


def dispatch_channels_change(word, word_eol, event):
    for x in registered_groups.values():
        x.menu_update()
        x.channels_update()


def command_handler(word, word_eol, userdata):
    if len(word) > 2:
        if word[1] == "channel_add":
            args = word_eol[2].split('??')
            if len(args) == 3:
                if args[2] not in registered_groups:
                    group = channel_group(args[2])
                    group._print("Rename this group with /ov rename NAME")
                else:
                    group = registered_groups[args[2]]
                group.add_channel(args[0], args[1])
        elif word[1] == "channel_remove":
            args = word_eol[2].split('??')
            if len(args) == 3:
                for group in registered_channel_groups(args[0], args[1]):
                    if group.name == args[2]:
                        group.remove_channel(args[0], args[1])
        elif word[1] == "group_add":
            channel_group(word_eol[2])._print("Rename this group with /ov rename NAME")
        elif word[1] == "group_remove":
            if word_eol[2] in registered_groups:
                registered_groups[word_eol[2]].remove()
        elif word[1] == "rename":
            group = xchat_in_group()
            if group:
                group.rename(word_eol[2])
        elif word[1] == "set_internal":
            args = word_eol[2].split('??')
            if len(args) == 3 and args[0] in registered_groups:
                registered_groups.set_option(args[1], args[2])
        elif word[1] == "set":
            group = xchat_in_group()
            if group:
                group.set_option(word[2], word_eol[3])
    if word[1] == "test":
        for x in registered_groups.values():
            print(x.name, jsonify_structure(x.channels))
    return xchat.EAT_ALL


menu_add("Overwatch")
menu_add("Overwatch/Create new group", "ov group_add ++New Group")
menu_add("Overwatch/-")


def load(*args):
    groups_load_from_settings()
    compile_strings()
    for event in chat_events:
        xchat.hook_print(event, dispatch_message, event)

    xchat.hook_print("Key Press", dispatch_key)
    xchat.hook_command("", dispatch_command)

    xchat.hook_command("ov", command_handler)

    for event in ["You Join", "You Kicked", "You Part", "you Part with Reason"]:
        xchat.hook_print(event, dispatch_channels_change, event)

    print(__module_name__, __module_version__, 'loaded')


def unload(*args):
    menu_del("Overwatch")
    print(__module_name__, __module_version__, 'unloaded')


# Defer load until config files stabilize
xchat.hook_timer(100, load)
xchat.hook_unload(unload)
