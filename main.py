from langchain_ollama import OllamaLLM                 # essential to use local chatbot
from langchain_core.prompts import ChatPromptTemplate  # other ai stuff
from langchain_community.chat_models import ChatOllama # stream chatbot message
from colorama import Fore, Back, Style                 # colorize messages for differentiation
import subprocess                                      # execute terminal commands
import lxml.etree as ET                                # parse chat history
import html                                            # for html.escape()
import curses                                          # user interface
import threading                                       # run ui and bot in parallel
import time                                            # time delay for ui
import random                                          # edgy animations

# global variables

chatbot_template = """
    You are {chatbot_name}, a helpful AI assistant with access to a Linux terminal running Arch Linux.

    ### Execution Rules:
    1. **You can only execute a command by sending a message to the terminal** in this format:  
    `<message from='{chatbot_name}' to='{terminal_name}'>your_command</message>`

    2. **You must wait for the terminal's response before proceeding.**  
    - Do not assume a command has been executed until you receive its output.  
    - Only take further action once you have processed the terminal's response.

    3. **You may only respond to the user when the task is fully completed.**  
    - If a task requires multiple steps, you must finish all steps before messaging the user.  
    - Format your response like this:  
        `<message from='{chatbot_name}' to='{user_name}'>your_response</message>`  
    - Do not send partial updates or ask unnecessary questions before finishing the task.

    4. **Before executing a command or responding, you must first think.**  
    - Format your internal thoughts like this:  
        `<message from='{chatbot_name}' to='{chatbot_name}'>your_thoughts</message>`

    5. **You can not write anything outside of tags.**  

    ### Context:
    {history}

    ### Last message:
    {message}

    ### Your next action:
"""

# utility functions

def equalize(some_string, n):
    if len(some_string) > n:
        return some_string[:n]
    else:
        return some_string + (n - len(some_string)) * ' '

def edgy_string(base_string):
    if base_string is None:
        return None
    base_string_letters = list(base_string)
    l = len(base_string_letters)
    base_string_letters += [chr(random.randrange(33,126)) for _ in range(0, random.randrange(0, int(50*(0.97**l))))]
    for i in range(0, l):
        if random.uniform(0, 1) < (i/l)**4:
            base_string_letters[i] = random.choice(base_string_letters)
    return "".join(base_string_letters)

# classes

class Ui:
    def __init__(self, chat, stdscr):
        """Initialize UI with curses settings and chat instance."""
        self.input_mode = False
        self.chat = chat
        self.input_str = ""
        self.n = None
        self.stdscr = stdscr
    
    def load(self):
        curses.curs_set(1)

        # Initialize terminal colors
        curses.start_color()
        for n, chat_client in enumerate(self.chat.chat_clients):
            curses.init_pair(n+1, chat_client.foreground_color, chat_client.background_color)
        
        # Initialize windows
        self.height, self.width = self.stdscr.getmaxyx()
        self.box = curses.newwin(self.height-3, self.width, 0, 0)
        self.input_win = curses.newwin(3, self.width, self.height-3, 0)


    def update(self):
        """Update UI with chat messages and user input."""
        self.box.clear()
        self.box.border()

        # add messages to chat

        y_offset = 1

        # add unfinished message

        unfinished_messages = self.chat.unfinished_messages()
        if len(unfinished_messages) > 0:
            y_offset = self.add_message(y_offset, unfinished_messages[0])

        for message in reversed(self.chat.history.messages):
            y_offset = self.add_message(y_offset, message)
        
        self.box.refresh()
        self.input_win.clear()
        self.input_win.border()
        self.input_win.addstr(1, 2, "You: " + self.input_str[:self.width-8], curses.color_pair(1))
        self.input_win.refresh()

        if self.input_mode:
            key = self.input_win.getch()
            if key == 10:  # Enter key
                self.input_mode = False
            elif key in (127, 8, curses.KEY_BACKSPACE):  # Backspace key
                self.input_str = self.input_str[:-1]
            elif 32 <= key <= 126 and len(self.input_str) < self.width-8:  # Printable characters, limit input width
                self.input_str += chr(key)
        
        time.sleep(0.1)  # Small delay to allow UI updates
    
    def add_message(self, y_offset, message):

        # handle message info

        message_sender_name = "" if message.sender is None else message.sender.name
        message_receiver_name = self.animation_circle() if message.receiver is None else message.receiver.name
        message_content = self.animation_circle() if message.content is None else message.content
        index = self.chat.chat_clients.index(message.sender) + 1 if message.sender in self.chat.chat_clients else 1

        color = curses.color_pair(index)
        indicator = f"[{equalize(message_sender_name, 10)}  => {equalize(message_receiver_name, 10)}]: "
        full_text = indicator + message_content
        lines = [full_text[i:i+self.width-4] for i in range(0, len(full_text), self.width-4)]
        
        # add message to list
        for line in lines:
            if y_offset < self.height - 4:
                try:
                    self.box.addstr(self.height-y_offset-4, 2, line, color)
                except curses.error:
                    pass  # Ignore errors if writing out of bounds
                y_offset += 1
        return y_offset

    def run(self):
        self.n = 0
        while True:
            self.n += 1
            self.update()
    
    # animations
    
    def animation_spinner(self):
        return "|/-\\"[self.n%4]
    
    def animation_cross(self):
        return "┤ ┘ ┴ └ ├ ┌ ┬ ┐"[(self.n%8)*2] # *2 because unicode is weird
    
    def animation_clock(self):
        return "← ↖ ↑ ↗ → ↘ ↓ ↙"[(self.n%8)*2] # *2 because unicode is weird
    
    def animation_dots(self):
        l = 5
        out = l * [' ']
        out[(self.n//2)%l] = '.'
        return "".join(out)
    
    def animation_circle(self):
        return "◴ ◷ ◶ ◵"[(self.n%4)*2] # *2 because unicode is weird
    
    def animation_bounce(self):
        return ".oOo"[int(self.n%4)]
    
    def animation_chat_clients(self):
        return list(map(lambda chat_client: chat_client.name, self.chat.chat_clients))[self.n % len(self.chat.chat_clients)]

class ChatServer:

    def __init__(self):

        # set values
        self.chat_clients = []
        self.history = ChatHistory([])
        #self.history = ChatHistory.load(self)

        # give parent element reference to children
        for chat_client in self.chat_clients:
            chat_client.chat = self
    
    def unfinished_messages(self):
        return [chat_client.unfinished_message() for chat_client in self.chat_clients if chat_client.inbox_content != ""]
    
    def get_chat_client_by_name(self, chat_client_name):
        try:
            return next(chat_client for chat_client in self.chat_clients if chat_client.name == chat_client_name)
        except:
            return None

    def get_index_by_name(self, name):
        pass

    def add_client(self, name, fg_color, bg_color, on_receive):
        chat_client = ChatClient(
            name = name,
            fg_color = fg_color,
            bg_color = bg_color,
            chat = self,
            on_receive = on_receive
        )
        self.chat_clients.append(chat_client)
        return chat_client
    
    def load_history(self):
        self.history = ChatHistory.load(self)
    
    def run(self):
        chatbot_client = self.chat_clients[2]
        user_client = self.chat_clients[0]
        chatbot_client.update_message(user_client, "hello there")
        chatbot_client.send_message()

# ---------------------- Message Class ---------------------- #

class Message:

    def __init__(self, content, sender, receiver, chat):
        self.content = content
        self.sender = sender
        self.receiver = receiver
        self.chat = chat
    
    @staticmethod
    def from_xml_object(xml_object, chat):
        return Message(
            xml_object.text,
            chat.get_chat_client_by_name(xml_object.get("from")),
            chat.get_chat_client_by_name(xml_object.get("to")),
            chat)
    
    @staticmethod
    def from_xml_string(raw_response, chat):
                # in case of correct xml
        # -------------------------------------------------------
        try:
            return Message.from_xml_object(ET.fromstring(raw_response), chat)
        except ET.ParseError:
            pass
        # in case of xml fragment
        # -------------------------------------------------------
        try:
            return Message.from_xml_object(ET.fromstring(f"<chat>{raw_response}</chat>").find("message"), chat)
        except ET.ParseError:
            pass
        except IndexError:
            pass
        # in case of unfinished response
        # -------------------------------------------------------
        try:
            return Message.from_xml_object(ET.fromstring(f"<chat>{raw_response}</message></chat>").find("message"), chat)
        except ET.ParseError:
            pass
        except IndexError:
            pass
        # in case of error.
        # -------------------------------------------------------
        return Message(None, None, None, chat)

    def to_xml_object(self):
        xml_object = ET.Element("message")
        xml_object.text = self.content
        if self.receiver.name is not None:
            xml_object.set("to", self.receiver.name)
        if self.sender.name is not None:
            xml_object.set("from", self.sender.name)
        return xml_object

    def to_xml_string(self):
        return ET.tostring(self.to_xml_object())

class ChatHistory:

    def __init__(self, messages):
        self.messages = messages
    
    def save(self):
        with open("chat_log.xml", "wb") as f:
            f.write(self.to_xml_string())

    @staticmethod
    def load(chat):
        try:
            return ChatHistory.from_xml_object(ET.parse('chat_log.xml'), chat)
        except ET.ParseError:
            A = chat.chat_clients[0]
            B = chat.chat_clients[1]
            return ChatHistory([Message(f"hello, i'm {A.name}. how can i assist you?", A, B, chat)])
    
    @staticmethod
    def from_xml_object(xml_object, chat):
        return ChatHistory([Message.from_xml_object(message, chat) for message in list(xml_object.iter())][1:]) # [1:] because first message is empty for some reason.

    @staticmethod
    def from_xml_string(xml_text):
        return ChatHistory.from_xml_object(ET.fromstring(xml_text))

    def to_xml_object(self):
        xml_object = ET.Element("chat")
        for message in self.messages:
            xml_object.append(message.to_xml_object())
        return xml_object
        
    def to_xml_string(self):
        return ET.tostring(self.to_xml_object())
    
    def append(self, sender, receiver, content):
        self.messages.append(Message(content, sender, receiver, self))
        #self.save()

# ---------------------- ChatClient Class ---------------------- #

class ChatClient:
    def __init__(self, name, fg_color, bg_color, chat, on_receive):
        self.chat = chat
        self.name = name
        self.foreground_color = fg_color
        self.background_color = bg_color
        self.inbox_content = ""
        self.inbox_receiver = None
        self.on_receive = on_receive
    
    def send_message(self):
        message_receiver = self.inbox_receiver
        message_content = self.inbox_content
        self.chat.history.append(self, message_receiver, message_content)
        self.inbox_content = ""
        self.inbox_receiver = None
        message_receiver.on_receive(message_receiver, self, message_content)
    
    def update_message(self, other, content):
        self.inbox_receiver = other
        self.inbox_content = content
    
    def unfinished_message(self):
        return Message(self.inbox_content, self, self.inbox_receiver, self.chat)

# ---------------------- ChatAgent Base Class ---------------------- #

class ChatAgent():

    def __init__(self, name = "chat agent", fg_color = curses.COLOR_WHITE, bg_color = curses.COLOR_BLACK, chat = None):
        agent_instance = self
        self.client = chat.add_client(
            name=name,
            fg_color=fg_color,
            bg_color=bg_color,
            on_receive = lambda self, other, content: agent_instance.receive_message(other, content))
    
    def receive_message(self, other, content):
        time.sleep(1)
        self.client.update_message(other, f"hi, i'm {self.client.name}")
        self.client.send_message()

# ---------------------- Chatbot Class ---------------------- #

class Chatbot(ChatAgent):
    def __init__(self, chat, name, user, terminal, model):
        super().__init__(name=name, fg_color=curses.COLOR_MAGENTA, chat=chat)
        self.model = ChatOllama(model=model, streaming=True)
        self.prompt = ChatPromptTemplate.from_template(chatbot_template)
        self.chain = self.prompt | self.model
        self.user = user
        self.terminal = terminal

    def receive_message(self, other, content):
        """Process user messages and generate AI responses."""
        message = Message(content, self.client, other, self.client.chat)

        raw_response = ""
        for chunk in self.chain.stream({
            "chatbot_name": self.client.name,
            "user_name": self.user.name,
            "terminal_name": self.terminal.name,
            "history": self.client.chat.history.to_xml_string(),
            "message": message.to_xml_string()
                }):
            raw_response += chunk.content
            parsed_response = Message.from_xml_string(raw_response, self.client.chat)

            if parsed_response.content is not None:
                self.client.update_message(parsed_response.receiver, edgy_string(parsed_response.content))
        
        parsed_response = Message.from_xml_string(raw_response, self.client.chat)
        self.client.update_message(parsed_response.receiver, parsed_response.content)
        self.client.send_message()

# ---------------------- User Class ---------------------- #

class User(ChatAgent):
    def __init__(self, chat, name, ui):
        super().__init__(name="user", fg_color=curses.COLOR_WHITE, chat=chat)
        self.name="asdf"
        self.ui = ui
    
    def receive_message(self, other, content):
        self.ui.input_mode = True
        while self.ui.input_mode:
            time.sleep(0.1)
            self.client.update_message(other, self.ui.input_str)
        self.ui.input_str = ""
        self.client.send_message()

# ---------------------- Terminal Class ---------------------- #

class Terminal(ChatAgent):
    def __init__(self, chat):
        super().__init__(name="terminal", fg_color=curses.COLOR_GREEN, chat=chat)
    
    def receive_message(self, other, content):
        proc = subprocess.Popen([content], stdout=subprocess.PIPE, shell=True)
        out, err = proc.communicate()
        self.client.update_message(other, f"output: '{out}', errors: '{err}'")
        self.client.send_message()

# ---------------------- Main Function ---------------------- #

def main(stdscr):

    chat_server = ChatServer()
    ui = Ui(chat_server, stdscr)

    user = User(chat_server, "user", ui)
    terminal = Terminal(chat_server)
    chatbot = Chatbot(chat_server, "chatbot", user.client, terminal.client, "gemma3")

    #user.client.update_message(chatbot.client, "hello there")
    #user.client.send_message()

    ui.load()

    chat_thread=threading.Thread(target=chat_server.run, args=())
    ui_thread=threading.Thread(target=ui.run, args=())

    chat_thread.start()
    ui_thread.start()

    chat_thread.join()
    ui_thread.join()

    time.sleep(100)

curses.wrapper(main)