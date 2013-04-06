__module_name__ = "Channel Monitor"
__module_version__ = "1.0"
__module_description__ = "Multi-channel message digest"

__tab_name__ = "*Monitor"

import xchat

# Decode Text Event strings into escaped python format strings
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
pevents = {}
events = ["Channel Message",
          "Channel Msg Hilight",
          "Channel Action"
          "Channel Action Hilight",
          "Your Message",
          "Your Action"]

next = ""
with open("config/pevents.conf") as f:
    for line in f:
        words = line.split("=", 1)
        if words and words[0] != "\n":
            (key, value) = words
            value = value.strip()
            if key == "event_name" and value in events:
                next = value
            elif key == "event_text" and next:
                pevents[next] = value
                next = ""

# Decode and modify event strings
for k in pevents.keys():
    # pevents[k] = "\0037{0}\003 "+decode(pevents[k])
    pevents[k] = decode(pevents[k]).replace("\t", "\t\0036{0}\003\t")

# Acquire our context
our_context = xchat.find_context(channel=__tab_name__)
if not our_context:
    xchat.command("newserver -noconnect "+__tab_name__)
    our_context = xchat.find_context(channel=__tab_name__)


# Set up callbacks
def callback(event, word, eol):
    channel = xchat.get_info("channel")
    our_context.set()
    if channel != __tab_name__:
        temp = [channel] + word + ["", "", ""]
        our_context.prnt(pevents[event].format(*temp))
    return xchat.EAT_NONE


def clone_event(event):
    def clone(word, eol, data):
        callback(event, word, eol)
    xchat.hook_print(event, clone)


map(clone_event, events)


xchat.prnt(__module_name__ + ' version ' + __module_version__ + ' loaded.')
