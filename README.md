xchat_overwatch
=============

Provides buffers which watch and interact with multiple channels

![Overwatch](https://github.com/Xuerian/xchat_overwatch/raw/master/overwatch_screenshot.png)

Settings are available at the top of the script:

* __server_name__ is the name of the server tab created
* __focus_on_load__ causes the tab to be focused immediately when loaded

Complete features:

* Watch all channels in one window
* Most-recent channel and nick autocomplete
* Modular structure

Incomplete:

* Update channel target based on nickname autocomplete
* Define multiple overwatches with channel include or exclude lists
* Provide secondary tabs to list hilights
* Options menu to manage overwatches

Usage:

* Tab or enter with empty entry will autocomplete most recent channel
* Tab with partial channel will complete by recent channels
* Tab with nicks will complete by recent nick

Issues:

* Actions are not reliably caught or passed on
* Multiple channels with the same name will currently break
* Can get hard to track with lots of busy channels
* While modular, the UI/commands to make multiple and manage filter lists for overwatches is not done
