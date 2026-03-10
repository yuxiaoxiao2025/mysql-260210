import streamlit
import sys

print(f"Before: {type(streamlit.session_state)}")
try:
    streamlit.session_state = {}
    print(f"After: {type(streamlit.session_state)}")
    print(f"Value: {streamlit.session_state}")
except Exception as e:
    print(f"Error: {e}")
