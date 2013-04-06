__module_name__ = "overwatch-mode"
__module_version__ = "0.2"
__module_description__ = "Provides meta-tabs which can watch and interact with multiple channels"

__server_name__ = ">Overwatch"
__focus_on_start__ = True

import xchat
from time import time
import re
from collections import deque


def error(msg):
    our_context.prnt("\012Overwatch Error:\017 " + msg)


def get_input():
    return our_context.get_info("inputbox")


def set_input(line, move_cursor=True):
    our_context.command("settext " + line)
    if move_cursor:
        set_input_pos(len(line))


def set_input_pos(pos):
    our_context.command("setcursor " + str(pos))


recent_events = deque([], 25)
recent_users = {}
recent_channels = {}

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
events_decoded = {}  # Event strings decoded with channel added
events_inline = {}  # Decoded strings with channel hidden
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


# Decode strings from Text Event settings
re_move = re.compile(r"(.+)(%C\d*)(\$t)(.*)")  # Message color code needs to be put after tab char
next = ""
with open("config/pevents.conf") as f:
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

# Acquire our context
our_context = xchat.find_context(channel=__server_name__)
if not our_context:
    xchat.command("newserver -noconnect "+__server_name__)
    our_context = xchat.find_context(channel=__server_name__)


def is_focused():
    return xchat.get_info("channel") == __server_name__


# Set up chat callbacks
last_channel = ""
last_action = time()
padding = ["", "", ""]  # Prevents format from complaining


def chat_callback(event, word, word_eol):
    global last_channel
    if not is_focused():
        channel = xchat.get_info("channel")
       # Add event to overwatch
        which_list = channel == last_channel and events_inline or events_decoded
        our_context.prnt(which_list[event].format(channel, *(word + padding)))
        # Update data
        now = recent_channels[channel] = recent_users[word[0]] = time()
        # Update prompt
        if now - last_action > 5:
            line = get_input()
            if not line or line == last_channel + " ":
                set_input(channel + " ")
        last_channel = channel
    return xchat.EAT_NONE


def clone_chat_event(event):
    def clone(word, word_eol, data):
        chat_callback(event, word, word_eol)
    xchat.hook_print(event, clone)


map(clone_chat_event, chat_events)


# Handle key presses
SHIFT = 1
CTRL = 4
ALT = 8

TAB = 0xFF09
LEFT_TAB = 0xFE20
ENTER = 0xFF0D


def on_tab(key, modifier):
    print "tab", key, modifier
    return xchat.EAT_ALL


# def on_enter(modifier):
#     print recent_channels, recent_users
#     line = xchat.get_info("inputbox")
#     if not line.startswith("/") or line.startswith("/em"):
#         return xchat.EAT_ALL
#     return xchat.EAT_NONE


# Hook keys
def key_press(word, word_eol, data):
    global last_action
    if is_focused():
        key, modifiers = int(word[0]), int(word[1])
        if key == TAB or key == LEFT_TAB:
            if not modifiers & (CTRL | ALT | SHIFT):
                return on_tab(key, modifiers)
        elif key == ENTER:
            if not xchat.get_info("inputbox") and last_channel:
                set_input(last_channel + " ")
                return xchat.EAT_ALL
        # else:
        #     print word
        #     return on_enter(modifiers)
        # word[2] contains keys with names
        last_action = time()

    return xchat.EAT_NONE


# Hook sending messages
def on_send(word, word_eol, data):
    if is_focused():
        # No target channel
        if not word or not word[0].startswith("#"):
            line = last_channel + " " + word_eol[0]
            set_input(line)
            set_input_pos(len(line))
        elif word:
            # Found target channel
            context = xchat.find_context(channel=word[0])
            if context:
                context.command("msg " + word_eol[0])
                set_input(word[0] + " ")
            # Invalid target channel
            else:
                error("Target channel %s not found" % word[0])
                set_input(word_eol[0])
        return xchat.EAT_ALL
    return xchat.EAT_NONE

xchat.hook_print("Key Press", key_press)
xchat.hook_command("", on_send)

if __focus_on_start__:
    our_context.command("gui focus")

print __module_name__, __module_version__, 'loaded'
