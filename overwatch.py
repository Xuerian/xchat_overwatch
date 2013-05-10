__module_name__ = "overwatch-mode"
__module_version__ = "0.5"
__module_description__ = "Provides digest tabs which can watch and interact with multiple channels"

option_defaults = {
    # Default tab name
    "server_name": "[Overwatch]",
    # Focus tab on load
    "focus_on_load": True,
    # Hide repeated channel names
    "hide_inline_channel": True,
    # Replace repeated channel with
    "inline_channel_prefix": "| ",
    # Shorten repeated nicks
    "truncate_nick_inline": False,
    "truncate_nick_length": 4,
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
}


def opt(key):
    return option_defaults[key]

# TODO: Option saving/changing without editing file
# TODO: Whitelist/Blacklist filters for overwatches
# TODO: Handle networks properly/separately
# TODO: Improve tab completion (It doesn't feel natural sometimes)
# TODO: Reduce overlaps in channel coloring? Might not be worth it due to low optimal channel number.
# This conflicts with hexchat's color = len(nick) % len(colors)
# TODO: Shortcuts (Reply to last hilight, send to last channel, clear to channel name)

import xchat
from time import time
import re
from collections import deque
import os

MOD_SHIFT = 1
MOD_CTRL = 4
MOD_ALT = 8

SHIFT = 0xFFE1
TAB = 0xFF09
LEFT_TAB = 0xFE20
ENTER = 0xFF0D
BACKSPACE = 0xFF08

events_decoded = {}  # Event strings decoded with channel marker added

overwatches = {}  # Shouldn't double up
greedy_overwatch = None
channel_map = {}
padding = ["", "", ""]  # Prevents format from complaining on short events

re_nick = re.compile(r"^(\x03[\d]+)?(.+?)$")

channel_pattern_visible = "\003{1}\010(\010{0}\010)\010\017 "
channel_pattern_hidden = "\003{1}\010({0})\010*\017".replace("*", opt("inline_channel_prefix"))


class xbuffer:
    initial_load = False

    def __init__(self, name, is_server=True):
        self.name = name
        self.context = xchat.find_context(channel=name)
        if not self.context:
            self.initial_load = True
            if is_server:
                xchat.command("newserver -noconnect "+name)
            else:
                xchat.command("query "+name)
            self.context = xchat.find_context(channel=name)

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


class overwatch:
    focus_on_load = opt("focus_on_load")  # Opt
    is_greedy = True  # Opt
    greedy_blacklist = []  # Opt
    current_channel = ""  # Latest event source
    last_channel = ""  # Previous event source
    last_nick = ""
    last_action = time()
    last_target = ""
    recent_channels = {}  # For building auto lists
    recent_users = {}  # For building auto lists
    channels = []  # Channels owned by this overwatch
    auto_type = 0  # Type of autocomplete in progress (1/channel 2/nick)
    auto_list = deque()  # Current autocomplete list
    auto_first = True  # First tabcomplete. TODO: auto_active better?

    def __init__(self, name=opt("server_name")):
        global overwatches, greedy_overwatch
        self.buffer = xbuffer(name)
        if self.buffer.initial_load and self.focus_on_load:
            self.buffer.focus()
        overwatches[name] = self
        if self.is_greedy:
            greedy_overwatch = self

    def echo(self, *args):
        self.buffer.context.prnt(', '.join(str(i) for i in args))

    def err(self, *args):
        self.echo("Overwatch %s error" % self.buffer.name, *args)

    def channel_color(self, channel):
        colors = opt("channel_colors")
        if not opt("colored_channel_names"):
            return colors[0]
        return colors[len(channel) % len(colors)]

    def auto_list_channels(self, search=""):
        self.auto_type = 1
        # Recent channels
        recent = [k for k in self.recent_channels if k.startswith(search)]
        recent.sort(reverse=True, key=lambda k: self.recent_channels[k])
        # Rest of channels
        rest = [k for k in self.channels if k not in recent and k.startswith(search)]
        rest.sort()
        self.auto_list.extend(recent + rest)

    def auto_list_users(self, channel, search=""):
        self.auto_type = 2
        p = re.compile(re.escape(search), re.I)
        # Recently seen nicks from this channel
        recent = [k for k, v in self.recent_users.items() if bool(p.match(k)) and v[0] == channel]
        recent.sort(reverse=True, key=lambda k: self.recent_users[k][1])
        # Get rest of nicks from target channel
        channel_context = xchat.find_context(channel=channel)
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

    def pressed_tab(self, modifiers):
        text = self.buffer.get_input().strip()
        word = text.split(" ", 1)
        num = len(word)
        if num == 2:
            (line, nick) = text.rsplit(" ", 1)

        # Generate autocomplete list
        if self.auto_first:
            if num == 1:
                # Tab to next channel
                if word[0] in self.channels:
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
                self.auto_list_users(word[0], nick)

        if self.auto_list:
            # Rotate to next
            if not self.auto_first:
                # Tab
                if modifiers == 0:
                    mod = -1
                # Shift-tab
                elif modifiers == 1:
                    mod = 1
                self.auto_list_rotate(mod, self.auto_type == 1 and word[0] or nick)
            # Complete channel
            if self.auto_type == 1:
                self.buffer.set_input(self.auto_list[0] + " " + (num > 1 and word[1] or ""))
            # Complete nick
            else:
                self.buffer.set_input("%s %s%s " % (line, self.auto_list[0], xchat.get_prefs("completion_suffix")))
            self.auto_first = False

        return xchat.EAT_ALL

    def pressed_enter(self, modifiers):
        if self.current_channel and not self.buffer.get_input():
            self.pressed_tab(0)
            return xchat.EAT_ALL
        return xchat.EAT_NONE

    def pressed_any(self, key, modifiers, word):
        # Clear auto-complete if not shift-tabbing
        if key != SHIFT:
            self.last_action = time()
            self.auto_clear()

        if key == BACKSPACE:
            # Reset to target
            if modifiers == MOD_ALT:
                self.buffer.set_input(self.last_target + " ")
                return xchat.EAT_ALL

        return xchat.EAT_NONE

    def on_event(self, channel, event, word, word_eol):
        # Separate nick and color
        if xchat.get_prefs("text_color_nicks"):
            (nick_color, nick) = re_nick.search(word[0]).groups("")
        else:
            nick_color, nick = "", word[0]
        # Inline channel names
        hide_channel = opt("hide_inline_channel")
        if hide_channel and channel == self.current_channel:
            channel_text = channel_pattern_hidden.format(channel, self.channel_color(channel))
        else:
            channel_text = channel_pattern_visible.format(channel, self.channel_color(channel))
        # Truncated nick
        truncate_length = opt("truncate_nick_length")
        if opt("truncate_nick_inline") and nick == self.last_nick and ((hide_channel and self.last_channel == self.current_channel) or (not hide_channel and self.current_channel == channel)) and len(nick) > truncate_length:
            nick_text = "{0}{1}\010{2}\010".format(nick_color, nick[0:truncate_length], nick[truncate_length:])
        else:
            nick_text = word[0]
        # Add to buffer
        self.buffer.context.prnt(events_decoded[event].format(channel_text, nick_text, *(word[1:] + padding)))
        # Update recents
        self.recent_channels[channel] = now = time()
        self.recent_users[nick] = (channel, time())
        # Update prompt
        if opt("auto_target"):
            line = self.buffer.get_input().strip()
            if now - self.last_action > opt("auto_target_delay") or (not line and now - self.last_action > opt("auto_target_delay_empty")):
                if not line or (line in self.channels and line != channel):
                    action = opt("auto_target_action")
                    if action == "clear":
                        self.buffer.set_input("")
                    elif action == "update":
                        self.buffer.set_input(channel + " ")
                    self.auto_clear()
        self.last_channel = self.current_channel
        self.current_channel = channel
        self.last_nick = nick

    def on_send(self, word, word_eol):
        if not word or not word[0].startswith("#"):
            if self.current_channel:
                # Add missing channel prefix
                line = self.current_channel + " " + word_eol[0]
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

                    self.echo(word[1], word[1][1:], word_eol, word)
                else:
                    context.command("msg " + word_eol[0])
                    self.last_target = word[0]
                self.buffer.set_input(word[0] + " ")
            else:
                # No valid target channel
                self.err("Target channel %s not found" % word[0])
        return xchat.EAT_ALL

    def watch_channel(self, channel):
        global channel_map
        if channel.startswith("#"):
            if not channel in self.channels:
                self.channels.append(channel)
                channel_map[channel] = self

    def is_focused(self):
        return xchat.get_info("channel") == self.name


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
    "Channel Action"
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

    configdir = xchat.get_info("configdir")
    if not configdir:  # For xchat
        configdir = xchat.get_info("xchatdir")
    stringfile = configdir + "/pevents.conf"

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


# Set up chat callbacks
# TODO: Handle queries and multiple channels of the same name properly
# TODO: Use server-channel instead of channel.
def chat_callback(event, word, word_eol):
    channel = xchat.get_info("channel")
    if not channel in channel_map and greedy_overwatch:
        greedy_overwatch.watch_channel(channel)
    if channel in channel_map and channel_map[channel]:
        return channel_map[channel].on_event(channel, event, word, word_eol)
    return xchat.EAT_NONE


def clone_chat_event(event):
    def clone(word, word_eol, data):
        chat_callback(event, word, word_eol)
    xchat.hook_print(event, clone)


# Hook keys
def key_press(word, word_eol, data):
    focus = xchat.get_info("channel")
    if focus in overwatches:
        key, modifiers = int(word[0]), int(word[1])
        if key == ENTER:
            return overwatches[focus].pressed_enter(modifiers)
        elif key == TAB or key == LEFT_TAB:
            return overwatches[focus].pressed_tab(modifiers)
        else:
            return overwatches[focus].pressed_any(key, modifiers, word)
    return xchat.EAT_NONE


# Hook sending messages
def on_send(word, word_eol, data):
    focus = xchat.get_info("channel")
    if focus in overwatches:
        return overwatches[focus].on_send(word, word_eol)
    return xchat.EAT_NONE


main = None


# Defer load until config files stabilize
def load(*args):
    global main
    compile_strings()
    for x in chat_events:
        clone_chat_event(x)

    main = overwatch(opt("server_name"))

    xchat.hook_print("Key Press", key_press)
    xchat.hook_command("", on_send)

    if greedy_overwatch:
        for x in xchat.get_list("channels"):
            greedy_overwatch.watch_channel(x.channel)

    print(__module_name__, __module_version__, main.buffer.initial_load and 'loaded' or 'reloaded')

xchat.hook_timer(100, load)


def unload(*args):
    print(__module_name__, __module_version__, 'unloaded')


# TODO: Provide separate buffer for debug, also split into separate module to catch script errors.
def debug(*args):
    main.echo(*args)

xchat.hook_unload(unload)
