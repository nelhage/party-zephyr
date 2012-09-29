This bot implements a simple bridge between
[partychat](http://partychapp.appspot.com/) chat rooms and
[Zephyr](http://zephyr.1ts.org/) classes.

It depends on [PyZephyr](https://github.com/ebroder/python-zephyr) and
[python-jabberbot](http://thp.io/2007/python-jabberbot/).

You'll need to configure it using a partychat.yml file, looking
something like:

    chats:
      ZEPHYR-CLASS-1: PARTYCHAT-1
      ZEPHYR-CLASS-2: PARTYCHAT-2
    creds:
      user: partychat@nelhage.com
      pass: '<password>'

And then invite the bot to the partychat chats.
