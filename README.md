xchat_overwatch
=============

Provides buffers which watch and interact with multiple channels

![Overwatch](https://github.com/Xuerian/xchat_overwatch/raw/master/overwatch_screenshot.png)

![Overwatch](https://github.com/Xuerian/xchat_overwatch/raw/master/overwatch_screenshot_random_channels.png)


Settings are available at the top of the script:

* __server_name__ is the name of the server tab created
* __focus_on_load__ causes the tab to be focused immediately when loaded
* __hide_inline_channel__ replaces consecutive channel names with..
* __inline_channel_prefix__
* __truncate_nick_inline__ shortens consecutive nicks to..
* __truncate_nick_length__
* __colored_channel_names__ causes channel names to be colored similarly to "Colored nick names" in heXchat
* __channel_colors__ provides a list of possible channel colors, the first of which is used if random colors is turned off.
* __auto_target__ enables updating the channel target based on last action time
* __auto_target_action__ is either "clear" to remove the outdated target, or "update" to change it to the new channel
* __auto_target_delay__ seconds, unless there is no current target, in which case after..
* __auto_target_delay_empty__ seconds

Complete features:

* Monitor multiple channels in a single buffer
* Most-recent-first channel and nick tab-completion


Incomplete:

* Create and manage multiple overwatches with different channel lists
* Target channel based on recent nickname autocomplete
* Provide secondary tabs to summarize hilights
* Options menu to manage overwatches
* Better shortcuts

Shortcuts:

* __tab__ and __shift-tab__
 * With less than two words, tab-completes channels
 * With more than one word, tab-completes nicks
* __alt-backspace__ clears entry and sets target to the last channel you sent to

Issues:

* Channel commands/Actions are not reliably caught or passed on
* Multiple channels with the same name will currently break
* Can get hard to track with lots of busy channels (Helped by random colors)
* Channel tab completion is still a bit derp
* While modular, the UI/commands to make multiple and manage filter lists for overwatches is not done
