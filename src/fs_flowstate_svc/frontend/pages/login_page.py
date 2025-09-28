import logging
import asyncio

import streamlit as st

from fs_flowstate_svc.frontend import auth_utils

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Login")


def _render():
    try:
        with st.form("login_form"):
            username_or_email = st.text_input("Username or Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

            if submitted:
                # simple client-side validation
                if not username_or_email or not password:
                    st.error("Please provide both username/email and password.")
                else:
                    try:
                        result = asyncio.run(auth_utils.login(username_or_email, password))
                    except Exception as e:
                        logger.error(e, exc_info=True)
                        st.error("An error occurred while attempting to log in.")
                        return

                    if result.get("success"):
                        st.success("Login successful.")
                        try:
                            st.switch_page("Home")
                        except Exception:
                            # In test environment switch_page may be stubbed; ignore.
                            pass
                    else:
                        err = result.get("error") or "Login failed"
                        st.error(err)

        # navigation button outside the form
        if st.button("Register"):
            try:
                st.switch_page("Register")
            except Exception:
                pass
    except Exception as e:
        logger.error(e, exc_info=True)
        # avoid exposing internals
        try:
            st.error("Unexpected error rendering login page.")
        except Exception:
            pass


# Execute render at import to mimic Streamlit page behavior
_render()
