import streamlit as st
import openai
import os
from dotenv import load_dotenv
from typing import List

# Load environment variables from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

def get_available_models() -> List[str]:
    """Get list of available OpenAI models that the user has access to."""
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        models = client.models.list()
        
        # Filter for chat models (GPT models)
        chat_models = []
        for model in models.data:
            model_id = model.id
            # Include common chat models
            if any(keyword in model_id.lower() for keyword in ["gpt", "o1"]):
                chat_models.append(model_id)
        
        # Sort models with newer/better models first
        chat_models.sort(reverse=True)
        return chat_models
    except Exception as e:
        st.error(f"Error fetching models: {str(e)}")
        # Fallback to common models
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]

def initialize_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = None

def clear_chat():
    """Clear the chat history."""
    st.session_state.messages = []

def send_message_to_openai(messages: List[dict], model: str) -> str:
    """Send messages to OpenAI and get response."""
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    st.set_page_config(
        page_title="LLM Chat Interface",
        page_icon="LLM",
        layout="wide"
    )

    st.title("LLM Chat Interface")
    st.markdown("Chat with OpenAI models in real-time!")
    
    # Initialize session state
    initialize_session_state()
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        st.error("⚠️ OpenAI API key not found! Please add your API key to the `.env` file in the parent directory.")
        st.stop()
    
    # Sidebar for model selection and controls
    with st.sidebar:
        st.header("Settings")
        
        # Get available models
        with st.spinner("Loading available models..."):
            available_models = get_available_models()
        
        # Model selection
        selected_model = st.selectbox(
            "Select Model:",
            available_models,
            index=0 if available_models else None,
            help="Choose an OpenAI model for the conversation"
        )
        st.session_state.selected_model = selected_model
        
        st.markdown("---")
        
        # Clear chat button
        if st.button("Clear Chat", use_container_width=True):
            clear_chat()
            st.rerun()

        # Chat statistics
        st.markdown("### Chat Stats")
        st.metric("Messages", len(st.session_state.messages))
        
        if st.session_state.messages:
            user_msgs = len([m for m in st.session_state.messages if m["role"] == "user"])
            assistant_msgs = len([m for m in st.session_state.messages if m["role"] == "assistant"])
            st.metric("User Messages", user_msgs)
            st.metric("Assistant Messages", assistant_msgs)
    
    # Main chat interface
    if not selected_model:
        st.warning("Please select a model to start chatting.")
        return
    
    # Display current model
    st.info(f"Currently using: **{selected_model}**")
    
    # Chat messages container
    chat_container = st.container()
    
    with chat_container:
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = send_message_to_openai(st.session_state.messages, selected_model)
                st.markdown(response)
        
        # Add assistant response to chat
        st.session_state.messages.append({"role": "assistant", "content": response})
    

if __name__ == "__main__":
    main()
