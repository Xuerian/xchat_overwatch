__module_name__ = "overwatch-mode"
__module_version__ = "0.3"
__module_description__ = "Provides meta-tabs which can watch and interact with multiple channels"

__server_name__ = "[Overwatch]"
__focus_on_load__ = True

import xchat
from time import time
import re
from collections import deque

SHIFT = 1
CTRL = 4
ALT = 8

TAB = 0xFF09
LEFT_TAB = 0xFE20
ENTER = 0xFF0D

events_decoded = {}  # Event strings decoded with channel added
events_inline = {}  # Decoded strings with channel hidden

overwatches = {}  # Shouldn't double up
greedy_overwatch = None
channel_map = {}
padding = ["", "", ""]  # Prevents format from complaining on short events


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
    focus_on_load = __focus_on_load__  # Opt
    is_greedy = True  # Opt
    greedy_blacklist = []  # Opt
    last_channel = ""
    last_action = time()
    recent_channels = {}
    recent_users = {}
    channels = []
    auto_type = 0
    auto_list = deque()
    auto_first = True

    def __init__(self, name=__server_name__):
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

    def auto_clear(self):
        if not self.auto_first:
            self.auto_first = True
            self.auto_list.clear()
            self.auto_type = None

    def pressed_tab(self, modifiers):
        text = self.buffer.get_input().strip()
        word = text.split(" ", 1)
        num = len(word)

        if self.auto_first:
            if num == 1:
                # Tab to next channel
                if word[0] in self.channels:
                    self.auto_list_channels()
                # Complete channel name
                elif word[0] and not word[0].startswith("#"):
                    self.auto_list_channels("#" + word[0])
                # Search partial chanel
                else:
                    self.auto_list_channels(word[0])
            # Search nick
            elif num == 2:
                (line, nick) = text.rsplit(" ", 1)
                self.auto_list_users(word[0], nick)
        elif self.auto_list:
            if modifiers == 0:
                self.auto_list.rotate(-1)
            elif modifiers == 1:
                self.auto_list.rotate(1)


        if self.auto_list:
            # Complete channel
            if self.auto_type == 1:
                self.buffer.set_input(self.auto_list[0] + " " + (num > 1 and word[1] or ""))
            # Complete nick
            else:
                line = text.rsplit(" ", 1)[0]
                self.buffer.set_input("%s %s%s " % (line, self.auto_list[0], xchat.get_prefs("completion_suffix")))
            self.auto_first = False

        return xchat.EAT_ALL

    def pressed_enter(self, modifiers):
        if self.last_channel and not self.buffer.get_input():
            self.buffer.set_input(self.last_channel + " ")
            return xchat.EAT_ALL
        return xchat.EAT_NONE

    def pressed_any(self, key, modifiers, word):
        self.last_action = time()
        self.auto_clear()
        return xchat.EAT_NONE

    def on_event(self, channel, event, word, word_eol):
        # Add to buffer
        which_list = (channel == self.last_channel and events_inline or events_decoded)
        self.echo(which_list[event].format(channel, *(word + padding)))
        # Update recents
        self.recent_channels[channel] = now = time()
        self.recent_users[word[0]] = (channel, time())
        # Update prompt
        if now - self.last_action > 5:
            line = self.buffer.get_input()
            if not line or line == self.last_channel + " ":
                self.buffer.set_input(channel + " ")
                self.auto_clear()
        self.last_channel = channel

    def on_send(self, word, word_eol):
        if not word or not word[0].startswith("#"):
            if self.last_channel:
                # Add missing channel prefix
                line = self.last_channel + " " + word_eol[0]
                self.buffer.set_input(line)
        elif word:
            context = xchat.find_context(channel=word[0])
            # Send message and restore channel prefix
            if context:
                context.command("msg " + word_eol[0])
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


class recent_list:
    def __init__(self):
        self.dict = {}

    def add(self, k):
        self.dict[k] = time()

    def has(self, key):
        return key in self.dict.keys()

    def list(self, search=""):
        if not self.dict:
            return []
        if search:
            return sorted([key for key in self.dict if key.startswith(search)], key=lambda k: self.dict[k])
        return sorted(self.dict.keys(), key=lambda k: self.dict[k])


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
    global events_decoded, events_inline
    # Decode strings from Text Event settings
    re_move = re.compile(r"(.+)(%C\d*)(\$t)(.*)")  # Message color code needs to be put after tab char
    next = ""
    with open(xchat.get_info("xchatdir") + "/pevents.conf") as f:
        for line in f:
            words = line.split("=", 1)
            if words and words[0] != "\n":
                (key, value) = words
                value = value.strip()
                if key == "event_name" and value in chat_events:
                    next = value
                elif key == "event_text" and next:
                    decoded = decode(re_move.sub(r"\1\3\2\4", value))
                    events_decoded[next] = decoded.replace("\t", "\t\0036\010(\010{0}\010)\010\017 ")
                    events_inline[next] = decoded.replace("\t", "\t\010({0})\010 ")
                    next = ""


# Set up chat callbacks
def chat_callback(event, word, word_eol):
    global last_channel
    channel = xchat.get_info("channel")
    if channel in channel_map and channel_map[channel]:
        return channel_map[channel].on_event(channel, event, word, word_eol)
    elif greedy_overwatch:
        greedy_overwatch.watch_channel(channel)
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
# not modifiers & (CTRL | ALT | SHIFT)
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
    map(clone_chat_event, chat_events)

    main = overwatch(__server_name__)

    xchat.hook_print("Key Press", key_press)
    xchat.hook_command("", on_send)

    if greedy_overwatch:
        for x in xchat.get_list("channels"):
            greedy_overwatch.watch_channel(x.channel)

    main.echo(__module_name__, __module_version__, main.buffer.initial_load and 'loaded' or 'reloaded')

xchat.hook_timer(100, load)
