#!/usr/bin/env python3
"""
============================================================
  PROJECT 2: Real-Time Chat Application
  Premium Flask Web UI  ·  Discord-style dark glassmorphic
============================================================
  Default:       python 2_chat_app.py          → Flask web UI on :5005
  Socket server: python 2_chat_app.py --server
  Socket client: python 2_chat_app.py --client
  Demo mode:     python 2_chat_app.py --demo
============================================================
"""

import socket
import threading
import json
import datetime
import sys
import time
import random
import hashlib
import webbrowser
from collections import defaultdict

# ── Flask import ──────────────────────────────────────────────
from flask import Flask, request, jsonify, render_template_string


# ── Shared helpers ────────────────────────────────────────────

def timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S")


def make_packet(ptype, **kwargs):
    kwargs['type'] = ptype
    kwargs['ts']   = timestamp()
    return json.dumps(kwargs).encode() + b'\n'


def parse_packet(raw: bytes):
    try:
        return json.loads(raw.decode().strip())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


# ── User Profile ──────────────────────────────────────────────

class UserProfile:
    AVATARS = ["🦊", "🐼", "🦁", "🐯", "🦉", "🐸", "🐺", "🦋",
               "🐙", "🦄", "🦅", "🐬"]

    def __init__(self, username: str, password: str = ""):
        self.username  = username
        self.avatar    = random.choice(self.AVATARS)
        self.joined_at = datetime.datetime.now()
        self.pw_hash   = hashlib.sha256(password.encode()).hexdigest() if password else ""
        self.status    = "online"
        self.msg_count = 0

    def verify(self, password: str) -> bool:
        return self.pw_hash == hashlib.sha256(password.encode()).hexdigest()

    def info(self) -> dict:
        return {
            "username":  self.username,
            "avatar":    self.avatar,
            "joined_at": self.joined_at.strftime("%Y-%m-%d %H:%M"),
            "status":    self.status,
            "msg_count": self.msg_count,
        }

    def __str__(self):
        return f"{self.avatar} {self.username} [{self.status}]"


# ── Chat Room ─────────────────────────────────────────────────

class ChatRoom:
    def __init__(self, name: str, owner: str, is_private: bool = False):
        self.name       = name
        self.owner      = owner
        self.is_private = is_private
        self.members    = {owner}
        self.history    = []          # list of (ts, user, msg)
        self.created_at = datetime.datetime.now()

    def add_message(self, username: str, message: str):
        entry = (timestamp(), username, message)
        self.history.append(entry)
        if len(self.history) > 200:
            self.history = self.history[-200:]

    def get_recent(self, n: int = 50):
        return self.history[-n:]

    def info(self) -> dict:
        return {
            "name":       self.name,
            "owner":      self.owner,
            "members":    list(self.members),
            "is_private": self.is_private,
            "msg_count":  len(self.history),
        }


# ── Chat Server (original socket-based) ──────────────────────

class ChatServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self.host    = host
        self.port    = port
        self.users   : dict[str, UserProfile]         = {}
        self.clients : dict[socket.socket, str]       = {}
        self.rooms   : dict[str, ChatRoom]            = {}
        self.lock    = threading.Lock()
        self._create_room("general", "system")
        self._create_room("random",  "system")
        self._running = False

    def _create_room(self, name: str, owner: str, private: bool = False):
        if name not in self.rooms:
            self.rooms[name] = ChatRoom(name, owner, private)

    def _send(self, sock: socket.socket, ptype: str, **kwargs):
        try:
            sock.sendall(make_packet(ptype, **kwargs))
        except Exception:
            pass

    def _broadcast_room(self, room_name: str, ptype: str, exclude=None, **kwargs):
        with self.lock:
            room = self.rooms.get(room_name)
            if not room:
                return
            targets = [s for s, u in self.clients.items()
                       if u in room.members and s is not exclude]
        for sock in targets:
            self._send(sock, ptype, **kwargs)

    def _broadcast_all(self, ptype: str, exclude=None, **kwargs):
        with self.lock:
            targets = [s for s in self.clients if s is not exclude]
        for sock in targets:
            self._send(sock, ptype, **kwargs)

    def _handle_client(self, sock: socket.socket, addr):
        buf = b""
        username = None
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    pkt = parse_packet(line)
                    if pkt:
                        username = self._dispatch(sock, pkt, username)
        except (ConnectionResetError, OSError):
            pass
        finally:
            self._disconnect(sock, username)

    def _dispatch(self, sock, pkt: dict, username):
        t = pkt.get('type')
        if t == 'register':
            uname = pkt.get('username', '').strip()
            pwd   = pkt.get('password', '')
            if not uname:
                self._send(sock, 'error', msg="Username cannot be empty.")
            elif uname in self.users:
                self._send(sock, 'error', msg=f"Username '{uname}' already taken.")
            else:
                with self.lock:
                    profile = UserProfile(uname, pwd)
                    self.users[uname]   = profile
                    self.clients[sock]  = uname
                    self.rooms['general'].members.add(uname)
                self._send(sock, 'registered', profile=profile.info())
                self._broadcast_all('system',
                    msg=f"{profile.avatar} {uname} joined the server!", exclude=sock)
                username = uname
        elif t == 'chat':
            room_name = pkt.get('room', 'general')
            msg       = pkt.get('msg', '').strip()
            if not username:
                self._send(sock, 'error', msg="Not registered.")
            elif not msg:
                pass
            elif room_name not in self.rooms:
                self._send(sock, 'error', msg=f"Room '{room_name}' not found.")
            elif username not in self.rooms[room_name].members:
                self._send(sock, 'error', msg=f"You are not in room '{room_name}'.")
            else:
                profile = self.users[username]
                profile.msg_count += 1
                self.rooms[room_name].add_message(username, msg)
                avatar = profile.avatar
                self._broadcast_room(room_name, 'chat',
                    room=room_name, user=username, avatar=avatar, msg=msg)
        elif t == 'join_room':
            room_name = pkt.get('room', '').strip()
            if not username:
                self._send(sock, 'error', msg="Not registered.")
            elif room_name not in self.rooms:
                self._send(sock, 'error', msg=f"Room '{room_name}' not found.")
            else:
                with self.lock:
                    self.rooms[room_name].members.add(username)
                self._send(sock, 'joined_room', room=room_name,
                    history=[{"ts": e[0], "user": e[1], "msg": e[2]}
                             for e in self.rooms[room_name].get_recent()])
                self._broadcast_room(room_name, 'system',
                    msg=f"{self.users[username].avatar} {username} joined #{room_name}",
                    exclude=sock)
        elif t == 'create_room':
            room_name = pkt.get('room', '').strip()
            private   = pkt.get('private', False)
            if not username:
                self._send(sock, 'error', msg="Not registered.")
            elif not room_name:
                self._send(sock, 'error', msg="Room name cannot be empty.")
            elif room_name in self.rooms:
                self._send(sock, 'error', msg=f"Room '{room_name}' already exists.")
            else:
                with self.lock:
                    self._create_room(room_name, username, private)
                    self.rooms[room_name].members.add(username)
                self._send(sock, 'room_created', room=self.rooms[room_name].info())
                if not private:
                    self._broadcast_all('system',
                        msg=f"📢 New room #{room_name} created by {username}!", exclude=sock)
        elif t == 'list_rooms':
            with self.lock:
                rooms_info = [r.info() for r in self.rooms.values() if not r.is_private]
            self._send(sock, 'rooms_list', rooms=rooms_info)
        elif t == 'profile':
            target = pkt.get('username', username)
            with self.lock:
                profile = self.users.get(target)
            if profile:
                self._send(sock, 'profile_info', profile=profile.info())
            else:
                self._send(sock, 'error', msg=f"User '{target}' not found.")
        elif t == 'online_users':
            with self.lock:
                users = [self.users[u].info() for u in self.clients.values()]
            self._send(sock, 'online_users', users=users)
        elif t == 'dm':
            target_name = pkt.get('to', '')
            msg         = pkt.get('msg', '').strip()
            if not username:
                self._send(sock, 'error', msg="Not registered.")
            else:
                with self.lock:
                    target_sock = next(
                        (s for s, u in self.clients.items() if u == target_name), None)
                if target_sock:
                    avatar = self.users[username].avatar
                    self._send(target_sock, 'dm',
                        frm=username, avatar=avatar, msg=msg)
                    self._send(sock, 'dm_sent', to=target_name, msg=msg)
                else:
                    self._send(sock, 'error', msg=f"User '{target_name}' is not online.")
        return username

    def _disconnect(self, sock: socket.socket, username):
        with self.lock:
            self.clients.pop(sock, None)
            if username and username in self.users:
                self.users[username].status = "offline"
        if username:
            self._broadcast_all('system', msg=f"👋 {username} left the server.")
        try:
            sock.close()
        except Exception:
            pass

    def start(self):
        self._running = True
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(50)
        print(f"  🚀 Chat Server running on {self.host}:{self.port}")
        print("  Press Ctrl+C to stop.\n")
        try:
            while self._running:
                try:
                    srv.settimeout(1.0)
                    conn, addr = srv.accept()
                    t = threading.Thread(
                        target=self._handle_client, args=(conn, addr), daemon=True)
                    t.start()
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            pass
        finally:
            srv.close()
            print("\n  Server stopped.")


# ── Chat Client (original socket-based) ──────────────────────

class ChatClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self.host        = host
        self.port        = port
        self.sock        = None
        self.username    = None
        self.current_room = "general"
        self._running    = False

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self._running = True
        t = threading.Thread(target=self._receive_loop, daemon=True)
        t.start()

    def _send(self, ptype: str, **kwargs):
        try:
            self.sock.sendall(make_packet(ptype, **kwargs))
        except Exception as e:
            print(f"  ❌ Send error: {e}")

    def _receive_loop(self):
        buf = b""
        while self._running:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    pkt = parse_packet(line)
                    if pkt:
                        self._handle_packet(pkt)
            except Exception:
                break

    def _handle_packet(self, pkt: dict):
        t = pkt.get('type')
        ts = pkt.get('ts', '')
        if t == 'registered':
            p = pkt['profile']
            print(f"\n  ✅ Registered as {p['avatar']} {p['username']}")
            print(f"     Joined #general automatically. Type /help for commands.\n")
        elif t == 'chat':
            room = pkt.get('room', '')
            print(f"  [{ts}] #{room} {pkt.get('avatar','')} {pkt.get('user','')}: {pkt.get('msg','')}")
        elif t == 'system':
            print(f"  [{ts}] ⚙️  {pkt.get('msg','')}")
        elif t == 'error':
            print(f"  ❌ {pkt.get('msg','')}")
        elif t == 'dm':
            print(f"  [{ts}] 📩 DM from {pkt.get('avatar','')} {pkt.get('frm','')}: {pkt.get('msg','')}")
        elif t == 'dm_sent':
            print(f"  [{ts}] 📤 DM sent to {pkt.get('to','')}: {pkt.get('msg','')}")
        elif t == 'joined_room':
            room = pkt.get('room','')
            self.current_room = room
            print(f"\n  ✅ Joined #{room}")
            history = pkt.get('history', [])
            if history:
                print(f"  ── Last {len(history)} messages ──")
                for e in history:
                    print(f"     [{e['ts']}] {e['user']}: {e['msg']}")
                print()
        elif t == 'room_created':
            r = pkt['room']
            print(f"  ✅ Room #{r['name']} created!")
        elif t == 'rooms_list':
            print("\n  📋 Available Rooms:")
            for r in pkt.get('rooms', []):
                priv = " 🔒" if r['is_private'] else ""
                print(f"     #{r['name']}{priv}  👥 {len(r['members'])} members  💬 {r['msg_count']} msgs")
            print()
        elif t == 'profile_info':
            p = pkt['profile']
            print(f"\n  👤 Profile: {p['avatar']} {p['username']}")
            print(f"     Status:   {p['status']}")
            print(f"     Joined:   {p['joined_at']}")
            print(f"     Messages: {p['msg_count']}\n")
        elif t == 'online_users':
            print(f"\n  🟢 Online users ({len(pkt.get('users',[]))}):")
            for u in pkt.get('users', []):
                print(f"     {u['avatar']} {u['username']}")
            print()

    def register(self, username: str, password: str = ""):
        self._send('register', username=username, password=password)

    def send_message(self, msg: str, room: str = None):
        self._send('chat', room=room or self.current_room, msg=msg)

    def join_room(self, room: str):
        self._send('join_room', room=room)

    def create_room(self, room: str, private: bool = False):
        self._send('create_room', room=room, private=private)

    def list_rooms(self):
        self._send('list_rooms')

    def dm(self, to: str, msg: str):
        self._send('dm', to=to, msg=msg)

    def profile(self, username: str = None):
        self._send('profile', username=username or self.username)

    def online_users(self):
        self._send('online_users')

    def run_interactive(self):
        print("\n  Commands: /join <room> | /create <room> | /rooms | /dm <user> <msg>")
        print("            /profile [user] | /who | /exit\n")
        while True:
            try:
                line = input().strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if line.startswith('/'):
                parts = line[1:].split(maxsplit=2)
                cmd = parts[0].lower()
                if cmd == 'exit':
                    break
                elif cmd == 'join'   and len(parts) > 1: self.join_room(parts[1])
                elif cmd == 'create' and len(parts) > 1: self.create_room(parts[1])
                elif cmd == 'rooms':                      self.list_rooms()
                elif cmd == 'who':                        self.online_users()
                elif cmd == 'profile':
                    self.profile(parts[1] if len(parts) > 1 else None)
                elif cmd == 'dm' and len(parts) > 2:     self.dm(parts[1], parts[2])
                else:
                    print("  Unknown command. Type /exit to quit.")
            else:
                self.send_message(line)
        self._running = False
        try:
            self.sock.close()
        except Exception:
            pass

    def disconnect(self):
        self._running = False
        try:
            self.sock.close()
        except Exception:
            pass


# ── In-Process Demo (no real sockets) ─────────────────────────

class ChatDemo:
    def __init__(self):
        self.server  = ChatServer()
        self.log     = []

    def _simulate(self):
        print("=" * 56)
        print("  💬  REAL-TIME CHAT APP — SIMULATION DEMO")
        print("=" * 56)
        alice = UserProfile("Alice", "pass1")
        bob   = UserProfile("Bob",   "pass2")
        carol = UserProfile("Carol", "pass3")
        self.server.users["Alice"] = alice
        self.server.users["Bob"]   = bob
        self.server.users["Carol"] = carol
        print(f"\n  👥 Users Created:")
        for u in [alice, bob, carol]:
            print(f"     {u}")
        self.server._create_room("gaming", "Alice")
        self.server.rooms["gaming"].members.update(["Alice", "Bob"])
        self.server._create_room("secret", "Carol", private=True)
        self.server.rooms["secret"].members.add("Carol")
        print(f"\n  🏠 Rooms Created:")
        for name, room in self.server.rooms.items():
            priv = " [private]" if room.is_private else ""
            print(f"     #{name}{priv}  members: {', '.join(room.members)}")
        print(f"\n  💬 Simulating Messages in #general:")
        general = self.server.rooms["general"]
        general.members.update(["Alice", "Bob", "Carol"])
        convos = [
            ("Alice", "Hey everyone! 👋"),
            ("Bob",   "Hi Alice! How's it going?"),
            ("Carol", "Hello all! Excited to be here!"),
            ("Alice", "Doing great! Anyone up for a game?"),
            ("Bob",   "I'm in! What are we playing?"),
            ("Carol", "Count me in too!"),
        ]
        for user, msg in convos:
            general.add_message(user, msg)
            u = self.server.users[user]
            u.msg_count += 1
            print(f"     [{timestamp()}] {u.avatar} {user}: {msg}")
        print(f"\n  🎮 Messages in #gaming:")
        gaming = self.server.rooms["gaming"]
        gaming_convos = [
            ("Alice", "Ready to play Minecraft?"),
            ("Bob",   "Let's go! Starting server now."),
        ]
        for user, msg in gaming_convos:
            gaming.add_message(user, msg)
            u = self.server.users[user]
            print(f"     [{timestamp()}] {u.avatar} {user}: {msg}")
        print(f"\n  ✅ All chat features verified successfully!")
        print("=" * 56)

    def run(self):
        self._simulate()


# ══════════════════════════════════════════════════════════════
#  FLASK WEB APPLICATION — Discord-style Chat UI
# ══════════════════════════════════════════════════════════════

app = Flask(__name__)

# ── In-memory state ───────────────────────────────────────────
chat_lock = threading.Lock()

# Bot users (fixed avatars)
BOT_PROFILES = {
    "Alice": UserProfile.__new__(UserProfile),
    "Bob":   UserProfile.__new__(UserProfile),
    "Carol": UserProfile.__new__(UserProfile),
}
for _name, _avatar in [("Alice", "🦊"), ("Bob", "🐯"), ("Carol", "🦉")]:
    p = BOT_PROFILES[_name]
    p.username  = _name
    p.avatar    = _avatar
    p.joined_at = datetime.datetime.now()
    p.pw_hash   = ""
    p.status    = "online"
    p.msg_count = 0

# The web user profile (set on first message or from avatar selector)
web_user = {
    "username": "You",
    "avatar": "🐼",
    "status": "online",
}

# Chat rooms
chat_rooms: dict[str, ChatRoom] = {}

def _init_rooms():
    """Create pre-seeded rooms with demo messages."""
    global chat_rooms
    chat_rooms["general"] = ChatRoom("general", "system")
    chat_rooms["gaming"]  = ChatRoom("gaming",  "system")
    chat_rooms["random"]  = ChatRoom("random",  "system")
    for r in chat_rooms.values():
        r.members = {"Alice", "Bob", "Carol", "You"}

    # Seed general
    seed_general = [
        ("Alice", "Hey everyone! Welcome to the chat 👋"),
        ("Bob",   "Yo! What's up? 🎉"),
        ("Carol", "Hi all! Great to see this server alive!"),
        ("Alice", "Anyone working on something cool today?"),
        ("Bob",   "Just deployed a new feature. Feeling great 💪"),
    ]
    for user, msg in seed_general:
        chat_rooms["general"].add_message(user, msg)
        BOT_PROFILES[user].msg_count += 1

    # Seed gaming
    seed_gaming = [
        ("Alice", "Anyone down for some Minecraft tonight? ⛏️"),
        ("Bob",   "I'm in! Let me grab my diamond pickaxe 💎"),
        ("Carol", "Count me in! I'll bring the potions 🧪"),
    ]
    for user, msg in seed_gaming:
        chat_rooms["gaming"].add_message(user, msg)
        BOT_PROFILES[user].msg_count += 1

    # Seed random
    seed_random = [
        ("Carol", "Did you know octopuses have three hearts? 🐙"),
        ("Alice", "Fun fact: honey never spoils! 🍯"),
        ("Bob",   "I just learned that bananas are berries 🍌"),
    ]
    for user, msg in seed_random:
        chat_rooms["random"].add_message(user, msg)
        BOT_PROFILES[user].msg_count += 1

_init_rooms()

# ── Bot auto-reply logic ─────────────────────────────────────

BOT_REPLIES = {
    "general": [
        "That's awesome! 🎉", "I totally agree! 👍", "Haha, nice one! 😂",
        "Interesting point! 🤔", "Tell me more!", "Couldn't agree more 💯",
        "That reminds me of something...", "LOL 😆", "Great to hear!",
        "Same here!", "Facts! 🔥", "No way, really?!", "Big mood 😎",
        "Love that energy! ⚡", "Keep going, you're on a roll!",
    ],
    "gaming": [
        "GG! 🏆", "Let's run it back! 🎮", "I call dibs on healer 🩹",
        "Anyone got extra loot? 💰", "Nerf incoming for sure 😅",
        "One more round? 🔄", "That was a clutch play! 🎯",
        "I need to upgrade my gear ⚔️", "Who's hosting tonight? 🌙",
        "My ping is terrible today 📶", "ez clap 👏", "Respawning... 💀",
    ],
    "random": [
        "Whoa, I didn't know that! 🤯", "That's wild! 🌀",
        "Here's another one: cats can't taste sweetness 🐱",
        "The universe is so weird 🌌", "Mind = blown 🤯",
        "Speaking of random, did you see that meme? 😂",
        "I need coffee ☕", "What a time to be alive ✨",
        "Alexa, play random facts 🎵", "Wait what?! No way!",
        "BRB, going down a Wikipedia rabbit hole 🐇",
    ],
}

def _schedule_bot_reply(room_name: str):
    """Schedule a bot to reply in 1-2 seconds on a background thread."""
    def _reply():
        delay = random.uniform(1.0, 2.0)
        time.sleep(delay)
        bot_name = random.choice(["Alice", "Bob", "Carol"])
        bot = BOT_PROFILES[bot_name]
        pool = BOT_REPLIES.get(room_name, BOT_REPLIES["general"])
        msg = random.choice(pool)
        with chat_lock:
            if room_name in chat_rooms:
                chat_rooms[room_name].add_message(bot_name, msg)
                bot.msg_count += 1

    t = threading.Thread(target=_reply, daemon=True)
    t.start()


# ── HTML Template ─────────────────────────────────────────────

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>💬 Pinnacle Chat</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#1e1f22;--bg-deep:#17181b;--card:#2b2d31;--card-hover:#32353b;
  --sidebar:#1e1f22;--accent:#5865f2;--accent-glow:rgba(88,101,242,.25);
  --text:#dbdee1;--text-muted:#949ba4;--text-dim:#6d6f78;
  --border:rgba(255,255,255,.06);--border-accent:rgba(88,101,242,.4);
  --success:#23a55a;--warning:#f0b232;--danger:#da373c;
  --glass:rgba(43,45,49,.65);--glass-border:rgba(255,255,255,.08);
  --font:'Outfit',sans-serif;--mono:'JetBrains Mono',monospace;
  --radius:12px;--radius-sm:8px;
}
html,body{height:100%;overflow:hidden}
body{font-family:var(--font);background:var(--bg-deep);color:var(--text);display:flex;flex-direction:column}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.12);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,.2)}

/* ── Top Bar ── */
.topbar{
  height:48px;min-height:48px;display:flex;align-items:center;
  padding:0 20px;background:var(--card);border-bottom:1px solid var(--border);
  gap:12px;z-index:10;
}
.topbar .hash{color:var(--text-muted);font-size:22px;font-weight:300}
.topbar .room-name{font-weight:600;font-size:15px;color:var(--text)}
.topbar .room-desc{color:var(--text-muted);font-size:13px;margin-left:12px;
  padding-left:12px;border-left:1px solid var(--border)}
.topbar .brand{margin-left:auto;font-size:12px;font-family:var(--mono);
  color:var(--text-dim);letter-spacing:1px;text-transform:uppercase}

/* ── Layout ── */
.app-layout{display:flex;flex:1;overflow:hidden}

/* ── Left Sidebar ── */
.sidebar-left{
  width:220px;min-width:220px;background:var(--sidebar);
  border-right:1px solid var(--border);display:flex;flex-direction:column;
  padding:0;overflow-y:auto;
}
.sidebar-header{
  padding:16px 16px 12px;font-size:11px;font-weight:600;
  text-transform:uppercase;letter-spacing:1.2px;color:var(--text-muted);
}
.channel-list{list-style:none;padding:0 8px}
.channel-item{
  display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:var(--radius-sm);cursor:pointer;font-size:14px;
  color:var(--text-muted);transition:all .15s ease;margin-bottom:2px;
  font-weight:500;position:relative;
}
.channel-item:hover{background:var(--card-hover);color:var(--text)}
.channel-item.active{background:var(--accent-glow);color:#fff}
.channel-item.active::before{
  content:'';position:absolute;left:-8px;top:50%;transform:translateY(-50%);
  width:4px;height:20px;background:var(--accent);border-radius:0 4px 4px 0;
}
.channel-item .hash-icon{font-family:var(--mono);font-size:16px;font-weight:700;opacity:.6}
.channel-item.active .hash-icon{opacity:1}
.channel-item .badge{
  margin-left:auto;background:var(--danger);color:#fff;font-size:11px;
  font-weight:600;padding:1px 6px;border-radius:10px;min-width:18px;
  text-align:center;font-family:var(--mono);
}

/* Avatar selector */
.avatar-section{
  margin-top:auto;padding:12px;border-top:1px solid var(--border);
}
.avatar-card{
  display:flex;align-items:center;gap:10px;padding:10px 12px;
  background:var(--bg-deep);border-radius:var(--radius-sm);
}
.avatar-emoji{font-size:28px;line-height:1}
.avatar-info{flex:1}
.avatar-info .name{font-size:13px;font-weight:600;color:var(--text)}
.avatar-info .status-text{font-size:11px;color:var(--success)}
.avatar-select{
  background:var(--card);border:1px solid var(--border);color:var(--text);
  border-radius:6px;padding:4px;font-size:18px;cursor:pointer;
  outline:none;transition:border-color .15s;
}
.avatar-select:focus{border-color:var(--accent)}

/* ── Center Chat ── */
.chat-center{flex:1;display:flex;flex-direction:column;min-width:0}
.messages-area{
  flex:1;overflow-y:auto;padding:16px 20px;display:flex;
  flex-direction:column;gap:2px;
}

/* Message groups */
.msg-group{display:flex;gap:12px;padding:6px 0}
.msg-group:hover{background:rgba(255,255,255,.02);border-radius:var(--radius-sm)}
.msg-avatar{
  font-size:28px;width:40px;height:40px;display:flex;
  align-items:center;justify-content:center;flex-shrink:0;
  background:var(--bg-deep);border-radius:50%;margin-top:2px;
}
.msg-body{flex:1;min-width:0}
.msg-header{display:flex;align-items:baseline;gap:8px;margin-bottom:2px}
.msg-user{font-weight:600;font-size:14px;color:var(--accent);cursor:pointer}
.msg-user:hover{text-decoration:underline}
.msg-time{font-size:11px;font-family:var(--mono);color:var(--text-dim);font-weight:400}
.msg-text{font-size:14px;line-height:1.45;color:var(--text);word-break:break-word}
.msg-text.system-msg{color:var(--text-muted);font-style:italic;font-size:13px}

/* Fade-in animation */
@keyframes msgFadeIn{
  from{opacity:0;transform:translateY(8px)}
  to{opacity:1;transform:translateY(0)}
}
.msg-group.new-msg{animation:msgFadeIn .3s ease forwards}

/* ── Input Bar ── */
.input-bar{
  padding:0 20px 20px;
}
.input-wrapper{
  display:flex;align-items:center;gap:0;
  background:var(--card);border:1px solid var(--border);
  border-radius:var(--radius);overflow:hidden;
  transition:border-color .2s;
}
.input-wrapper:focus-within{border-color:var(--accent)}
.input-wrapper input{
  flex:1;background:transparent;border:none;outline:none;
  color:var(--text);font-family:var(--font);font-size:14px;
  padding:14px 16px;
}
.input-wrapper input::placeholder{color:var(--text-dim)}
.send-btn{
  display:flex;align-items:center;justify-content:center;
  width:44px;height:44px;background:var(--accent);border:none;
  color:#fff;cursor:pointer;font-size:18px;transition:all .15s;
  margin:3px;border-radius:var(--radius-sm);
}
.send-btn:hover{background:#4752c4;transform:scale(1.05)}
.send-btn:active{transform:scale(.95)}
.send-btn svg{width:18px;height:18px}

/* ── Right Sidebar ── */
.sidebar-right{
  width:220px;min-width:220px;background:var(--sidebar);
  border-left:1px solid var(--border);overflow-y:auto;padding:0;
}
.users-header{
  padding:16px 16px 12px;font-size:11px;font-weight:600;
  text-transform:uppercase;letter-spacing:1.2px;color:var(--text-muted);
}
.user-list{list-style:none;padding:0 8px}
.user-item{
  display:flex;align-items:center;gap:10px;padding:8px 12px;
  border-radius:var(--radius-sm);transition:background .15s;cursor:default;
  margin-bottom:2px;
}
.user-item:hover{background:var(--card-hover)}
.user-item .u-avatar{font-size:22px}
.user-item .u-name{font-size:13px;font-weight:500;color:var(--text)}
.user-item .u-status{
  width:8px;height:8px;border-radius:50%;margin-left:auto;flex-shrink:0;
}
.u-status.online{background:var(--success);box-shadow:0 0 6px var(--success)}
.u-status.idle{background:var(--warning)}
.u-status.offline{background:var(--text-dim)}

/* ── Welcome splash ── */
.welcome-splash{
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  padding:40px;text-align:center;gap:8px;margin-bottom:12px;
}
.welcome-splash .big-hash{font-size:52px;color:var(--accent);opacity:.4;font-family:var(--mono);font-weight:700}
.welcome-splash h2{font-size:22px;font-weight:700;color:var(--text)}
.welcome-splash p{font-size:13px;color:var(--text-muted);max-width:380px}

/* ── Typing indicator ── */
.typing-indicator{
  padding:0 20px 4px;font-size:12px;color:var(--text-muted);
  font-style:italic;min-height:20px;
}
@keyframes blink{0%,100%{opacity:.3}50%{opacity:1}}
.typing-dots span{animation:blink 1.4s infinite;display:inline-block}
.typing-dots span:nth-child(2){animation-delay:.2s}
.typing-dots span:nth-child(3){animation-delay:.4s}

/* ── Responsive ── */
@media(max-width:900px){
  .sidebar-right{display:none}
  .sidebar-left{width:64px;min-width:64px}
  .sidebar-header,.channel-item span:not(.hash-icon),.avatar-info,.avatar-select{display:none}
  .channel-item{justify-content:center;padding:10px}
  .channel-item .hash-icon{font-size:18px}
  .avatar-card{justify-content:center;padding:8px}
}
@media(max-width:600px){
  .sidebar-left{width:52px;min-width:52px}
}
</style>
</head>
<body>

<!-- Top Bar -->
<div class="topbar">
  <span class="hash">#</span>
  <span class="room-name" id="topRoomName">general</span>
  <span class="room-desc" id="topRoomDesc">Welcome to the general chat</span>
  <span class="brand">Pinnacle Chat v2.0</span>
</div>

<div class="app-layout">

  <!-- Left Sidebar -->
  <div class="sidebar-left">
    <div class="sidebar-header">💬 Channels</div>
    <ul class="channel-list" id="channelList"></ul>
    <div class="avatar-section">
      <div class="avatar-card">
        <span class="avatar-emoji" id="myAvatar">🐼</span>
        <div class="avatar-info">
          <div class="name" id="myName">You</div>
          <div class="status-text">● Online</div>
        </div>
        <select class="avatar-select" id="avatarSelect" title="Change avatar">
          <option>🐼</option><option>🦊</option><option>🦁</option>
          <option>🐯</option><option>🦉</option><option>🐸</option>
          <option>🐺</option><option>🦋</option><option>🐙</option>
          <option>🦄</option><option>🦅</option><option>🐬</option>
        </select>
      </div>
    </div>
  </div>

  <!-- Center Chat -->
  <div class="chat-center">
    <div class="messages-area" id="messagesArea"></div>
    <div class="typing-indicator" id="typingIndicator"></div>
    <div class="input-bar">
      <div class="input-wrapper">
        <input type="text" id="msgInput" placeholder="Message #general" autocomplete="off"/>
        <button class="send-btn" id="sendBtn" title="Send message">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
               stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  </div>

  <!-- Right Sidebar -->
  <div class="sidebar-right">
    <div class="users-header">👥 Online — <span id="onlineCount">0</span></div>
    <ul class="user-list" id="userList"></ul>
  </div>

</div>

<script>
// ── State ──
let currentRoom = 'general';
let lastMsgCount = {};
let myAvatar = '🐼';
let pollInterval = null;
let lastKnownCounts = {};

const roomDescriptions = {
  general: 'Welcome to the general chat',
  gaming: 'Talk about games, find teammates',
  random: 'Off-topic, memes, and random fun'
};

// ── Web Audio click sound ──
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;
function playClickSound(){
  try{
    if(!audioCtx) audioCtx = new AudioCtx();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.type = 'sine'; osc.frequency.setValueAtTime(880, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.08);
    gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.1);
    osc.start(); osc.stop(audioCtx.currentTime + 0.1);
  }catch(e){}
}
function playReceiveSound(){
  try{
    if(!audioCtx) audioCtx = new AudioCtx();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.type = 'sine'; osc.frequency.setValueAtTime(523, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(784, audioCtx.currentTime + 0.06);
    gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.08);
    osc.start(); osc.stop(audioCtx.currentTime + 0.08);
  }catch(e){}
}

// ── API helpers ──
async function api(path, opts){
  const r = await fetch(path, opts);
  return r.json();
}

// ── Load rooms ──
async function loadRooms(){
  const data = await api('/api/chat/rooms');
  const list = document.getElementById('channelList');
  list.innerHTML = '';
  data.rooms.forEach(r => {
    const li = document.createElement('li');
    li.className = 'channel-item' + (r.name === currentRoom ? ' active' : '');
    const unread = (lastKnownCounts[r.name] || 0) > 0 && r.name !== currentRoom;
    li.innerHTML = '<span class="hash-icon">#</span><span>' + r.name + '</span>' +
                   (unread ? '<span class="badge">' + lastKnownCounts[r.name] + '</span>' : '');
    li.onclick = () => switchRoom(r.name);
    list.appendChild(li);
  });
}

// ── Load users ──
async function loadUsers(){
  const data = await api('/api/chat/users');
  const list = document.getElementById('userList');
  list.innerHTML = '';
  document.getElementById('onlineCount').textContent = data.users.length;
  data.users.forEach(u => {
    const li = document.createElement('li');
    li.className = 'user-item';
    const statusCls = u.status === 'online' ? 'online' : u.status === 'idle' ? 'idle' : 'offline';
    li.innerHTML = '<span class="u-avatar">' + u.avatar + '</span>' +
                   '<span class="u-name">' + u.username + '</span>' +
                   '<span class="u-status ' + statusCls + '"></span>';
    list.appendChild(li);
  });
}

// ── Load messages ──
let previousMsgLen = 0;
async function loadMessages(scroll){
  const data = await api('/api/chat/messages?room=' + currentRoom);
  const area = document.getElementById('messagesArea');
  const msgs = data.messages;
  const isNew = msgs.length > previousMsgLen;
  previousMsgLen = msgs.length;

  // Build HTML
  let html = '<div class="welcome-splash"><div class="big-hash">#</div>' +
             '<h2>Welcome to #' + currentRoom + '</h2>' +
             '<p>' + (roomDescriptions[currentRoom]||'Chat away!') + '</p></div>';

  let lastUser = null;
  msgs.forEach((m, i) => {
    const isNewMsg = isNew && i >= msgs.length - 1;
    if(m.user !== lastUser){
      html += '<div class="msg-group' + (isNewMsg ? ' new-msg' : '') + '">' +
              '<div class="msg-avatar">' + m.avatar + '</div>' +
              '<div class="msg-body">' +
              '<div class="msg-header"><span class="msg-user">' + m.user + '</span>' +
              '<span class="msg-time">' + m.ts + '</span></div>' +
              '<div class="msg-text">' + escapeHtml(m.msg) + '</div></div></div>';
    } else {
      html += '<div class="msg-group' + (isNewMsg ? ' new-msg' : '') +
              '" style="padding-left:52px;padding-top:0;padding-bottom:0">' +
              '<div class="msg-body"><div class="msg-text">' + escapeHtml(m.msg) + '</div></div></div>';
    }
    lastUser = m.user;
  });

  area.innerHTML = html;
  if(scroll !== false){
    area.scrollTop = area.scrollHeight;
  }
  if(isNew && msgs.length > 0){
    const lastMsg = msgs[msgs.length - 1];
    if(lastMsg.user !== 'You'){
      playReceiveSound();
    }
  }
}

function escapeHtml(t){
  const d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}

// ── Switch room ──
function switchRoom(name){
  currentRoom = name;
  previousMsgLen = 0;
  lastKnownCounts[name] = 0;
  document.getElementById('topRoomName').textContent = name;
  document.getElementById('topRoomDesc').textContent = roomDescriptions[name]||'';
  document.getElementById('msgInput').placeholder = 'Message #' + name;
  loadRooms();
  loadMessages(true);
}

// ── Send message ──
async function sendMessage(){
  const input = document.getElementById('msgInput');
  const msg = input.value.trim();
  if(!msg) return;
  input.value = '';
  playClickSound();

  // Show typing indicator
  const typing = document.getElementById('typingIndicator');
  typing.innerHTML = '';

  await api('/api/chat/messages', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({room: currentRoom, msg: msg, avatar: myAvatar})
  });
  await loadMessages(true);

  // Show bot typing after short delay
  setTimeout(() => {
    const bots = ['Alice','Bob','Carol'];
    const bot = bots[Math.floor(Math.random()*bots.length)];
    typing.innerHTML = '<span class="typing-dots"><span>●</span><span>●</span><span>●</span></span> ' + bot + ' is typing...';
    setTimeout(() => { typing.innerHTML = ''; }, 2500);
  }, 400);
}

// ── Avatar selector ──
document.getElementById('avatarSelect').addEventListener('change', function(){
  myAvatar = this.value;
  document.getElementById('myAvatar').textContent = myAvatar;
  // Notify server
  api('/api/chat/avatar', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({avatar: myAvatar})
  });
});

// ── Input events ──
document.getElementById('msgInput').addEventListener('keydown', e => {
  if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); sendMessage(); }
});
document.getElementById('sendBtn').addEventListener('click', sendMessage);

// ── Polling ──
async function poll(){
  // Check for new messages in current room
  await loadMessages(true);
  // Check other rooms for badge counts
  const roomsData = await api('/api/chat/rooms');
  roomsData.rooms.forEach(r => {
    if(r.name !== currentRoom){
      const prev = lastMsgCount[r.name] || 0;
      const diff = r.msg_count - prev;
      if(diff > 0){
        lastKnownCounts[r.name] = (lastKnownCounts[r.name]||0) + diff;
      }
    }
    lastMsgCount[r.name] = r.msg_count;
  });
  loadRooms();
  loadUsers();
}

// ── Init ──
(async function init(){
  // Snapshot initial counts
  const roomsData = await api('/api/chat/rooms');
  roomsData.rooms.forEach(r => { lastMsgCount[r.name] = r.msg_count; });
  lastKnownCounts = {};
  await loadRooms();
  await loadUsers();
  await loadMessages(true);
  pollInterval = setInterval(poll, 1500);
  document.getElementById('msgInput').focus();
})();
</script>
</body>
</html>
"""

# ── Room descriptions for API ────────────────────────────────
ROOM_DESCRIPTIONS = {
    "general": "Welcome to the general chat",
    "gaming": "Talk about games, find teammates",
    "random": "Off-topic, memes, and random fun",
}

# ── Flask Routes ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/chat/rooms")
def api_rooms():
    with chat_lock:
        rooms = []
        for name, room in chat_rooms.items():
            info = room.info()
            info["description"] = ROOM_DESCRIPTIONS.get(name, "")
            rooms.append(info)
    return jsonify({"rooms": rooms})


@app.route("/api/chat/messages")
def api_messages():
    room_name = request.args.get("room", "general")
    with chat_lock:
        room = chat_rooms.get(room_name)
        if not room:
            return jsonify({"error": f"Room '{room_name}' not found"}), 404
        messages = []
        for ts, user, msg in room.get_recent(50):
            avatar = "🐼"  # default
            if user in BOT_PROFILES:
                avatar = BOT_PROFILES[user].avatar
            elif user == "You":
                avatar = web_user["avatar"]
            messages.append({
                "ts": ts,
                "user": user,
                "msg": msg,
                "avatar": avatar,
            })
    return jsonify({"messages": messages, "room": room_name})


@app.route("/api/chat/messages", methods=["POST"])
def api_send_message():
    data = request.get_json(silent=True) or {}
    room_name = data.get("room", "general")
    msg = data.get("msg", "").strip()
    avatar = data.get("avatar", "🐼")

    if not msg:
        return jsonify({"error": "Empty message"}), 400

    with chat_lock:
        room = chat_rooms.get(room_name)
        if not room:
            return jsonify({"error": f"Room '{room_name}' not found"}), 404
        web_user["avatar"] = avatar
        room.add_message("You", msg)

    # Schedule bot reply
    _schedule_bot_reply(room_name)

    return jsonify({"ok": True, "room": room_name})


@app.route("/api/chat/users")
def api_users():
    users = []
    # Web user
    users.append({
        "username": web_user["username"],
        "avatar": web_user["avatar"],
        "status": "online",
    })
    # Bots
    for name in ["Alice", "Bob", "Carol"]:
        bot = BOT_PROFILES[name]
        users.append({
            "username": bot.username,
            "avatar": bot.avatar,
            "status": "online",
        })
    return jsonify({"users": users})


@app.route("/api/chat/avatar", methods=["POST"])
def api_set_avatar():
    data = request.get_json(silent=True) or {}
    avatar = data.get("avatar", "🐼")
    web_user["avatar"] = avatar
    return jsonify({"ok": True, "avatar": avatar})


# ══════════════════════════════════════════════════════════════
#  Entry Point
# ══════════════════════════════════════════════════════════════

def print_banner():
    banner = r"""
╔══════════════════════════════════════════════════════════╗
║          💬  PINNACLE CHAT  ·  Premium Web UI            ║
║══════════════════════════════════════════════════════════║
║  Flask server starting on http://127.0.0.1:5005         ║
║  Auto-opening browser...                                 ║
║  Press Ctrl+C to stop                                    ║
╚══════════════════════════════════════════════════════════╝
"""
    print(banner)


if __name__ == "__main__":
    mode = None
    for arg in sys.argv[1:]:
        if arg in ("--server", "--client", "--demo"):
            mode = arg
            break

    if mode == "--server":
        server = ChatServer()
        server.start()

    elif mode == "--client":
        host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 9000
        client = ChatClient(host, port)
        try:
            client.connect()
            uname = input("  Username: ").strip()
            pwd   = input("  Password: ").strip()
            client.username = uname
            client.register(uname, pwd)
            time.sleep(0.3)
            client.run_interactive()
        except ConnectionRefusedError:
            print("  ❌ Could not connect. Is the server running?")

    elif mode == "--demo":
        ChatDemo().run()

    else:
        # Default: Flask web UI
        print_banner()
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5005")).start()
        app.run(host="127.0.0.1", port=5005, debug=False)
