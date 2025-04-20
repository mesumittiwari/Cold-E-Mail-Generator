# Required for ChromaDB compatibility on Streamlit Cloud
import sqlite3

import sys
import os

sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
# --- End of ChromaDB patch ---

import streamlit as st
from langchain_community.document_loaders import WebBaseLoader
from chains import Chain
from portfolio import Portfolio
from utils import clean_text
# Removed: from streamlit_clipboard import clipboard
import os # Needed for checking environment variable

# --- Configuration ---
NUM_EMAIL_VARIATIONS = 3

# --- Initialize Session State ---
# Use setdefault to initialize only if keys don't exist
st.session_state.setdefault('generated_emails', {}) # Stores {variation_index: email_text}
st.session_state.setdefault('processed_url', None)   # Stores the URL for which emails were generated
# Keep track of the URL currently in the input box to detect changes
st.session_state.setdefault('current_input_url', '')

def create_streamlit_app(llm, portfolio, clean_text_func):
    """Creates the main Streamlit application UI."""

    st.title("📧 Cold E-Mail Generator")
    st.subheader("by Sumit Tiwari")
    st.caption("Enter a job description URL, generate email variations, edit them directly, and manually copy.")
    st.markdown("---")

    # --- Input Section ---
    url_input = st.text_input(
        "Job Description URL:",
        placeholder="Paste the job description URL here...",
        key="url_input_box" # Assign a key for explicit access if needed later
    )
    submit_button = st.button("✨ Generate Emails")
    st.markdown("---")

    # --- Logic for Clearing State on URL Change ---
    # If the URL in the box changes compared to the last *processed* URL,
    # clear the generated emails. This happens on *every* rerun if the text changes.
    if url_input != st.session_state.get('processed_url'):
        # This condition indicates the user has typed something new or cleared the input
        # since the last *successful* generation.
        if url_input != st.session_state.current_input_url:
             # Update the tracking URL
             st.session_state.current_input_url = url_input
             # Clear previous generation results immediately upon text change
             st.session_state.generated_emails = {}
             # Clear text area states if the URL changes to avoid showing stale edits
             for i in range(NUM_EMAIL_VARIATIONS):
                 st.session_state.pop(f"email_textarea_{i}", None)
             # Important: Don't set processed_url here, only after successful generation

    # --- Generation Logic (Only runs on Button Press) ---
    if submit_button and url_input:
        # Set the URL that is actively being processed *now*
        st.session_state.processed_url = url_input
        st.session_state.current_input_url = url_input # Sync tracker on successful submit
        # Clear any previous emails for this specific URL before regenerating
        st.session_state.generated_emails = {}
        # Clear potentially stale individual text area states before filling them
        for i in range(NUM_EMAIL_VARIATIONS):
            st.session_state.pop(f"email_textarea_{i}", None) # Remove old text area states if they exist

        try:
            with st.spinner("Analyzing job description and crafting email variations... ⏳"):
                # 1. Load and clean data
                loader = WebBaseLoader([url_input])
                if callable(clean_text_func):
                    try:
                        loaded_docs = loader.load()
                        if not loaded_docs:
                            st.error("Could not load content from the URL.")
                            st.stop()
                        page_content = getattr(loaded_docs[0], 'page_content', None)
                        if page_content is None:
                             st.error("Loaded document structure is unexpected (no 'page_content').")
                             st.stop()
                        data = clean_text_func(page_content)
                        if not data:
                             st.warning("Content loaded, but resulted in empty text after cleaning.")
                             # Don't stop, maybe generation can handle empty input gracefully or fail later
                    except Exception as load_err:
                        st.error(f"Error loading/cleaning data from URL: {load_err}")
                        st.stop()
                else:
                    st.error("Internal error: clean_text function is not available.")
                    st.stop()

                # 2. Load portfolio and extract job details
                portfolio.load_portfolio()
                jobs = llm.extract_jobs(data)

                if not jobs:
                    st.warning("Could not extract structured job details from the content. Please check the URL.")
                    st.stop() # Stop if no job details could be parsed

                # 3. Generate and STORE email variations
                job = jobs[0] # Process first job found
                skills = job.get('skills', [])
                links = portfolio.query_links(skills)
                generation_successful = False
                generated_emails_temp = {} # Use a temporary dict

                for variation_index in range(NUM_EMAIL_VARIATIONS):
                    try:
                        email = llm.write_mail(job, links)
                        if email and isinstance(email, str):
                            # Store the initially generated email in the temp dict
                            generated_emails_temp[variation_index] = email.strip()
                            generation_successful = True
                        else:
                            st.warning(f"Generated empty or invalid content for Variation {variation_index + 1}.")
                            # Store empty string to avoid errors later if key is expected
                            generated_emails_temp[variation_index] = f"Failed to generate Variation {variation_index + 1}."

                    except Exception as mail_gen_err:
                        st.error(f"Error generating Variation {variation_index + 1}: {mail_gen_err}")
                        generated_emails_temp[variation_index] = f"Error during generation: {mail_gen_err}" # Store error message

                # Update session state *after* the loop completes
                st.session_state.generated_emails = generated_emails_temp

                if generation_successful:
                    st.success("Email variations generated successfully! 🎉 You can now edit them below.")
                else:
                    st.error("Could not generate any usable email variations.")
                # --- End of generation block ---

        except Exception as e:
            st.error(f"An Unexpected Error Occurred during the generation process: {e}")
            st.exception(e) # Shows detailed traceback in console/logs

    # --- Display Section (Runs on Every Rerun) ---
    # Check if the URL *for which emails were generated* matches the *current URL in the input box*
    # AND if there are any emails stored.
    if st.session_state.processed_url == url_input and st.session_state.generated_emails:
        st.subheader("Generated Email Variations:")
        st.info("ℹ️ Edit the text directly in the boxes below. Your edits are saved automatically.")
        st.caption("To copy, select the text in the desired box and press Ctrl+C (or Cmd+C).")
        # Explain Ctrl+Enter behavior subtly
        st.caption("Note: Pressing Ctrl+Enter in a text box might refresh the app (Streamlit's default behavior), but your edits will be preserved.")

        for variation_index, initial_email in st.session_state.generated_emails.items():
            st.markdown(f"--- \n #### Variation {variation_index + 1}")

            # Define a unique key for this text area instance
            text_area_key = f"email_textarea_{variation_index}"

            # Display the text area. Streamlit handles state updates via the 'key'.
            # When the page reruns, Streamlit automatically populates this with the
            # value stored in st.session_state[text_area_key].
            # If the key doesn't exist yet (e.g., first time after generation),
            # it uses the 'value' argument.
            st.text_area(
                label=f"Edit Email Content (Variation {variation_index + 1})",
                value=initial_email, # Provide the initially generated email as the starting point
                height=300,
                key=text_area_key, # Assign the key for state management
                help="Edit the email text here. Select and copy (Ctrl+C / Cmd+C) when ready."
            )
            # Removed copy button - User manually copies from text_area

    elif submit_button and not url_input: # Handle empty URL submit case
        st.warning("Please enter a Job Description URL.")
    # Optional: Add a message if the user clears the URL after generating
    elif not url_input and st.session_state.processed_url:
        st.info("Enter a URL and click 'Generate Emails'. Previous results cleared.")

# --- Footer / Copyright Notice ---
    # Add a separator line before the copyright for better visual separation
    st.markdown("---")
    # Add the copyright notice using st.caption for appropriate styling
    st.caption("© 2025 Cold E-Mail Generator by Sumit Tiwari. All rights reserved.")


# --- Main Execution Block ---
if __name__ == "__main__":
    # Set page config as the absolute first Streamlit command
    st.set_page_config(layout="wide", page_title="Cold Email Generator", page_icon="📧")

    # Removed dependency check for streamlit_clipboard

    # Environment Variable Check
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        st.error("🚨 GROQ_API_KEY environment variable not found!")
        st.info("Please set the GROQ_API_KEY environment variable (e.g., in your .env file or system settings) and restart the app.")
        # Optionally provide link to Groq Console or setup instructions
        # st.markdown("You can get an API key from [Groq Console](https://console.groq.com/keys).")
        st.stop()

    # Initialization
    try:
        # Pass the key directly if needed by Chain, otherwise it might read it itself
        chain_instance = Chain()
        portfolio_instance = Portfolio()
    except Exception as e:
        st.error(f"Failed to initialize application components: {e}")
        st.exception(e)
        st.stop()

    # Run the App
    create_streamlit_app(chain_instance, portfolio_instance, clean_text)
