import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Only the cheap "mini" and "nano" GPT models, to keep token costs low.
CHEAP = ["mini", "nano"]
# Models whose names contain these words don't take plain text chat.
NOT_CHAT = ["audio", "realtime", "tts", "transcribe", "search"]
DEFAULT_MODEL = "gpt-4o-mini"  # the model used in all the lessons


@st.cache_data
def get_available_models() -> list:
    """Cheap chat models this API key can use (fetched once, then cached)."""
    models = [m.id for m in OpenAI().models.list().data
              if m.id.startswith("gpt-") and any(word in m.id for word in CHEAP)
              and not any(word in m.id for word in NOT_CHAT)]
    return sorted(models, reverse=True)


def main():
    st.set_page_config(page_title="LLM Chat Interface", layout="wide")
    st.title("LLM Chat Interface")
    st.markdown("Chat with OpenAI models in real-time!")

    if not os.getenv("OPENAI_API_KEY"):
        st.error("OpenAI API key not found! Please add your API key to the `.env` file in the parent directory.")
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.header("Settings")
        models = get_available_models()
        selected_model = st.selectbox(
            "Select Model:",
            models,
            index=models.index(DEFAULT_MODEL) if DEFAULT_MODEL in models else 0,
            help="Choose an OpenAI model for the conversation",
        )

        st.markdown("---")
        if st.button("Clear Chat", width="stretch"):
            st.session_state.messages = []
            st.rerun()

        st.markdown("### Chat Stats")
        st.metric("Messages", len(st.session_state.messages))
        if st.session_state.messages:
            user_msgs = len([m for m in st.session_state.messages if m["role"] == "user"])
            st.metric("User Messages", user_msgs)
            st.metric("Assistant Messages", len(st.session_state.messages) - user_msgs)

    st.info(f"Currently using: **{selected_model}**")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Type your message here..."):
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # The whole conversation is sent each time: the model has no memory.
                    response = OpenAI().chat.completions.create(
                        model=selected_model,
                        messages=st.session_state.messages + [{"role": "user", "content": prompt}],
                    )
                except Exception as e:
                    st.error(f"Error: {e}")  # not added to the history, so it isn't sent to the model
                    st.stop()
            answer = response.choices[0].message.content
            st.markdown(answer)

        st.session_state.messages += [{"role": "user", "content": prompt},
                                      {"role": "assistant", "content": answer}]
        st.rerun()  # redraw so the sidebar stats include this reply


if __name__ == "__main__":
    main()
