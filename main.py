#!/usr/bin/env python3

"""
This module creates a simple chat framework with a UI and chat agents that interact with each other.
It uses curses for the UI, executes terminal commands via a Terminal agent,
and generates AI responses using a Chatbot agent powered by a local model.
"""

import curses
import subprocess
import threading
import time
import random
import html
import lxml.etree as ET

from colorama import Fore, Back, Style  # Colorize terminal messages
from langchain_ollama import OllamaLLM  # Local chatbot model
from langchain_core.prompts import ChatPromptTemplate  # Chat prompt template
from langchain_community.chat_models import ChatOllama  # Chat model for streaming responses


# ------------------------------------------------------------------------------
# Chatbot Prompt Template
# ------------------------------------------------------------------------------

CHATBOT_PROMPT_TEMPLATE = """
You are {chatbot_name}, a helpful AI assistant with access to a Linux terminal running Arch Linux.

### Execution Rules:
1. **Command Execution:**  
   You can only execute a command by sending a message to the terminal using the format:  
   `<message from='{chatbot_name}' to='{terminal_name}'>your_command</message>`

2. **Response Waiting:**  
   You must wait for the terminal's response before proceeding.  
   Do not assume a command has executed until you receive its output.  
   Only act after processing the terminal's response.

3. **Complete Tasks:**  
   You may only respond to the user once the task is fully completed.  
   For multi-step tasks, finish all steps before messaging the user.  
   Format your response as:  
   `<message from='{chatbot_name}' to='{user_name}'>your_response</message>`  
   Avoid sending partial updates or unnecessary questions.

4. **Internal Reasoning:**  
   Before executing a command or responding, you must first think.  
   Format internal thoughts as:  
   `<message from='{chatbot_name}' to='{chatbot_name}'>your_thoughts</message>`

5. **Tag Confinement:**  
   Do not write anything outside of the specified tags.

### Context:
{history}

### Last Message:
{message}

### Your Next Action:
"""


# ------------------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------------------

def pad_string(text, length):
    """
    Pads or truncates the given text to exactly 'length' characters.
    """
    if len(text) > length:
        return text[:length]
    return text + (' ' * (length - len(text)))


def generate_edgy_text(base_text):
    """
    Generates a modified version of base_text by randomly inserting characters
    and randomly replacing characters based on a probability that increases with the character's position.
    """
    if base_text is None:
        return None
    text_chars = list(base_text)
    text_length = len(text_chars)
    
    # Append a random number of random ASCII characters
    extra_chars = [chr(random.randrange(33, 126)) for _ in range(random.randrange(0, int(50 * (0.97 ** text_length))))]
    text_chars += extra_chars
    
    # Randomly replace some characters based on position probability
    for i in range(text_length):
        if random.uniform(0, 1) < (i / text_length) ** 4:
            text_chars[i] = random.choice(text_chars)
    
    return "".join(text_chars)


# ------------------------------------------------------------------------------
# UI Class
# ------------------------------------------------------------------------------

class ChatUI:
    """
    The ChatUI class manages the curses-based terminal user interface.
    It handles drawing chat messages and capturing user input.
    """

    def __init__(self, chat_server, stdscr, client):
        """
        Initialize the UI with the chat server instance, the curses standard screen,
        and the associated client.
        """
        self.chat_server = chat_server
        self.stdscr = stdscr
        self.client = client
        self.input_mode = False
        self.client.inbox_text = ""
        self.tick = 0

        # Configure curses settings
        curses.curs_set(1)
        curses.start_color()

        # Initialize color pairs for each chat client
        for idx, chat_client in enumerate(self.chat_server.chat_clients):
            curses.init_pair(idx + 1, chat_client.foreground_color, chat_client.background_color)

        # Setup windows for chat display and input area
        self.height, self.width = self.stdscr.getmaxyx()
        self.chat_win = curses.newwin(self.height - 3, self.width, 0, 0)
        self.input_win = curses.newwin(3, self.width, self.height - 3, 0)

    def update_ui(self):
        """
        Refresh the UI windows with the latest chat messages and user input.
        """
        self.chat_win.clear()
        self.chat_win.border()

        y_offset = 1

        # Display unfinished messages
        for message in self.chat_server.get_unfinished_messages():
            y_offset = self.display_message(y_offset, message)

        # Display chat history in reverse order
        for msg in reversed(self.chat_server.history.messages):
            y_offset = self.display_message(y_offset, msg)

        self.chat_win.refresh()

        # Update input window
        self.input_win.clear()
        self.input_win.border()
        input_display = "You: " + self.client.inbox_text[:self.width - 8]
        self.input_win.addstr(1, 2, input_display, curses.color_pair(1))
        self.input_win.refresh()

        if self.input_mode:
            key = self.input_win.getch()
            if key == 10:  # Enter key
                self.input_mode = False
            elif key in (127, 8, curses.KEY_BACKSPACE):  # Backspace key
                self.client.inbox_text = self.client.inbox_text[:-1]
            elif 32 <= key <= 126 and len(self.client.inbox_text) < self.width - 8:  # Printable characters
                self.client.inbox_text += chr(key)
        
        time.sleep(0.1)  # Small delay to control UI refresh rate

    def display_message(self, y_offset, message):
        """
        Display a single message on the chat window at the given vertical offset.
        """
        sender_name = message.sender.name if message.sender else ""
        receiver_name = message.receiver.name if message.receiver else self.get_animated_circle()
        content = message.content if message.content else self.get_animated_circle()

        # Determine color pair based on sender index
        try:
            color_index = self.chat_server.chat_clients.index(message.sender) + 1
        except ValueError:
            color_index = 1
        color = curses.color_pair(color_index)

        indicator = f"[{pad_string(sender_name, 10)}  => {pad_string(receiver_name, 10)}]: "
        full_text = indicator + content

        # Split message into lines based on window width
        lines = [full_text[i:i + self.width - 4] for i in range(0, len(full_text), self.width - 4)]

        for line in lines:
            if y_offset < self.height - 4:
                try:
                    self.chat_win.addstr(self.height - y_offset - 4, 2, line, color)
                except curses.error:
                    pass  # Ignore if out-of-bounds
                y_offset += 1

        return y_offset

    def run(self):
        """
        Continuously update the UI.
        """
        while True:
            self.tick += 1
            self.update_ui()

    # --- Animation Helpers ---
    def get_spinner(self):
        return "|/-\\"[self.tick % 4]

    def get_cross(self):
        # Unicode symbols may require adjustments; using simple text fallback here
        return "┤ ┘ ┴ └ ├ ┌ ┬ ┐"[(self.tick % 8) * 2]

    def get_clock(self):
        return "← ↖ ↑ ↗ → ↘ ↓ ↙"[(self.tick % 8) * 2]

    def get_dots(self):
        dot_length = 5
        dots = [' '] * dot_length
        dots[(self.tick // 2) % dot_length] = '.'
        return "".join(dots)

    def get_animated_circle(self):
        return "◴ ◷ ◶ ◵"[(self.tick % 4) * 2]

    def get_bounce(self):
        return ".oOo"[int(self.tick % 4)]

    def get_active_client_name(self):
        names = [client.name for client in self.chat_server.chat_clients]
        return names[self.tick % len(names)]


# ------------------------------------------------------------------------------
# Chat History and Message Classes
# ------------------------------------------------------------------------------

class Message:
    """
    Represents a message exchanged between chat clients.
    """

    def __init__(self, content, sender, receiver, chat_server):
        self.content = content
        self.sender = sender
        self.receiver = receiver
        self.chat_server = chat_server

    @staticmethod
    def from_xml_element(xml_elem, chat_server):
        return Message(
            content=xml_elem.text,
            sender=chat_server.get_client_by_name(xml_elem.get("from")),
            receiver=chat_server.get_client_by_name(xml_elem.get("to")),
            chat_server=chat_server
        )

    @staticmethod
    def from_xml_string(xml_string, chat_server):
        """
        Parses an XML string to create a Message object.
        Handles full XML documents, fragments, and unfinished responses.
        """
        try:
            return Message.from_xml_element(ET.fromstring(xml_string), chat_server)
        except ET.ParseError:
            pass

        # Try wrapping in a <chat> tag (for fragments)
        try:
            wrapped = ET.fromstring(f"<chat>{xml_string}</chat>")
            return Message.from_xml_element(wrapped.find("message"), chat_server)
        except (ET.ParseError, IndexError):
            pass

        # Try handling unfinished responses
        try:
            wrapped = ET.fromstring(f"<chat>{xml_string}</message></chat>")
            return Message.from_xml_element(wrapped.find("message"), chat_server)
        except (ET.ParseError, IndexError):
            pass

        # If all parsing attempts fail, return an empty Message
        return Message(content=None, sender=None, receiver=None, chat_server=chat_server)

    def to_xml_element(self):
        elem = ET.Element("message")
        elem.text = self.content
        if self.receiver and self.receiver.name:
            elem.set("to", self.receiver.name)
        if self.sender and self.sender.name:
            elem.set("from", self.sender.name)
        return elem

    def to_xml_string(self):
        return ET.tostring(self.to_xml_element())


class ChatHistory:
    """
    Manages the chat history and provides methods for saving/loading from XML.
    """

    def __init__(self, messages):
        self.messages = messages

    def save(self):
        with open("chat_log.xml", "wb") as f:
            f.write(self.to_xml_string())

    @staticmethod
    def load(chat_server):
        try:
            xml_tree = ET.parse('chat_log.xml')
            return ChatHistory.from_xml_element(xml_tree, chat_server)
        except ET.ParseError:
            return ChatHistory([])

    @staticmethod
    def from_xml_element(xml_tree, chat_server):
        # Skip the first element if it's empty
        messages = [Message.from_xml_element(elem, chat_server) for elem in list(xml_tree.iter())][1:]
        return ChatHistory(messages)

    @staticmethod
    def from_xml_string(xml_text, chat_server):
        return ChatHistory.from_xml_element(ET.fromstring(xml_text), chat_server)

    def to_xml_element(self):
        root = ET.Element("chat")
        for msg in self.messages:
            root.append(msg.to_xml_element())
        return root

    def to_xml_string(self):
        return ET.tostring(self.to_xml_element())

    def append_message(self, sender, receiver, content):
        self.messages.append(Message(content, sender, receiver, self))
        # Optionally, uncomment the following line to save the history automatically
        # self.save()


# ------------------------------------------------------------------------------
# Chat Server and Client Classes
# ------------------------------------------------------------------------------

class ChatServer:
    """
    Represents the chat server that holds chat clients and their history.
    """

    def __init__(self):
        self.chat_clients = []
        self.history = ChatHistory([])
        # Assign this chat server to each client (if already added)
        for client in self.chat_clients:
            client.chat_server = self

    def get_unfinished_messages(self):
        """
        Returns a list of unfinished messages from all chat clients.
        """
        return [client.get_unfinished_message() for client in self.chat_clients if client.inbox_text != ""]

    def get_client_by_name(self, client_name):
        """
        Retrieves a chat client by its name.
        """
        for client in self.chat_clients:
            if client.name == client_name:
                return client
        return None

    def add_client(self, name, fg_color, bg_color, on_receive_callback):
        """
        Creates and adds a new ChatClient to the server.
        """
        new_client = ChatClient(name=name, fg_color=fg_color, bg_color=bg_color, chat_server=self, on_receive_callback=on_receive_callback)
        self.chat_clients.append(new_client)
        return new_client

    def load_history(self):
        self.history = ChatHistory.load(self)

class ChatClient:
    """
    Represents a participant in the chat.
    """

    chat_clients = []

    def __init__(self, name, fg_color, bg_color, chat_server, on_receive_callback):
        self.chat_server = chat_server
        self.name = name
        self.foreground_color = fg_color
        self.background_color = bg_color
        self.inbox_text = ""
        self.inbox_receiver = None
        self.on_receive_callback = on_receive_callback  # Callback function when a message is received

        self.chat_clients.append(self)

    def send_message(self):
        """
        Sends the current message from the client's inbox and appends it to chat history.
        """
        receiver = self.inbox_receiver
        content = self.inbox_text
        self.chat_server.history.append_message(self, receiver, content)
        # Clear inbox after sending
        self.inbox_text = ""
        self.inbox_receiver = None
        receiver.on_receive_callback(receiver, self, content)

    def update_inbox(self, receiver, content):
        """
        Updates the client's inbox with a new message.
        """
        self.inbox_receiver = receiver
        self.inbox_text = content

    def get_unfinished_message(self):
        """
        Returns a Message object for the current unfinished inbox content.
        """
        return Message(self.inbox_text, self, self.inbox_receiver, self.chat_server)

    def load_ui(self, stdscr):
        """
        Initializes the UI for this client.
        """
        self.ui = ChatUI(self.chat_server, stdscr, self)
    
    def from_string(self, client_name, chat_server):
        """
        Retrieves a chat client by its name.
        """
        for client in chat_server.chat_clients:
            if client.name == client_name:
                return client
        return None


# ------------------------------------------------------------------------------
# Chat Agent Base Class and Specific Agents
# ------------------------------------------------------------------------------

class ChatAgent:
    """
    Base class for all chat agents. Automatically registers the agent as a client in the chat server.
    """

    def __init__(self, name="chat agent", fg_color=curses.COLOR_WHITE, bg_color=curses.COLOR_BLACK, chat_server=None):
        self.client = chat_server.add_client(
            name=name,
            fg_color=fg_color,
            bg_color=bg_color,
            on_receive_callback=lambda receiver, sender, content: self.receive_message(sender, content)
        )

    def receive_message(self, sender, content):
        """
        Default message processing for an agent.
        """
        time.sleep(1)
        self.client.update_inbox(sender, f"Hi, I'm {self.client.name}")
        self.client.send_message()


class ChatbotAgent(ChatAgent):
    """
    Chatbot agent that generates responses using a local AI model.
    """

    def __init__(self, chat_server, name, user_client, terminal_client, model_name):
        super().__init__(name=name, fg_color=curses.COLOR_MAGENTA, chat_server=chat_server)
        self.model = ChatOllama(model=model_name, streaming=True)
        self.prompt_template = ChatPromptTemplate.from_template(CHATBOT_PROMPT_TEMPLATE)
        self.chain = self.prompt_template | self.model
        self.user_client = user_client
        self.terminal_client = terminal_client

    def receive_message(self, sender, content):
        """
        Processes incoming messages, streams the response from the model,
        and sends the final response.
        """
        incoming_message = Message(content, self.client, sender, self.client.chat_server)
        raw_response = ""

        # Stream the AI response in chunks
        for chunk in self.chain.stream({
            "chatbot_name": self.client.name,
            "user_name": self.user_client.name,
            "terminal_name": self.terminal_client.name,
            "history": self.client.chat_server.history.to_xml_string(),
            "message": incoming_message.to_xml_string()
        }):
            raw_response += chunk.content
            parsed_chunk = Message.from_xml_string(raw_response, self.client.chat_server)
            if parsed_chunk.content is not None:
                # Use edgy text animation for intermediate updates
                self.client.update_inbox(parsed_chunk.receiver, generate_edgy_text(parsed_chunk.content))

        # Send the final response
        final_response = Message.from_xml_string(raw_response, self.client.chat_server)
        self.client.update_inbox(final_response.receiver, final_response.content)
        self.client.send_message()


class UserAgent(ChatAgent):
    """
    Represents the human user interacting with the chat system.
    """

    def __init__(self, chat_server, name):
        super().__init__(name="user", fg_color=curses.COLOR_WHITE, chat_server=chat_server)

    def receive_message(self, sender, content):
        """
        Activates the UI input mode to capture user input.
        """
        self.client.inbox_receiver=sender
        self.client.ui.input_mode = True
        while self.client.ui.input_mode:
            time.sleep(0.1)
        self.client.send_message()


class TerminalAgent(ChatAgent):
    """
    Agent that executes terminal commands and returns the output.
    """

    def __init__(self, chat_server):
        super().__init__(name="terminal", fg_color=curses.COLOR_GREEN, chat_server=chat_server)

    def receive_message(self, sender, content):
        """
        Executes the received command and returns the command output and errors.
        """
        process = subprocess.Popen([content], stdout=subprocess.PIPE, shell=True)
        stdout, stderr = process.communicate()
        response_text = f"Output: '{stdout}', Errors: '{stderr}'"
        self.client.update_inbox(sender, response_text)
        self.client.send_message()


# ------------------------------------------------------------------------------
# Main Function to Start the Chat Application
# ------------------------------------------------------------------------------

def main(stdscr):
    # Initialize the chat server
    chat_server = ChatServer()

    # Create agents: user, terminal, and chatbot
    user_agent = UserAgent(chat_server, "user")
    terminal_agent = TerminalAgent(chat_server)
    chatbot_agent = ChatbotAgent(chat_server, "chatbot", user_agent.client, terminal_agent.client, "gemma3")

    # Load the UI for the user
    user_agent.client.load_ui(stdscr)

    # Start the chat and UI in separate threads
    chat_thread = threading.Thread(target=user_agent.client.on_receive_callback, args=(user_agent.client, chatbot_agent.client, ""))
    ui_thread = threading.Thread(target=user_agent.client.ui.run)

    chat_thread.start()
    ui_thread.start()

    chat_thread.join()
    ui_thread.join()


if __name__ == "__main__":
    curses.wrapper(main)
