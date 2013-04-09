xchat_overwatch
=============

Provides buffers which watch and interact with multiple channels

![Overwatch](https://github.com/Xuerian/xchat_overwatch/raw/master/overwatch_screenshot.png)

Settings are available at the top of the script:

* __server_name__ is the name of the server tab created
* __focus_on_load__ causes the tab to be focused immediately when loaded

Complete features:

* Monitor multiple channels in a single buffer
* Most-recent-first channel and nick tab-completion

Incomplete:

* Create and manage multiple overwatches with different channel lists
* Target channel based on recent nickname autocomplete
* Provide secondary tabs to list hilights
* Options menu to manage overwatches

Usage:

* Autocomplete channels or nicks with tab/shift-tab
* Tab/enter without any channel will add most recent

Issues:

* Channel commands/Actions are not reliably caught or passed on
* Multiple channels with the same name will currently break
* Can get hard to track with lots of busy channels
* While modular, the UI/commands to make multiple and manage filter lists for overwatches is not done
