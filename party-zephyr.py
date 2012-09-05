import jabberbot
import logging
import re
import threading
import signal
import zephyr
import sys

USER = 'partychat@nelhage.com'
PASS = '7d6sqHKdDlBv'

SHUTDOWN = False

JOIN_ALERT = re.compile(r"""^You have joined '([^']+)' with the alias '([^']+)'$""")
CHAT_MESSAGE = re.compile(r"""^\[([^]]+)\]\s*(.*)$""", re.S|re.M)

CHAT_MAP = [('nelhage-test', 'partychat-test')]

jabber_chats = dict(CHAT_MAP)
zephyr_classes = dict(reversed(c) for c in CHAT_MAP)

class BridgeBot(jabberbot.JabberBot):
    def __init__(self, user, pw):
        super(BridgeBot, self).__init__(user, pw)

#         chandler = logging.StreamHandler()
#         formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
#         chandler.setFormatter(formatter)
#         self.log.addHandler(chandler)
#         self.log.setLevel(logging.DEBUG)

    def callback_message(self, conn, mess):
        if not str(mess.getFrom()).endswith('@im.partych.at'):
            return
        from_ = str(mess.getFrom())
        chat = from_[:from_.rindex('@')]
        body = mess.getBody()
        m = JOIN_ALERT.search(body)
        if m:
            self.send(mess.getFrom(), "Joining the chat...", mess)
            return
        m = CHAT_MESSAGE.search(body)
        if m:
            who = m.group(1)
            body = m.group(2)
            print "CHAT: [%s] %s" % (who, body,)
        else:
            print "[%s] %s" % (mess.getFrom(), mess.getBody())

    def callback_presence(self, conn, presence):
        jid, type_, show, status = presence.getFrom(), \
                presence.getType(), presence.getShow(), \
                presence.getStatus()
        if type_ == 'subscribe':
            self.roster.Authorize(jid)
        else:
            super(BridgeBot, self).callback_presence(conn, presence)

def run_jabber():
    bot = BridgeBot(USER, PASS)
    bot.serve_forever()

def run_zephyr():
    zephyr.init()
    subs = zephyr.Subscriptions()
    for c in CHAT_MAP:
        subs.add((c[1], '*', ''))
    while not SHUTDOWN:
        note = zephyr.receive(True)
        print note

def main():
    global SHUTDOWN

    jabber_thread = threading.Thread(target = run_jabber)
    zephyr_thread = threading.Thread(target = run_zephyr)

    threads = [jabber_thread, zephyr_thread]
    for t in threads: t.start()

    while True:
        try:
            signal.pause()
        except KeyboardInterrupt:
            break
    SHUTDOWN = True

    for t in threads: t.join()

    return 0

if __name__ == '__main__':
    sys.exit(main())
