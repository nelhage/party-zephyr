import jabberbot
import logging
import re
import threading
import signal
import zephyr
import sys
import select
import Queue
import yaml
import os.path
import time

SHUTDOWN = False

JOIN_ALERT = re.compile(r"""^You have joined '([^']+)' with the alias '([^']+)'$""")
CHAT_MESSAGE = re.compile(r"""^\[([^]]+)\]\s*(.*)$""", re.S|re.M)

CONF = yaml.safe_load(open(os.path.join(os.path.dirname(__file__),
                                        'partychat.yml')))
jabber_chats = CONF['chats']
zephyr_classes = dict(map(reversed, jabber_chats.items()))

USER = CONF['creds']['user']
PASS = CONF['creds']['pass']

from_zephyr_q = Queue.Queue()
from_jabber_q = Queue.Queue()

PARTYCHAT_HOST = 'im.partych.at'

class BridgeBot(jabberbot.JabberBot):
    def __init__(self, user, pw):
        super(BridgeBot, self).__init__(user, pw)

#         chandler = logging.StreamHandler()
#         formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
#         chandler.setFormatter(formatter)
#         self.log.addHandler(chandler)
#         self.log.setLevel(logging.DEBUG)

    def chat_to_jid(self, chat):
        return chat + '@' + PARTYCHAT_HOST

    def joined_chat(self, chat):
        self.send(self.chat_to_jid(chat), "/nick z")
        if chat in jabber_chats:
            self.send(self.chat_to_jid(chat),
                      "This chat is now being mirrored to -c %s" %
                      (jabber_chats[chat],))

    def callback_message(self, conn, mess):
        if not mess.getFrom().getDomain() == PARTYCHAT_HOST:
            return
        from_ = str(mess.getFrom())
        chat = from_[:from_.rindex('@')]
        body = mess.getBody()
        logging.debug("JABBER: %s: %s", from_, body)
        m = JOIN_ALERT.search(body)
        if m:
            self.joined_chat(chat)
            return
        m = CHAT_MESSAGE.search(body)
        if m:
            who = m.group(1)
            body = m.group(2)
            from_jabber_q.put((chat, who, body))

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
            self.send(self.chat_to_jid(zephyr_classes[cls]), "[%s] %s" % (sender, msg))

    def on_connect(self):
        for who in jabber_chats.values():
            self.send(self.chat_to_jid(who), '/nick z')

def run_jabber():
    bot = BridgeBot(USER, PASS)
    while not SHUTDOWN:
        try:
            logging.info("Connecting to Jabber...")
            bot.serve_forever(connect_callback = bot.on_connect)
        except IOError, e:
            logging.error("IOError in Jabber thread", exc_info=True)
            time.sleep(60)

def run_zephyr():
    zephyr.init()
    subs = zephyr.Subscriptions()
    logging.info("Subscribing to: " + ','.join(zephyr_classes.keys()))
    for c in zephyr_classes.keys():
        subs.add((c, '*', ''))
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
            body = note.fields[1] if len(note.fields) > 1 else ''
            logging.debug("ZEPHYR: %s/%s[%s]: %s",
                          note.sender, note.cls, note.opcode,
                          body)
            if note.opcode.lower() not in ('auto', 'ping'):
                from_zephyr_q.put((note.cls, note.sender.split('@')[0],
                                   body))
        else:
            select.select([zephyr._z.getFD()], [], [], 1)

def main():
    global SHUTDOWN

    logging.basicConfig(level = logging.DEBUG)

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
