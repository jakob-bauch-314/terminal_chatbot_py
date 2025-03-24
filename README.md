# Chat Framework with UI and AI Agents

## Overview
This project implements a simple chat framework featuring a terminal-based UI and chat agents that interact with each other. The system consists of three main agents:

1. **User Agent** - Represents the human user interacting with the chat system.
2. **Terminal Agent** - Executes commands in a Linux terminal and returns the results.
3. **Chatbot Agent** - Uses a local AI model (via `Ollama`) to generate responses based on chat history and system state.

The UI is built using `curses`, providing a text-based interface for interaction.

## Features
- Interactive chat UI using `curses`
- AI-powered chatbot using `Langchain` and `Ollama`
- Terminal command execution via the `TerminalAgent`
- XML-based structured messaging
- Customizable chat clients with different colors

## Installation
### Prerequisites
Ensure you have the following dependencies installed:

- Python 3.8+
- `curses` (pre-installed in Unix-based systems)
- `colorama`
- `lxml`
- `langchain`
- `langchain_ollama`
- `langchain_community`

To install the required dependencies, run:
```sh
pip install colorama lxml langchain langchain_ollama langchain_community
```

## Usage
- The chat interface starts automatically.
- The user can enter messages which will be processed by the AI chatbot.
- The chatbot can execute terminal commands via the TerminalAgent when needed.

## File Structure
- `main.py` - The core script implementing the chat framework.
- `chat_log.xml` - Stores chat history in XML format.

## Customization
### Modifying the AI Model
You can change the AI model used by the chatbot by modifying the `model_name` parameter in `ChatbotAgent`:
```python
chatbot_agent = ChatbotAgent(chat_server, "chatbot", user_agent.client, terminal_agent.client, "gemma3")
```
Replace `gemma3` with the desired model.