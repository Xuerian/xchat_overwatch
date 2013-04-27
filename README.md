xchat_overwatch
=============

Provides buffers which watch and interact with multiple channels

![Overwatch](https://github.com/Xuerian/xchat_overwatch/raw/master/overwatch_screenshot.png)

![Overwatch](https://github.com/Xuerian/xchat_overwatch/raw/master/overwatch_screenshot_random_channels.png)


Settings are available at the top of the script:

* __server_name__ is the name of the server tab created
* __focus_on_load__ causes the tab to be focused immediately when loaded
* __hide_inline_channel__ replaces consecutive channel names with..
* __inline_prefix__ which defaults to "| "
* __hide_inline_nick__ replaces consecutive nicks with..
* __inline_nick_Prefix__ which defaults to "
* __colored_channel_names__ causes channel names to be colored similarly to "Colored nick names" in heXchat
* __channel_colors__ provides a list of possible channel colors, the first of which is used if random colors is turned off.

Complete features:

* Monitor multiple channels in a single buffer
* Most-recent-first channel and nick tab-completion

Incomplete:

* Create and manage multiple overwatches with different channel lists
* Target channel based on recent nickname autocomplete
* Provide secondary tabs to summarize hilights
* Options menu to manage overwatches

Usage:

* Autocomplete channels or nicks with tab/shift-tab
* Tab/enter without any channel will add most recent

Issues:

* Channel commands/Actions are not reliably caught or passed on
* Multiple channels with the same name will currently break
* Can get hard to track with lots of busy channels (Helped by random colors)
* Channel tab completion is still a bit derp
* While modular, the UI/commands to make multiple and manage filter lists for overwatches is not done
