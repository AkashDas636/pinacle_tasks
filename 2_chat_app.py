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
import queue
from collections import defaultdict

# Force UTF-8 encoding on standard output/error on Windows
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# ── Flask import ──────────────────────────────────────────────
from flask import Flask, request, jsonify, render_template_string, Response, session, make_response, redirect


# ── Shared helpers ────────────────────────────────────────────

def timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S")


# ── Real-Time Streaming & Unification State ───────────────────
sse_listeners = []
sse_lock = threading.Lock()
active_server_instance = None
global_users = {}
chat_rooms = {}
chat_lock = threading.Lock()

def broadcast_sse(event_type: str, data: dict):
    payload = json.dumps({"event": event_type, "data": data})
    with sse_lock:
        for q in list(sse_listeners):
            try:
                q.put_nowait(payload)
            except Exception:
                pass

def broadcast_to_sockets(room_name: str, ptype: str, **kwargs):
    global active_server_instance
    if active_server_instance:
        active_server_instance._broadcast_room(room_name, ptype, **kwargs)


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
        self.custom_status = ""
        self.mute      = False
        self.deafen    = False

    def verify(self, password: str) -> bool:
        return self.pw_hash == hashlib.sha256(password.encode()).hexdigest()

    def info(self) -> dict:
        return {
            "username":  self.username,
            "avatar":    self.avatar,
            "joined_at": self.joined_at.strftime("%Y-%m-%d %H:%M"),
            "status":    self.status,
            "msg_count": self.msg_count,
            "custom_status": getattr(self, "custom_status", ""),
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
        self.history    = []          # list of dicts: {"id", "ts", "user", "msg", "avatar", "reactions"}
        self.created_at = datetime.datetime.now()
        self.type       = "text"      # "text", "voice", or "dm"
        self.voice_members = set()

    def add_message(self, username: str, message: str, msg_id: str = None):
        avatar = "🐼"
        if username in global_users:
            avatar = global_users[username].avatar
        
        entry = {
            "id": msg_id or hashlib.md5(f"{username}-{timestamp()}-{random.random()}".encode()).hexdigest(),
            "ts": timestamp(),
            "user": username,
            "msg": message,
            "avatar": avatar,
            "reactions": {}
        }
        self.history.append(entry)
        if len(self.history) > 200:
            self.history = self.history[-200:]
            
        # SSE broadcast
        broadcast_sse("message", {
            "room": self.name,
            "message": entry
        })
        
        # Socket broadcast
        broadcast_to_sockets(self.name, 'chat', room=self.name, user=username, avatar=avatar, msg=message)
        return entry

    def get_recent(self, n: int = 50):
        return self.history[-n:]

    def info(self) -> dict:
        return {
            "name":       self.name,
            "owner":      self.owner,
            "members":    list(self.members),
            "is_private": self.is_private,
            "msg_count":  len(self.history),
            "type":       getattr(self, "type", "text"),
            "voice_members": list(getattr(self, "voice_members", set())),
        }


# ── Chat Server (socket-based) ───────────────────────────────

class ChatServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self.host    = host
        self.port    = port
        self.users   = global_users
        self.clients : dict[socket.socket, str]       = {}
        self.rooms   = chat_rooms
        self.lock    = chat_lock
        self._create_room("general", "system")
        self._create_room("gaming",  "system")
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
                    history=[{"ts": e["ts"], "user": e["user"], "msg": e["msg"]}
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
            broadcast_sse("presence", {
                "username": username,
                "status": "offline"
            })
        try:
            sock.close()
        except Exception:
            pass

    def start(self):
        global active_server_instance
        active_server_instance = self
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


# ── Chat Client (socket-based) ───────────────────────────────

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
app.secret_key = "pinnacle_chat_super_secret_key_99"

# Bot users (fixed avatars seeded in global_users)
BOT_PROFILES = {}
for _name, _avatar in [("Alice", "🦊"), ("Bob", "🐯"), ("Carol", "🦉")]:
    p = UserProfile(_name)
    p.avatar    = _avatar
    p.pw_hash   = ""
    p.status    = "online"
    global_users[_name] = p
    BOT_PROFILES[_name] = p

def _init_rooms():
    """Create pre-seeded rooms with demo messages."""
    global chat_rooms
    
    # Text channels
    chat_rooms["general"] = ChatRoom("general", "system")
    chat_rooms["general"].type = "text"
    chat_rooms["gaming"]  = ChatRoom("gaming",  "system")
    chat_rooms["gaming"].type = "text"
    chat_rooms["random"]  = ChatRoom("random",  "system")
    chat_rooms["random"].type = "text"

    # Voice channels
    chat_rooms["Lounge"] = ChatRoom("Lounge", "system")
    chat_rooms["Lounge"].type = "voice"
    chat_rooms["Gaming Voice"] = ChatRoom("Gaming Voice", "system")
    chat_rooms["Gaming Voice"].type = "voice"

    for r in chat_rooms.values():
        r.members.update(["Alice", "Bob", "Carol"])

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
        delay = random.uniform(1.2, 2.2)
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

def get_dm_bot_target(room_name: str, current_user: str):
    if not room_name.startswith("dm__"):
        return None
    parts = room_name[4:].split("__")
    if len(parts) == 2:
        other = parts[1] if parts[0] == current_user else parts[0]
        if other in BOT_PROFILES:
            return other
    return None

def _schedule_bot_dm_reply(room_name: str, bot_name: str):
    def _reply():
        delay = random.uniform(1.2, 2.2)
        time.sleep(delay)
        bot = BOT_PROFILES[bot_name]
        pool = [
            "Hey! How's your day going?",
            "That's super cool! Tell me more about it.",
            "I'm actually coding a new Flask feature right now! 🐍",
            "Haha! That's awesome. 😂",
            "Do you want to play Minecraft later? ⛏️",
            "I totally agree with that!",
            "Let me think about it... 🤔",
        ]
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
  --bg-primary:#313338;
  --bg-secondary:#2b2d31;
  --bg-secondary-alt:#232428;
  --bg-tertiary:#1e1f22;
  --bg-modifier-selected:rgba(79,84,92,0.32);
  --bg-modifier-hover:rgba(79,84,92,0.16);
  --bg-floating:#111214;
  --accent:#5865f2;
  --accent-hover:#4752c4;
  --text-normal:#dbdee1;
  --text-muted:#949ba4;
  --text-dim:#4e5058;
  --border:rgba(255,255,255,0.05);
  --status-online:#23a55a;
  --status-idle:#f0b232;
  --status-dnd:#f23f43;
  --status-offline:#80848e;
  --radius-lg:16px;
  --radius-md:8px;
  --radius-sm:4px;
  --font:'Outfit',sans-serif;
}
html,body{height:100%;overflow:hidden;font-family:var(--font);background:var(--bg-tertiary);color:var(--text-normal)}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(0,0,0,0.3);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:rgba(0,0,0,0.5)}

.app-container {
  display: flex; height: 100vh; width: 100vw; overflow: hidden;
}

/* ── Left Navigation Bar ── */
.nav-sidebar {
  width: 72px; background: var(--bg-tertiary); display: flex; flex-direction: column; align-items: center; padding: 12px 0; gap: 8px; flex-shrink: 0;
}
.nav-icon {
  width: 48px; height: 48px; border-radius: 50%; background: var(--bg-primary); display: flex; align-items: center; justify-content: center; font-size: 20px; cursor: pointer; transition: all 0.2s ease-in-out; position: relative; color: var(--text-normal);
}
.nav-icon:hover {
  border-radius: 35%; background: var(--accent); color: white;
}
.nav-icon.active {
  border-radius: 35%; background: var(--accent); color: white;
}
.nav-icon.active::before {
  content: ''; position: absolute; left: 0; width: 4px; height: 40px; background: white; border-radius: 0 4px 4px 0;
}
.nav-separator {
  width: 32px; height: 2px; background: var(--bg-modifier-selected); margin: 4px 0;
}

/* ── Channels/DMs Sidebar ── */
.channels-sidebar {
  width: 240px; background: var(--bg-secondary); display: flex; flex-direction: column; flex-shrink: 0; border-right: 1px solid var(--border);
}
.sidebar-header {
  height: 48px; padding: 0 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; font-weight: 700; font-size: 15px;
}
.sidebar-scrollable {
  flex: 1; overflow-y: auto; padding: 12px 8px; display: flex; flex-direction: column; gap: 16px;
}
.channel-group-header {
  font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px; padding: 0 8px 4px; display: flex; align-items: center; justify-content: space-between;
}
.btn-add-channel {
  background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 16px; transition: color 0.15s;
}
.btn-add-channel:hover {
  color: var(--text-normal);
}
.channel-list {
  list-style: none; display: flex; flex-direction: column; gap: 2px;
}
.channel-item-container {
  display: flex; flex-direction: column;
}
.channel-item {
  display: flex; align-items: center; gap: 6px; padding: 6px 8px; border-radius: var(--radius-md); cursor: pointer; color: var(--text-muted); font-size: 14px; font-weight: 500; transition: all 0.15s; position: relative;
}
.channel-item:hover {
  background: var(--bg-modifier-hover); color: var(--text-normal);
}
.channel-item.active {
  background: var(--bg-modifier-selected); color: white;
}
.channel-item .hash-icon {
  font-size: 16px; width: 20px; text-align: center;
}
.channel-item .badge {
  margin-left: auto; background: var(--status-dnd); color: white; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 10px;
}
.dm-status-dot {
  position: absolute; right: 8px; width: 8px; height: 8px; border-radius: 50%;
}
.dm-status-dot.online { background: var(--status-online); }
.dm-status-dot.idle { background: var(--status-idle); }
.dm-status-dot.dnd { background: var(--status-dnd); }
.dm-status-dot.offline { background: var(--status-offline); }

.voice-users {
  list-style: none; padding-left: 28px; display: flex; flex-direction: column; gap: 2px; margin: 2px 0 6px;
}
.voice-user-item {
  display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-normal); padding: 4px;
}
.voice-user-item .v-avatar {
  font-size: 14px;
}

/* ── Voice Connected State Panel ── */
.voice-panel {
  background: var(--bg-secondary-alt); padding: 10px 12px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border);
}
.voice-info {
  display: flex; flex-direction: column; gap: 2px;
}
.voice-status {
  font-size: 12px; font-weight: 700; color: var(--status-online); display: flex; align-items: center; gap: 4px;
}
.voice-status::before {
  content: ''; display: inline-block; width: 6px; height: 6px; background: var(--status-online); border-radius: 50%;
}
.voice-room {
  font-size: 13px; font-weight: 600; color: white; max-width: 110px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.voice-controls {
  display: flex; gap: 4px;
}
.voice-controls button {
  background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 6px; border-radius: 4px; display: flex; align-items: center; justify-content: center; transition: all 0.15s;
}
.voice-controls button:hover {
  background: var(--bg-modifier-hover); color: var(--text-normal);
}
.voice-controls button.active {
  color: var(--status-dnd);
}
.voice-controls button.disconnect:hover {
  color: var(--status-dnd);
}
.voice-controls svg {
  width: 16px; height: 16px;
}

/* ── User Footer ── */
.user-footer {
  background: var(--bg-secondary-alt); height: 52px; padding: 0 8px; display: flex; align-items: center; gap: 8px;
}
.footer-avatar {
  font-size: 26px; cursor: pointer; transition: transform 0.2s; position: relative;
}
.footer-avatar:hover {
  transform: scale(1.1);
}
.footer-info {
  flex: 1; display: flex; flex-direction: column; min-width: 0;
}
.footer-name {
  font-size: 13px; font-weight: 700; color: white; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.footer-status {
  font-size: 11px; color: var(--text-muted); display: flex; align-items: center; gap: 4px;
}
.footer-status-dot {
  width: 6px; height: 6px; border-radius: 50%;
}
.footer-status-dot.online { background: var(--status-online); }
.footer-status-dot.idle { background: var(--status-idle); }
.footer-status-dot.dnd { background: var(--status-dnd); }
.footer-status-dot.offline { background: var(--status-offline); }

.footer-actions {
  display: flex; gap: 2px;
}
.footer-actions button {
  background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 6px; border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; transition: all 0.15s;
}
.footer-actions button:hover {
  background: var(--bg-modifier-hover); color: var(--text-normal);
}
.footer-actions svg {
  width: 16px; height: 16px;
}

/* ── Active Chat Area ── */
.chat-area {
  flex: 1; background: var(--bg-primary); display: flex; flex-direction: column; min-width: 0; position: relative;
}
.chat-header {
  height: 48px; border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 16px; gap: 8px; flex-shrink: 0;
}
.chat-header .hash {
  font-size: 20px; color: var(--text-muted); font-weight: 300;
}
.chat-header .title {
  font-weight: 700; font-size: 15px; color: white;
}
.chat-header .description {
  font-size: 12px; color: var(--text-muted); border-left: 1px solid var(--border); padding-left: 8px; margin-left: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 400px;
}
.chat-header .logout-btn {
  margin-left: auto; background: none; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 4px 10px; font-size: 12px; font-weight: 600; color: var(--text-muted); cursor: pointer; transition: all 0.15s;
}
.chat-header .logout-btn:hover {
  border-color: var(--status-dnd); color: white; background: var(--status-dnd);
}
.messages-scroller {
  flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px;
}

/* ── Welcome Splash ── */
.welcome-splash {
  display: flex; flex-direction: column; justify-content: center; padding: 20px 0; gap: 8px; border-bottom: 1px solid var(--border); margin-bottom: 8px;
}
.welcome-splash .big-hash {
  font-size: 48px; width: 68px; height: 68px; background: var(--bg-secondary); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; color: white;
}
.welcome-splash h2 {
  font-size: 24px; font-weight: 700; color: white;
}
.welcome-splash p {
  font-size: 14px; color: var(--text-muted);
}

/* ── Messages & Reactions ── */
.msg-group {
  display: flex; gap: 16px; padding: 4px 8px; border-radius: var(--radius-md); transition: background 0.1s; position: relative;
}
.msg-group:hover {
  background: rgba(0, 0, 0, 0.08);
}
.msg-avatar {
  font-size: 32px; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; background: var(--bg-tertiary); border-radius: 50%; flex-shrink: 0;
}
.msg-body {
  flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px;
}
.msg-header {
  display: flex; align-items: baseline; gap: 8px;
}
.msg-user {
  font-size: 14px; font-weight: 600; color: white; cursor: pointer;
}
.msg-user:hover {
  text-decoration: underline;
}
.msg-time {
  font-size: 10px; color: var(--text-muted); font-family: monospace;
}
.msg-text {
  font-size: 14px; line-height: 1.4; color: var(--text-normal); word-break: break-word; white-space: pre-wrap;
}
.msg-attachment {
  margin-top: 8px; max-width: 320px; max-height: 240px; border-radius: var(--radius-md); overflow: hidden; border: 1px solid var(--border);
}
.msg-attachment img {
  width: 100%; height: 100%; object-fit: contain;
}
.msg-reactions {
  display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px;
}
.reaction-badge {
  display: flex; align-items: center; gap: 4px; background: var(--bg-secondary-alt); border: 1px solid transparent; border-radius: var(--radius-md); padding: 2px 6px; font-size: 12px; cursor: pointer; transition: all 0.1s; user-select: none;
}
.reaction-badge:hover {
  border-color: var(--text-muted); background: var(--bg-modifier-hover);
}
.reaction-badge.active {
  background: rgba(88, 101, 242, 0.15); border-color: var(--accent);
}
.reaction-badge.active:hover {
  background: rgba(88, 101, 242, 0.25);
}
.reaction-badge .count {
  font-size: 11px; font-weight: 700; color: var(--text-normal);
}
.msg-hover-actions {
  position: absolute; right: 16px; top: -12px; display: none; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-md); box-shadow: 0 4px 8px rgba(0,0,0,0.2); gap: 6px; padding: 2px 8px; z-index: 10;
}
.msg-group:hover .msg-hover-actions {
  display: flex;
}
.msg-hover-actions span {
  font-size: 16px; cursor: pointer; transition: transform 0.1s; padding: 2px;
}
.msg-hover-actions span:hover {
  transform: scale(1.3);
}

/* ── Typing Indicator ── */
.typing-indicator {
  padding: 0 20px 4px; font-size: 12px; color: var(--text-muted); font-style: italic; min-height: 20px;
}
@keyframes blink{0%,100%{opacity:.3}50%{opacity:1}}
.typing-dots span{animation:blink 1.4s infinite;display:inline-block}
.typing-dots span:nth-child(2){animation-delay:.2s}
.typing-dots span:nth-child(3){animation-delay:.4s}

/* ── Input Box ── */
.chat-input-container {
  padding: 0 20px 24px; flex-shrink: 0;
}
.chat-input-wrapper {
  background: var(--bg-secondary); border-radius: var(--radius-md); display: flex; align-items: center; padding: 0 16px; gap: 12px; border: 1px solid transparent; transition: border-color 0.15s;
}
.chat-input-wrapper:focus-within {
  border-color: var(--accent);
}
.chat-input-wrapper input {
  flex: 1; height: 44px; background: none; border: none; outline: none; color: var(--text-normal); font-size: 14px;
}
.chat-input-wrapper input::placeholder {
  color: var(--text-muted);
}
.btn-input-attach, .btn-input-send {
  background: none; border: none; color: var(--text-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 4px; border-radius: 4px; transition: color 0.15s, background-color 0.15s;
}
.btn-input-attach:hover {
  color: var(--text-normal); background: var(--bg-modifier-hover);
}
.btn-input-send {
  color: var(--accent);
}
.btn-input-send:hover {
  color: white; background: var(--accent);
}
.chat-input-wrapper svg {
  width: 18px; height: 18px;
}

/* ── Members List Sidebar ── */
.member-sidebar {
  width: 240px; background: var(--bg-secondary); display: flex; flex-direction: column; flex-shrink: 0; border-left: 1px solid var(--border); overflow-y: auto; padding: 16px 8px; gap: 16px;
}
.member-group-header {
  font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px; padding-left: 8px;
}
.user-list {
  list-style: none; display: flex; flex-direction: column; gap: 2px;
}
.user-item {
  display: flex; align-items: center; gap: 10px; padding: 6px 8px; border-radius: var(--radius-md); cursor: pointer; transition: background 0.15s;
}
.user-item:hover {
  background: var(--bg-modifier-hover);
}
.user-item .u-avatar {
  font-size: 24px;
}
.user-item .u-info {
  display: flex; flex-direction: column; flex: 1; min-width: 0;
}
.user-item .u-name {
  font-size: 13.5px; font-weight: 600; color: var(--text-normal); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.user-item .u-custom-status {
  font-size: 11px; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.user-item .u-status {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.user-item .u-status.online { background: var(--status-online); box-shadow: 0 0 6px var(--status-online); }
.user-item .u-status.idle { background: var(--status-idle); }
.user-item .u-status.dnd { background: var(--status-dnd); box-shadow: 0 0 6px var(--status-dnd); }
.user-item .u-status.offline { background: var(--status-offline); }

/* ── Modals / Overlays ── */
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(10, 10, 12, 0.82); backdrop-filter: blur(10px); display: flex; align-items: center; justify-content: center; z-index: 1000; opacity: 1; transition: opacity 0.25s ease;
}
.modal-card {
  background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px; width: 420px; max-width: 90vw; padding: 28px; display: flex; flex-direction: column; gap: 20px; box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4); animation: scaleUp 0.2s cubic-bezier(0.18, 0.89, 0.32, 1.28);
}
@keyframes scaleUp {
  from { transform: scale(0.9); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
.modal-title {
  font-size: 22px; font-weight: 700; color: white; text-align: center;
}
.form-group {
  display: flex; flex-direction: column; gap: 6px;
}
.form-group label {
  font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-normal); letter-spacing: 0.5px;
}
.form-group input, .form-group select {
  background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: var(--radius-md); height: 40px; padding: 0 12px; color: white; outline: none; font-family: var(--font); font-size: 14px; transition: border-color 0.15s;
}
.form-group input:focus, .form-group select:focus {
  border-color: var(--accent);
}
.form-row {
  display: flex; gap: 12px;
}
.form-row .form-group {
  flex: 1;
}
.modal-buttons {
  display: flex; justify-content: flex-end; gap: 10px; margin-top: 10px;
}
.btn-primary {
  background: var(--accent); color: white; border: none; border-radius: var(--radius-md); font-weight: 600; padding: 10px 18px; cursor: pointer; transition: background 0.15s; font-size: 14px;
}
.btn-primary:hover {
  background: var(--accent-hover);
}
.btn-link {
  background: none; border: none; color: var(--text-muted); cursor: pointer; font-weight: 600; padding: 10px; font-size: 14px; transition: color 0.15s;
}
.btn-link:hover {
  color: white;
}

/* Avatar selection grid in modal */
.avatar-grid {
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; justify-items: center; margin-top: 4px;
}
.avatar-grid-item {
  font-size: 28px; width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); cursor: pointer; transition: background 0.15s; border: 2px solid transparent;
}
.avatar-grid-item:hover {
  background: var(--bg-modifier-hover);
}
.avatar-grid-item.selected {
  background: var(--bg-modifier-selected); border-color: var(--accent);
}

.no-dms {
  font-size: 13px; color: var(--text-muted); text-align: center; padding: 20px 8px; font-style: italic;
}

/* ── Responsive ── */
@media(max-width:900px){
  .member-sidebar{display:none}
}
@media(max-width:600px){
  .channels-sidebar{display:none}
}
</style>
</head>
<body>

<div class="app-container">
  <!-- Leftmost Navigation Bar -->
  <div class="nav-sidebar">
    <div class="nav-icon active" id="navHome" onclick="selectView('dm')" title="Home (Direct Messages)">
      📩
    </div>
    <div class="nav-separator"></div>
    <div class="nav-icon" id="navServer" onclick="selectView('server')" title="Pinnacle Server">
      💬
    </div>
  </div>

  <!-- Channels/DMs Sidebar -->
  <div class="channels-sidebar">
    <div class="sidebar-header">
      <span id="sidebarTitle">📩 Direct Messages</span>
      <button class="btn-add-channel" id="btnAddChannel" style="display:none;" onclick="openChannelModal()" title="Create Channel">+</button>
    </div>
    <div class="sidebar-scrollable">
      <ul class="channel-list" id="channelList"></ul>
    </div>

    <!-- Voice Panel -->
    <div class="voice-panel" id="voicePanel" style="display:none;">
      <div class="voice-info">
        <span class="voice-status">Voice Connected</span>
        <span class="voice-room" id="voiceRoomName">Lounge</span>
      </div>
      <div class="voice-controls">
        <button id="btnMute" title="Mute" onclick="toggleMute()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
          </svg>
        </button>
        <button id="btnDeafen" title="Deafen" onclick="toggleDeafen()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 18v-6a9 9 0 0 1 18 0v6"/>
            <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/>
          </svg>
        </button>
        <button class="disconnect" title="Disconnect" onclick="leaveVoice()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7 2 2 0 0 1 1.72 2v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.42 19.42 0 0 1-6.07-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 2.59 3.4z"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- User panel footer -->
    <div class="user-footer">
      <span class="footer-avatar" id="footerAvatar" onclick="openSettingsModal()">🐼</span>
      <div class="footer-info">
        <span class="footer-name" id="footerName">You</span>
        <span class="footer-status">
          <span class="footer-status-dot online" id="footerStatusDot"></span>
          <span id="footerStatusText">Online</span>
        </span>
      </div>
      <div class="footer-actions">
        <button onclick="openSettingsModal()" title="User Settings">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51-1z"/>
          </svg>
        </button>
      </div>
    </div>
  </div>

  <!-- Active Chat Panel -->
  <div class="chat-area">
    <div class="chat-header">
      <span class="hash" id="topChannelIcon">#</span>
      <span class="title" id="topChannelName">general</span>
      <span class="description" id="topChannelDesc">Welcome to general</span>
      <button class="logout-btn" onclick="logout()">Logout</button>
    </div>

    <div class="messages-scroller" id="messagesArea"></div>
    
    <!-- Typing indicator -->
    <div class="typing-indicator" id="typingIndicator"></div>

    <!-- Message Input Bar -->
    <div class="chat-input-container">
      <div class="chat-input-wrapper">
        <button class="btn-input-attach" onclick="attachImage()" title="Attach image URL">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
        <input type="text" id="msgInput" placeholder="Message #general" autocomplete="off" oninput="handleTyping()"/>
        <button class="btn-input-send" onclick="sendMessage()" title="Send message">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  </div>

  <!-- Right Sidebar Members List -->
  <div class="member-sidebar" id="memberSidebar">
    <div class="member-group-header">Online — <span id="onlineCount">0</span></div>
    <ul class="user-list" id="userList"></ul>
  </div>
</div>

<!-- Modal: Login -->
<div class="modal-overlay" id="loginModal" style="display:none;">
  <div class="modal-card">
    <h2 class="modal-title">💬 Welcome to Pinnacle Chat</h2>
    <div class="form-group">
      <label for="loginUsername">Username</label>
      <input type="text" id="loginUsername" placeholder="Enter username..." autocomplete="off"/>
    </div>
    <div class="form-group">
      <label for="loginPassword">Password (Optional)</label>
      <input type="password" id="loginPassword" placeholder="Enter password..."/>
    </div>
    <div class="form-group">
      <label>Choose Avatar</label>
      <div class="avatar-grid" id="loginAvatarGrid"></div>
    </div>
    <div class="modal-buttons">
      <button class="btn-primary" onclick="login()">Enter Chat</button>
    </div>
  </div>
</div>

<!-- Modal: Settings -->
<div class="modal-overlay" id="settingsModal" style="display:none;">
  <div class="modal-card">
    <h2 class="modal-title">⚙️ User Settings</h2>
    <div class="form-group">
      <label>Change Avatar</label>
      <div class="avatar-grid" id="settingsAvatarGrid"></div>
    </div>
    <div class="form-group">
      <label for="settingsStatus">Status</label>
      <select id="settingsStatus">
        <option value="online">🟢 Online</option>
        <option value="idle">🟡 Idle</option>
        <option value="dnd">🔴 Do Not Disturb</option>
        <option value="offline">⚪ Invisible</option>
      </select>
    </div>
    <div class="form-group">
      <label for="settingsCustomStatus">Custom Status Message</label>
      <input type="text" id="settingsCustomStatus" placeholder="What's on your mind? (max 100 chars)" autocomplete="off" maxlength="100"/>
    </div>
    <div class="modal-buttons">
      <button class="btn-link" onclick="closeSettingsModal()">Cancel</button>
      <button class="btn-primary" onclick="saveSettings()">Save Changes</button>
    </div>
  </div>
</div>

<!-- Modal: Create Channel -->
<div class="modal-overlay" id="channelModal" style="display:none;">
  <div class="modal-card">
    <h2 class="modal-title">➕ Create Channel</h2>
    <div class="form-group">
      <label for="channelName">Channel Name</label>
      <input type="text" id="channelName" placeholder="e.g. support" autocomplete="off"/>
    </div>
    <div class="form-group">
      <label for="channelType">Type</label>
      <select id="channelType">
        <option value="text"># Text Channel</option>
        <option value="voice">🔊 Voice Channel</option>
      </select>
    </div>
    <div class="form-group" style="flex-direction:row; justify-content:space-between; align-items:center;">
      <label for="channelPrivate">Private Channel</label>
      <input type="checkbox" id="channelPrivate" style="width:20px; height:20px; cursor:pointer;"/>
    </div>
    <div class="modal-buttons">
      <button class="btn-link" onclick="closeChannelModal()">Cancel</button>
      <button class="btn-primary" onclick="createChannel()">Create Channel</button>
    </div>
  </div>
</div>

<script>
// ── State ──
let currentRoom = 'general';
let myUsername = 'You';
let myAvatar = '🐼';
let onlineUsers = [];
let roomDescriptions = {
  general: 'Welcome to the general chat',
  gaming: 'Talk about games, find teammates',
  random: 'Off-topic, memes, and random fun',
  Lounge: 'Click to join Lounge voice channel',
  'Gaming Voice': 'Click to join Gaming Voice channel'
};
let lastKnownCounts = {};
let currentView = 'dm'; // Start in Home/DMs view
let eventSource = null;
let currentVoiceRoom = null;
let isMuted = false;
let isDeafened = false;

// Typing states
let typingTimeout = null;
let activeTypingUsers = {}; // username -> timestamp

// Available avatars
const AVAILABLE_AVATARS = ["🦊", "🐼", "🦁", "🐯", "🦉", "🐸", "🐺", "🦋", "🐙", "🦄", "🦅", "🐬"];
let selectedLoginAvatar = "🐼";
let selectedSettingsAvatar = "🐼";

// ── Web Audio click/receive sound ──
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;

function playVoiceJoinSound() {
  try {
    if (!audioCtx) audioCtx = new AudioCtx();
    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.type = 'sine'; osc.frequency.setValueAtTime(392, now);
    osc.frequency.setValueAtTime(523, now + 0.12);
    gain.gain.setValueAtTime(0.0, now);
    gain.gain.linearRampToValueAtTime(0.06, now + 0.04);
    gain.gain.linearRampToValueAtTime(0.06, now + 0.12);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc.start(now); osc.stop(now + 0.35);
  } catch(e) {}
}

function playVoiceLeaveSound() {
  try {
    if (!audioCtx) audioCtx = new AudioCtx();
    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.type = 'sine'; osc.frequency.setValueAtTime(523, now);
    osc.frequency.setValueAtTime(392, now + 0.12);
    gain.gain.setValueAtTime(0.0, now);
    gain.gain.linearRampToValueAtTime(0.06, now + 0.04);
    gain.gain.linearRampToValueAtTime(0.06, now + 0.12);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc.start(now); osc.stop(now + 0.35);
  } catch(e) {}
}

function playReceiveSound() {
  try {
    if (!audioCtx) audioCtx = new AudioCtx();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.type = 'sine'; osc.frequency.setValueAtTime(523, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(784, audioCtx.currentTime + 0.06);
    gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.08);
    osc.start(); osc.stop(audioCtx.currentTime + 0.08);
  } catch(e) {}
}

function playShortBeep(freq, dur) {
  try {
    if (!audioCtx) audioCtx = new AudioCtx();
    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.type = 'sine'; osc.frequency.setValueAtTime(freq, now);
    gain.gain.setValueAtTime(0.03, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + dur);
    osc.start(now); osc.stop(now + dur);
  } catch(e) {}
}

// ── API helper ──
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    const err = await r.json().catch(() => ({error: 'An error occurred'}));
    throw new Error(err.error || 'Server error');
  }
  return r.json();
}

// ── Authentication check ──
async function checkAuth() {
  try {
    const data = await api('/api/auth/me');
    if (data.logged_in) {
      myUsername = data.user.username;
      myAvatar = data.user.avatar;
      
      document.getElementById('footerName').textContent = myUsername;
      document.getElementById('footerAvatar').textContent = myAvatar;
      
      const dot = document.getElementById('footerStatusDot');
      dot.className = 'footer-status-dot ' + data.user.status;
      document.getElementById('footerStatusText').textContent = getStatusLabel(data.user.status);
      
      document.getElementById('loginModal').style.display = 'none';
      
      // Start Real-Time SSE Stream
      connectSSE();
      
      // Load Initial state
      await loadUsers();
      selectView('server'); // Default to server channels on load
      
    } else {
      showLoginModal();
    }
  } catch (e) {
    showLoginModal();
  }
}

function getStatusLabel(st) {
  if (st === 'online') return 'Online';
  if (st === 'idle') return 'Idle';
  if (st === 'dnd') return 'Do Not Disturb';
  return 'Invisible';
}

function showLoginModal() {
  document.getElementById('loginModal').style.display = 'flex';
  const grid = document.getElementById('loginAvatarGrid');
  grid.innerHTML = '';
  AVAILABLE_AVATARS.forEach(emoji => {
    const div = document.createElement('div');
    div.className = 'avatar-grid-item' + (emoji === selectedLoginAvatar ? ' selected' : '');
    div.textContent = emoji;
    div.onclick = () => {
      selectedLoginAvatar = emoji;
      showLoginModal(); // Redraw selection outline
    };
    grid.appendChild(div);
  });
}

async function login() {
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value;
  if (!username) {
    alert("Username cannot be empty");
    return;
  }
  try {
    await api('/api/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username: username, password: password, avatar: selectedLoginAvatar})
    });
    checkAuth();
  } catch (e) {
    alert(e.message);
  }
}

async function logout() {
  try {
    await api('/api/auth/logout', {method: 'POST'});
    if (eventSource) eventSource.close();
    location.reload();
  } catch (e) {
    location.reload();
  }
}

// ── User Settings Modal ──
function openSettingsModal() {
  selectedSettingsAvatar = myAvatar;
  document.getElementById('settingsModal').style.display = 'flex';
  drawSettingsAvatars();
  
  // Set current values
  const dot = document.getElementById('footerStatusDot');
  let currentStatus = 'online';
  if (dot.classList.contains('idle')) currentStatus = 'idle';
  else if (dot.classList.contains('dnd')) currentStatus = 'dnd';
  else if (dot.classList.contains('offline')) currentStatus = 'offline';
  
  document.getElementById('settingsStatus').value = currentStatus;
  
  const userObj = onlineUsers.find(u => u.username === myUsername);
  document.getElementById('settingsCustomStatus').value = userObj ? (userObj.custom_status || '') : '';
}

function drawSettingsAvatars() {
  const grid = document.getElementById('settingsAvatarGrid');
  grid.innerHTML = '';
  AVAILABLE_AVATARS.forEach(emoji => {
    const div = document.createElement('div');
    div.className = 'avatar-grid-item' + (emoji === selectedSettingsAvatar ? ' selected' : '');
    div.textContent = emoji;
    div.onclick = () => {
      selectedSettingsAvatar = emoji;
      drawSettingsAvatars();
    };
    grid.appendChild(div);
  });
}

function closeSettingsModal() {
  document.getElementById('settingsModal').style.display = 'none';
}

async function saveSettings() {
  const status = document.getElementById('settingsStatus').value;
  const customStatus = document.getElementById('settingsCustomStatus').value.trim();
  
  try {
    await api('/api/user/settings', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        status: status,
        custom_status: customStatus,
        avatar: selectedSettingsAvatar
      })
    });
    closeSettingsModal();
    // Profile loads automatically via SSE presence event, but let's refresh locally to be safe
    myAvatar = selectedSettingsAvatar;
    document.getElementById('footerAvatar').textContent = myAvatar;
    document.getElementById('footerStatusDot').className = 'footer-status-dot ' + status;
    document.getElementById('footerStatusText').textContent = getStatusLabel(status);
    loadUsers();
  } catch (e) {
    alert(e.message);
  }
}

// ── Views management (Server Channels vs Home DMs) ──
function selectView(view) {
  currentView = view;
  document.getElementById('navHome').classList.toggle('active', view === 'dm');
  document.getElementById('navServer').classList.toggle('active', view === 'server');
  
  if (view === 'server') {
    document.getElementById('sidebarTitle').textContent = '💬 Channels';
    document.getElementById('btnAddChannel').style.display = 'block';
    loadRooms();
  } else {
    document.getElementById('sidebarTitle').textContent = '📩 Direct Messages';
    document.getElementById('btnAddChannel').style.display = 'none';
    loadDMsList();
  }
}

// ── Channels Loader ──
async function loadRooms() {
  try {
    const data = await api('/api/chat/rooms');
    if (currentView !== 'server') return;
    
    const list = document.getElementById('channelList');
    list.innerHTML = '';
    
    // Sort text rooms first, then voice rooms
    data.rooms.sort((a, b) => {
      const typeA = a.type || 'text';
      const typeB = b.type || 'text';
      if (typeA === 'voice' && typeB !== 'voice') return 1;
      if (typeA !== 'voice' && typeB === 'voice') return -1;
      return a.name.localeCompare(b.name);
    });

    data.rooms.forEach(r => {
      if (r.type === 'dm') return; // DMs handled separately
      
      const isVoice = r.type === 'voice';
      const li = document.createElement('li');
      li.className = 'channel-item-container';
      
      let voiceMembersHtml = '';
      if (isVoice && r.voice_members && r.voice_members.length > 0) {
        voiceMembersHtml = '<ul class="voice-users">';
        r.voice_members.forEach(m => {
          const userObj = onlineUsers.find(u => u.username === m);
          const av = userObj ? userObj.avatar : '👤';
          voiceMembersHtml += `<li class="voice-user-item">
              <span class="v-avatar">${av}</span>
              <span class="v-name">${m}</span>
          </li>`;
        });
        voiceMembersHtml += '</ul>';
      }
      
      const activeClass = (r.name === currentRoom && !isVoice) ? ' active' : '';
      const unread = (lastKnownCounts[r.name] || 0) > 0 && r.name !== currentRoom;
      
      li.innerHTML = `
        <div class="channel-item${activeClass}" onclick="${isVoice ? `joinVoice('${r.name}')` : `switchRoom('${r.name}')`}">
          <span class="hash-icon">${isVoice ? '🔊' : '#'}</span>
          <span>${r.name}</span>
          ${unread ? `<span class="badge">${lastKnownCounts[r.name]}</span>` : ''}
        </div>
        ${voiceMembersHtml}
      `;
      list.appendChild(li);
    });
  } catch (e) {}
}

// ── DMs List Loader ──
async function loadDMsList() {
  try {
    const data = await api('/api/chat/rooms');
    if (currentView !== 'dm') return;
    
    const list = document.getElementById('channelList');
    list.innerHTML = '';
    
    const dmRooms = data.rooms.filter(r => r.type === 'dm');
    if (dmRooms.length === 0) {
      list.innerHTML = '<div class="no-dms">No active conversations. Click a user in the online list to start a DM!</div>';
      return;
    }
    
    dmRooms.forEach(r => {
      const targetUser = getDMTargetName(r.name);
      const userObj = onlineUsers.find(u => u.username === targetUser);
      const av = userObj ? userObj.avatar : '👤';
      const statusCls = userObj ? (userObj.status === 'online' ? 'online' : userObj.status === 'idle' ? 'idle' : userObj.status === 'dnd' ? 'dnd' : 'offline') : 'offline';
      
      const activeClass = r.name === currentRoom ? ' active' : '';
      const unread = (lastKnownCounts[r.name] || 0) > 0 && r.name !== currentRoom;
      
      const li = document.createElement('li');
      li.className = 'channel-item-container';
      li.innerHTML = `
        <div class="channel-item${activeClass}" onclick="switchRoom('${r.name}')">
          <span class="hash-icon">${av}</span>
          <span>${targetUser}</span>
          <span class="dm-status-dot ${statusCls}"></span>
          ${unread ? `<span class="badge">${lastKnownCounts[r.name]}</span>` : ''}
        </div>
      `;
      list.appendChild(li);
    });
  } catch(e) {}
}

function getDMTargetName(roomName) {
  if (!roomName.startsWith('dm__')) return roomName;
  const parts = roomName.substring(4).split('__');
  return parts[0] === myUsername ? parts[1] : parts[0];
}

// ── Online Users Loader ──
async function loadUsers() {
  try {
    const data = await api('/api/chat/users');
    onlineUsers = data.users;
    
    const list = document.getElementById('userList');
    list.innerHTML = '';
    
    // Sort online users first
    const visibleUsers = onlineUsers.filter(u => u.status !== 'offline' && u.status !== 'invisible');
    document.getElementById('onlineCount').textContent = visibleUsers.length;
    
    onlineUsers.forEach(u => {
      // Hide invisible users for others
      if (u.status === 'offline' && u.username !== myUsername) {
        // Just show them offline
      }
      
      const li = document.createElement('li');
      li.className = 'user-item';
      li.onclick = () => startDM(u.username);
      
      const statusCls = u.status === 'online' ? 'online' : u.status === 'idle' ? 'idle' : u.status === 'dnd' ? 'dnd' : 'offline';
      
      li.innerHTML = `
        <span class="u-avatar">${u.avatar}</span>
        <div class="u-info">
          <span class="u-name">${u.username}</span>
          ${u.custom_status ? `<span class="u-custom-status">${escapeHtml(u.custom_status)}</span>` : ''}
        </div>
        <span class="u-status ${statusCls}"></span>
      `;
      list.appendChild(li);
    });
    
    // Redraw list to match avatars/presence
    if (currentView === 'server') loadRooms();
    else loadDMsList();
  } catch(e) {}
}

// ── Switch Rooms ──
function switchRoom(name) {
  currentRoom = name;
  lastKnownCounts[name] = 0;
  
  const isDM = name.startsWith('dm__');
  const dispName = isDM ? getDMTargetName(name) : name;
  
  document.getElementById('topChannelIcon').textContent = isDM ? '👤' : '#';
  document.getElementById('topChannelName').textContent = dispName;
  document.getElementById('topChannelDesc').textContent = roomDescriptions[name] || (isDM ? `Direct messages with ${dispName}` : '');
  document.getElementById('msgInput').placeholder = 'Message ' + (isDM ? '@' : '#') + dispName;
  
  if (isDM) {
    selectView('dm');
  } else {
    selectView('server');
  }
  
  loadMessages(true);
}

// ── Load & Draw Messages ──
let lastUser = null;
async function loadMessages(scroll) {
  try {
    const data = await api('/api/chat/messages?room=' + currentRoom);
    const area = document.getElementById('messagesArea');
    const msgs = data.messages;
    
    const isDM = currentRoom.startsWith('dm__');
    const dispName = isDM ? getDMTargetName(currentRoom) : '#' + currentRoom;
    
    let html = `<div class="welcome-splash">
      <div class="big-hash">${isDM ? '👤' : '#'}</div>
      <h2>Welcome to ${dispName}!</h2>
      <p>${roomDescriptions[currentRoom] || (isDM ? `This is the beginning of your direct message history with ${dispName}.` : 'This is the start of this channel.')}</p>
    </div>`;
    
    lastUser = null;
    msgs.forEach(m => {
      const reactionsHtml = getReactionsHtml(m.id, m.reactions);
      const textHtml = renderMessageText(m.msg);
      
      if (m.user !== lastUser) {
        html += `<div class="msg-group" data-msg-id="${m.id}">
          <div class="msg-avatar">${m.avatar}</div>
          <div class="msg-body">
            <div class="msg-header">
              <span class="msg-user" onclick="startDM('${m.user}')">${m.user}</span>
              <span class="msg-time">${m.ts}</span>
            </div>
            <div class="msg-text">${textHtml}</div>
            <div class="msg-reactions" id="react-${m.id}">${reactionsHtml}</div>
          </div>
          <div class="msg-hover-actions">
            <span onclick="reactMsg('${m.id}', '👍')">👍</span>
            <span onclick="reactMsg('${m.id}', '❤️')">❤️</span>
            <span onclick="reactMsg('${m.id}', '🔥')">🔥</span>
            <span onclick="reactMsg('${m.id}', '😂')">😂</span>
          </div>
        </div>`;
      } else {
        html += `<div class="msg-group" data-msg-id="${m.id}" style="padding-left:56px; padding-top:0; padding-bottom:0;">
          <div class="msg-body">
            <div class="msg-text">${textHtml}</div>
            <div class="msg-reactions" id="react-${m.id}">${reactionsHtml}</div>
          </div>
          <div class="msg-hover-actions">
            <span onclick="reactMsg('${m.id}', '👍')">👍</span>
            <span onclick="reactMsg('${m.id}', '❤️')">❤️</span>
            <span onclick="reactMsg('${m.id}', '🔥')">🔥</span>
            <span onclick="reactMsg('${m.id}', '😂')">😂</span>
          </div>
        </div>`;
      }
      lastUser = m.user;
    });
    
    area.innerHTML = html;
    if (scroll) {
      area.scrollTop = area.scrollHeight;
    }
  } catch (e) {}
}

function appendMessage(m) {
  const area = document.getElementById('messagesArea');
  const reactionsHtml = getReactionsHtml(m.id, m.reactions);
  const textHtml = renderMessageText(m.msg);
  
  let html = '';
  if (m.user !== lastUser) {
    html = `<div class="msg-group new-msg" data-msg-id="${m.id}">
      <div class="msg-avatar">${m.avatar}</div>
      <div class="msg-body">
        <div class="msg-header">
          <span class="msg-user" onclick="startDM('${m.user}')">${m.user}</span>
          <span class="msg-time">${m.ts}</span>
        </div>
        <div class="msg-text">${textHtml}</div>
        <div class="msg-reactions" id="react-${m.id}">${reactionsHtml}</div>
      </div>
      <div class="msg-hover-actions">
        <span onclick="reactMsg('${m.id}', '👍')">👍</span>
        <span onclick="reactMsg('${m.id}', '❤️')">❤️</span>
        <span onclick="reactMsg('${m.id}', '🔥')">🔥</span>
        <span onclick="reactMsg('${m.id}', '😂')">😂</span>
      </div>
    </div>`;
  } else {
    html = `<div class="msg-group new-msg" data-msg-id="${m.id}" style="padding-left:56px; padding-top:0; padding-bottom:0;">
      <div class="msg-body">
        <div class="msg-text">${textHtml}</div>
        <div class="msg-reactions" id="react-${m.id}">${reactionsHtml}</div>
      </div>
      <div class="msg-hover-actions">
        <span onclick="reactMsg('${m.id}', '👍')">👍</span>
        <span onclick="reactMsg('${m.id}', '❤️')">❤️</span>
        <span onclick="reactMsg('${m.id}', '🔥')">🔥</span>
        <span onclick="reactMsg('${m.id}', '😂')">😂</span>
      </div>
    </div>`;
  }
  lastUser = m.user;
  
  const div = document.createElement('div');
  div.innerHTML = html;
  area.appendChild(div.firstChild);
  area.scrollTop = area.scrollHeight;
  
  if (m.user !== myUsername) {
    playReceiveSound();
  }
}

function escapeHtml(t) {
  const d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}

function renderMessageText(text) {
  const escaped = escapeHtml(text);
  const imgRegex = /(https?:\/\/\S+\.(?:png|jpg|jpeg|gif|webp|svg)(?:\?\S+)?)/gi;
  if (imgRegex.test(text)) {
    return escaped.replace(imgRegex, (match) => {
      return `<div class="msg-attachment"><img src="${match}" alt="attachment" onload="scrollToBottom()"/></div>`;
    });
  }
  return escaped;
}

function scrollToBottom() {
  const area = document.getElementById('messagesArea');
  area.scrollTop = area.scrollHeight;
}

// ── Reactions Renderer & Handler ──
function getReactionsHtml(msgId, reactions) {
  if (!reactions) return '';
  let html = '';
  Object.entries(reactions).forEach(([emoji, users]) => {
    if (!users || users.length === 0) return;
    const isActive = users.includes(myUsername) ? ' active' : '';
    html += `<span class="reaction-badge${isActive}" onclick="reactMsg('${msgId}', '${emoji}')" title="${users.join(', ')}">
      ${emoji} <span class="count">${users.length}</span>
    </span>`;
  });
  return html;
}

function updateReactionsUI(msgId, reactions) {
  const el = document.getElementById(`react-${msgId}`);
  if (el) {
    el.innerHTML = getReactionsHtml(msgId, reactions);
  }
}

async function reactMsg(msgId, emoji) {
  try {
    await api('/api/chat/react', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({room: currentRoom, msg_id: msgId, emoji: emoji})
    });
  } catch(e) {}
}

// ── Send Message ──
async function sendMessage() {
  const input = document.getElementById('msgInput');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  
  try {
    await api('/api/chat/messages', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({room: currentRoom, msg: msg})
    });
  } catch(e) {
    alert(e.message);
  }
}

function attachImage() {
  const url = prompt("Enter an image URL to attach:");
  if (url && url.startsWith('http')) {
    const input = document.getElementById('msgInput');
    input.value = (input.value + " " + url).trim();
    input.focus();
  }
}

// ── Typing Indicator systems ──
function handleTyping() {
  if (typingTimeout) clearTimeout(typingTimeout);
  
  // Send typing notify to server every 2 seconds
  if (!typingTimeout) {
    api('/api/chat/typing', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({room: currentRoom})
    });
  }
  
  typingTimeout = setTimeout(() => {
    typingTimeout = null;
  }, 2000);
}

function updateTypingDisplay() {
  const ind = document.getElementById('typingIndicator');
  const now = Date.now();
  
  // Prune expired typing status
  const typers = [];
  Object.entries(activeTypingUsers).forEach(([uname, ts]) => {
    if (now - ts < 3000) {
      typers.push(uname);
    }
  });
  
  if (typers.length === 0) {
    ind.innerHTML = '';
  } else if (typers.length === 1) {
    ind.innerHTML = `<span class="typing-dots"><span>●</span><span>●</span><span>●</span></span> <strong>${typers[0]}</strong> is typing...`;
  } else if (typers.length === 2) {
    ind.innerHTML = `<span class="typing-dots"><span>●</span><span>●</span><span>●</span></span> <strong>${typers[0]}</strong> and <strong>${typers[1]}</strong> are typing...`;
  } else {
    ind.innerHTML = `<span class="typing-dots"><span>●</span><span>●</span><span>●</span></span> Multiple users are typing...`;
  }
}

// Check and update typing indicators periodically
setInterval(updateTypingDisplay, 1000);

// ── DMs Room Launcher ──
async function startDM(username) {
  if (username === myUsername) return;
  try {
    const res = await api('/api/chat/dm/room', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({target: username})
    });
    
    // Add description
    roomDescriptions[res.room_name] = `Direct messages with ${username}`;
    
    switchRoom(res.room_name);
  } catch (e) {
    alert(e.message);
  }
}

// ── Voice channels systems ──
async function joinVoice(roomName) {
  if (currentVoiceRoom === roomName) return;
  try {
    await api('/api/chat/voice/join', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({room: roomName})
    });
    currentVoiceRoom = roomName;
    playVoiceJoinSound();
    
    // Draw Voice Panel
    document.getElementById('voiceRoomName').textContent = roomName;
    document.getElementById('voicePanel').style.display = 'flex';
    
    loadRooms();
  } catch (e) {
    alert(e.message);
  }
}

async function leaveVoice() {
  if (!currentVoiceRoom) return;
  try {
    await api('/api/chat/voice/leave', {method: 'POST'});
    currentVoiceRoom = null;
    playVoiceLeaveSound();
    
    document.getElementById('voicePanel').style.display = 'none';
    loadRooms();
  } catch(e) {}
}

function toggleMute() {
  isMuted = !isMuted;
  const btn = document.getElementById('btnMute');
  btn.classList.toggle('active', isMuted);
  playShortBeep(isMuted ? 550 : 650, 0.05);
}

function toggleDeafen() {
  isDeafened = !isDeafened;
  const btn = document.getElementById('btnDeafen');
  btn.classList.toggle('active', isDeafened);
  
  if (isDeafened && !isMuted) {
    toggleMute();
  } else if (!isDeafened && isMuted) {
    toggleMute();
  }
  playShortBeep(isDeafened ? 450 : 750, 0.05);
}

// ── Create Channel ──
function openChannelModal() {
  document.getElementById('channelModal').style.display = 'flex';
}
function closeChannelModal() {
  document.getElementById('channelModal').style.display = 'none';
}
async function createChannel() {
  const name = document.getElementById('channelName').value.trim();
  const type = document.getElementById('channelType').value;
  const isPrivate = document.getElementById('channelPrivate').checked;
  if (!name) {
    alert("Channel name is required");
    return;
  }
  try {
    await api('/api/chat/rooms', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: name, type: type, private: isPrivate})
    });
    closeChannelModal();
    document.getElementById('channelName').value = '';
    document.getElementById('channelPrivate').checked = false;
  } catch (e) {
    alert(e.message);
  }
}

// ── SSE Real-Time Stream Event Listener ──
function connectSSE() {
  if (eventSource) {
    eventSource.close();
  }
  eventSource = new EventSource('/api/chat/stream');
  
  eventSource.onmessage = function(event) {
    const pkt = JSON.parse(event.data);
    if (pkt.event === 'ping') return;
    
    const d = pkt.data;
    if (pkt.event === 'message') {
      if (d.room === currentRoom) {
        appendMessage(d.message);
      } else {
        lastKnownCounts[d.room] = (lastKnownCounts[d.room] || 0) + 1;
        if (currentView === 'server') loadRooms();
        else loadDMsList();
      }
    } else if (pkt.event === 'typing') {
      if (d.room === currentRoom && d.user !== myUsername) {
        activeTypingUsers[d.user] = Date.now();
        updateTypingDisplay();
      }
    } else if (pkt.event === 'presence') {
      loadUsers();
    } else if (pkt.event === 'room_created') {
      roomDescriptions[d.room.name] = d.description;
      if (currentView === 'server') loadRooms();
    } else if (pkt.event === 'reaction') {
      if (d.room === currentRoom) {
        updateReactionsUI(d.msg_id, d.reactions);
      }
    } else if (pkt.event === 'voice_update') {
      loadRooms();
    }
  };
  
  eventSource.onerror = function() {
    console.log("SSE Connection lost. Reconnecting...");
    setTimeout(connectSSE, 3000);
  };
}

// ── Init ──
document.getElementById('msgInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Run auth check
checkAuth();

</script>
</body>
</html>
"""

# ── Flask Routes ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    avatar = data.get("avatar", "🐼")
    
    if not username:
        return jsonify({"error": "Username cannot be empty"}), 400
        
    with chat_lock:
        user = global_users.get(username)
        if user:
            if password and user.pw_hash:
                if not user.verify(password):
                    return jsonify({"error": "Incorrect password"}), 401
            elif user.pw_hash:
                return jsonify({"error": "Password required for this user"}), 401
            
            user.status = "online"
            if avatar:
                user.avatar = avatar
        else:
            user = UserProfile(username, password)
            if avatar:
                user.avatar = avatar
            global_users[username] = user
            
            # Join general automatically
            if "general" in chat_rooms:
                chat_rooms["general"].members.add(username)
        
        session["username"] = username
        
    broadcast_sse("presence", {
        "username": username,
        "avatar": user.avatar,
        "status": "online",
        "custom_status": getattr(user, "custom_status", "")
    })
    
    return jsonify({"ok": True, "user": user.info()})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    username = session.pop("username", None)
    if username:
        with chat_lock:
            user = global_users.get(username)
            if user:
                user.status = "offline"
        broadcast_sse("presence", {
            "username": username,
            "status": "offline"
        })
    return jsonify({"ok": True})


@app.route("/api/auth/me")
def api_me():
    username = session.get("username")
    if not username:
        return jsonify({"logged_in": False}), 401
    with chat_lock:
        user = global_users.get(username)
        if not user:
            session.pop("username", None)
            return jsonify({"logged_in": False}), 401
        return jsonify({"logged_in": True, "user": user.info()})


@app.route("/api/user/settings", methods=["POST"])
def api_user_settings():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    custom_status = data.get("custom_status")
    avatar = data.get("avatar")
    
    with chat_lock:
        user = global_users.get(username)
        if not user:
            return jsonify({"error": "User not found"}), 404
        if status in ("online", "idle", "dnd", "offline"):
            user.status = status
        if custom_status is not None:
            user.custom_status = custom_status[:100]
        if avatar:
            user.avatar = avatar
            
    broadcast_sse("presence", {
        "username": username,
        "avatar": user.avatar,
        "status": user.status,
        "custom_status": getattr(user, "custom_status", "")
    })
    return jsonify({"ok": True, "user": user.info()})


@app.route("/api/chat/rooms", methods=["GET", "POST"])
def api_rooms_route():
    username = session.get("username")
    if request.method == "POST":
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        room_name = data.get("name", "").strip()
        is_private = data.get("private", False)
        room_type = data.get("type", "text")
        
        if not room_name:
            return jsonify({"error": "Channel name cannot be empty"}), 400
            
        room_name = "".join(c for c in room_name if c.isalnum() or c in "-_ ")
        if not room_name:
            return jsonify({"error": "Invalid channel name"}), 400
            
        with chat_lock:
            if room_name in chat_rooms:
                return jsonify({"error": f"Channel '{room_name}' already exists"}), 400
            room = ChatRoom(room_name, username, is_private)
            room.type = room_type
            room.members.add(username)
            chat_rooms[room_name] = room
            desc = f"Welcome to the {room_name} channel!"
            if room_type == "voice":
                desc = f"Simulated voice connection room."
            ROOM_DESCRIPTIONS[room_name] = desc
            
        broadcast_sse("room_created", {
            "room": room.info(),
            "description": desc
        })
        return jsonify({"ok": True, "room": room.info()})
        
    else:
        with chat_lock:
            rooms = []
            for name, room in chat_rooms.items():
                info = room.info()
                info["description"] = ROOM_DESCRIPTIONS.get(name, "")
                
                # Filter private rooms and DMs
                if info.get("is_private") or getattr(room, "type", "text") == "dm":
                    if not username or username not in room.members:
                        continue
                rooms.append(info)
        return jsonify({"rooms": rooms})


@app.route("/api/chat/dm/room", methods=["POST"])
def api_dm_room():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    target = data.get("target")
    if not target or target not in global_users:
        return jsonify({"error": "User not found"}), 404
        
    room_name = f"dm__{'__'.join(sorted([username, target]))}"
    with chat_lock:
        if room_name not in chat_rooms:
            room = ChatRoom(room_name, "system", is_private=True)
            room.type = "dm"
            room.members.update([username, target])
            chat_rooms[room_name] = room
            ROOM_DESCRIPTIONS[room_name] = f"Direct Messages with {target}"
        else:
            room = chat_rooms[room_name]
            
    return jsonify({"ok": True, "room_name": room_name})


@app.route("/api/chat/messages", methods=["GET", "POST"])
def api_messages_route():
    username = session.get("username")
    if request.method == "POST":
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        room_name = data.get("room", "general")
        msg = data.get("msg", "").strip()
        
        if not msg:
            return jsonify({"error": "Empty message"}), 400
            
        with chat_lock:
            room = chat_rooms.get(room_name)
            if not room:
                return jsonify({"error": f"Room '{room_name}' not found"}), 404
            if getattr(room, "is_private", False) or getattr(room, "type", "text") == "dm":
                if username not in room.members:
                    return jsonify({"error": "Access denied"}), 403
                    
            room.add_message(username, msg)
            if username in global_users:
                global_users[username].msg_count += 1
                
        # Handle bot replies
        if not room_name.startswith("dm__"):
            _schedule_bot_reply(room_name)
        else:
            bot_target = get_dm_bot_target(room_name, username)
            if bot_target:
                _schedule_bot_dm_reply(room_name, bot_target)
                
        return jsonify({"ok": True, "room": room_name})
        
    else:
        room_name = request.args.get("room", "general")
        with chat_lock:
            room = chat_rooms.get(room_name)
            if not room:
                return jsonify({"error": f"Room '{room_name}' not found"}), 404
            if getattr(room, "is_private", False) or getattr(room, "type", "text") == "dm":
                if not username or username not in room.members:
                    return jsonify({"error": "Access denied"}), 403
            
            messages = []
            for e in room.get_recent(50):
                messages.append({
                    "id": e["id"],
                    "ts": e["ts"],
                    "user": e["user"],
                    "msg": e["msg"],
                    "avatar": e.get("avatar", "🐼"),
                    "reactions": e.get("reactions", {})
                })
        return jsonify({"messages": messages, "room": room_name})


@app.route("/api/chat/react", methods=["POST"])
def api_react():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    room_name = data.get("room", "general")
    msg_id = data.get("msg_id")
    emoji = data.get("emoji")
    
    if not msg_id or not emoji:
        return jsonify({"error": "Missing parameters"}), 400
        
    with chat_lock:
        room = chat_rooms.get(room_name)
        if not room:
            return jsonify({"error": f"Room '{room_name}' not found"}), 404
            
        msg_found = None
        for m in room.history:
            if m["id"] == msg_id:
                msg_found = m
                break
                
        if not msg_found:
            return jsonify({"error": "Message not found"}), 404
            
        reactions = msg_found.setdefault("reactions", {})
        user_list = reactions.setdefault(emoji, [])
        if username in user_list:
            user_list.remove(username)
            if not user_list:
                del reactions[emoji]
        else:
            user_list.append(username)
            
        broadcast_sse("reaction", {
            "room": room_name,
            "msg_id": msg_id,
            "reactions": reactions
        })
        
    return jsonify({"ok": True})


@app.route("/api/chat/typing", methods=["POST"])
def api_typing():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    room_name = data.get("room", "general")
    broadcast_sse("typing", {"room": room_name, "user": username})
    return jsonify({"ok": True})


@app.route("/api/chat/voice/join", methods=["POST"])
def api_voice_join():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    room_name = data.get("room")
    
    with chat_lock:
        # Leave previous voice room
        for rname, room in chat_rooms.items():
            v_m = getattr(room, "voice_members", set())
            if username in v_m:
                v_m.remove(username)
                broadcast_sse("voice_update", {
                    "room": rname,
                    "voice_members": list(v_m),
                    "user_left": username
                })
                
        room = chat_rooms.get(room_name)
        if not room or getattr(room, "type", "text") != "voice":
            return jsonify({"error": "Voice channel not found"}), 404
            
        v_m = getattr(room, "voice_members", set())
        v_m.add(username)
        room.voice_members = v_m
        
    broadcast_sse("voice_update", {
        "room": room_name,
        "voice_members": list(v_m),
        "user_joined": username
    })
    return jsonify({"ok": True, "voice_members": list(v_m)})


@app.route("/api/chat/voice/leave", methods=["POST"])
def api_voice_leave():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
        
    with chat_lock:
        left_room = None
        for rname, room in chat_rooms.items():
            v_m = getattr(room, "voice_members", set())
            if username in v_m:
                v_m.remove(username)
                left_room = rname
                broadcast_sse("voice_update", {
                    "room": rname,
                    "voice_members": list(v_m),
                    "user_left": username
                })
                break
                
    return jsonify({"ok": True, "left_room": left_room})


@app.route("/api/chat/users")
def api_users():
    users = []
    with chat_lock:
        for name, user in global_users.items():
            users.append(user.info())
    return jsonify({"users": users})


@app.route("/api/chat/stream")
def api_chat_stream():
    q = queue.Queue(maxsize=100)
    with sse_lock:
        sse_listeners.append(q)
        
    def event_generator():
        try:
            while True:
                try:
                    data = q.get(timeout=15.0)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield f"data: {json.dumps({'event': 'ping'})}\n\n"
        except GeneratorExit:
            pass
        finally:
            with sse_lock:
                if q in sse_listeners:
                    sse_listeners.remove(q)
                    
    return Response(event_generator(), mimetype="text/event-stream")


ROOM_DESCRIPTIONS = {
    "general": "Welcome to the general chat",
    "gaming": "Talk about games, find teammates",
    "random": "Off-topic, memes, and random fun",
    "Lounge": "Simulated voice connection room.",
    "Gaming Voice": "Simulated voice connection room."
}


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
