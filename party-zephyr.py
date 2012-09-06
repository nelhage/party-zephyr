import jabberbot
import logging
import re
import threading
import signal
import zephyr
import sys
import select
import Queue

USER = 'partychat@nelhage.com'
PASS = '7d6sqHKdDlBv'

SHUTDOWN = False

JOIN_ALERT = re.compile(r"""^You have joined '([^']+)' with the alias '([^']+)'$""")
CHAT_MESSAGE = re.compile(r"""^\[([^]]+)\]\s*(.*)$""", re.S|re.M)

CHAT_MAP = [('nelhage-test', 'partychat-test'),
            ('dfrpg', 'dfrpg'),
            # ('nothing.reasonable.happens.here', 'nothing-reasonable-happens-here')
            ]

jabber_chats = dict(CHAT_MAP)
zephyr_classes = dict(reversed(c) for c in CHAT_MAP)

from_zephyr_q = Queue.Queue()
from_jabber_q = Queue.Queue()

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
        print "JABBER: %s: %s" % (from_, body)
        m = JOIN_ALERT.search(body)
        if m:
            self.send(mess.getFrom(), "/nick z", mess)
            self.send(mess.getFrom(), "Joining the chat...", mess)
            return
        m = CHAT_MESSAGE.search(body)
        if m:
            who = m.group(1)
            body = m.group(2)
            from_jabber_q.put((chat, who, body))
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

    def idle_proc(self):
        super(BridgeBot, self).idle_proc()
        if SHUTDOWN:
            self.quit()
        while True:
            try:
                m = from_zephyr_q.get(False)
            except Queue.Empty:
                return
            (cls, sender, msg) = m
            if cls not in zephyr_classes: return
            self.send(zephyr_classes[cls] + '@im.partych.at', "[%s] %s" % (sender, msg))

    def on_connect(self):
        for who in jabber_chats.values():
            self.send(who + '@im.partych.at', '/nick z')

def run_jabber():
    bot = BridgeBot(USER, PASS)
    bot.serve_forever(connect_callback = bot.on_connect)

def run_zephyr():
    zephyr.init()
    subs = zephyr.Subscriptions()
    for c in CHAT_MAP:
        subs.add((c[1], '*', ''))
    while not SHUTDOWN:
        while True:
            try:
                m = from_jabber_q.get(False)
            except Queue.Empty:
                break
            (src, sender, msg) = m
            if src not in jabber_chats:
                continue
            note = zephyr.ZNotice()
            note.fields = [src, msg]
            note.sender = sender
            note.auth   = False
            note.cls    = jabber_chats[src]
            note.instance = ''
            note.opcode = 'auto'
            note.send()

        note = zephyr.receive(False)
        if note:
            print "ZEPHYR: %s[%s]: %s" % (note.sender, note.opcode, note.fields[1] if len(note.fields) > 1 else '')
            if note.opcode.lower() not in ('auto', 'ping'):
                from_zephyr_q.put((note.cls, note.sender.split('@')[0], note.fields[1] if len(note.fields) > 1 else ''))
        else:
            select.select([zephyr._z.getFD()], [], [], 1)

def main():
    global SHUTDOWN

    jabber_thread = threading.Thread(target = run_jabber)
    zephyr_thread = threading.Thread(target = run_zephyr)

    threads = [jabber_thread, zephyr_thread]
    for t in threads:
        t.start()

    while True:
        try:
            signal.pause()
        except KeyboardInterrupt:
            break
    SHUTDOWN = True

    for t in threads:
        t.join()

    return 0

if __name__ == '__main__':
    sys.exit(main())
