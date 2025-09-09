# LLM Chat Interface

A modern Streamlit-based chat interface for interacting with OpenAI language models.

## Features

- **Interactive Chat**: Real-time conversation with OpenAI models
- **Model Selection**: Automatically detects available models
- **Chat Management**: Clear history and view statistics
- **Session Stats**: Track message counts and conversation metrics
- **Easy Setup**: Simple installation and configuration

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure you have an OpenAI API key in `../.env`:**
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

3. **Run the app:**
   ```bash
   streamlit run app.py
   ```

4. **Open your browser** to `http://localhost:8501`

## Usage

1. Select an OpenAI model from the sidebar dropdown
2. Type your message in the chat input at the bottom
3. Press Enter to send and receive responses
4. Use the "Clear Chat" button to reset the conversation
5. View chat statistics in the sidebar

## Requirements

- Python 3.7+
- OpenAI API key
- Internet connection

The app will automatically check which OpenAI models you have access to and only show those in the selection dropdown.
