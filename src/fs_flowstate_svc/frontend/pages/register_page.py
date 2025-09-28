import logging
import asyncio

import streamlit as st
from email_validator import validate_email, EmailNotValidError

from fs_flowstate_svc.frontend import auth_utils

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Register")


def _render():
    try:
        # flag to perform navigation after form context exits
        redirect_to_login = False

        with st.form("register_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Register")

            if submitted:
                # client-side validation
                if not username:
                    st.error("Username is required.")
                else:
                    try:
                        validate_email(email)
                    except EmailNotValidError:
                        st.error("Please enter a valid email address.")
                        return

                    if not password or len(password) < 8:
                        st.error("Password must be at least 8 characters long.")
                        return

                    try:
                        result = asyncio.run(auth_utils.register(username, email, password))
                    except Exception as e:
                        logger.error(e, exc_info=True)
                        st.error("An error occurred while attempting to register.")
                        return

                    # On success, set flag to navigate after leaving form context
                    if result.get("success"):
                        st.success("Registration successful. Please log in.")
                        redirect_to_login = True
                    else:
                        err = result.get("error") or "Registration failed"
                        st.error(err)

        # perform navigation outside of the form context to ensure switch_page is called
        if redirect_to_login:
            try:
                st.switch_page("Login")
            except Exception:
                # In some test environments/stubs switch_page may raise; ignore
                pass

        # navigation button outside the form
        if st.button("Login"):
            try:
                st.switch_page("Login")
            except Exception:
                pass

    except Exception as e:
        logger.error(e, exc_info=True)
        try:
            st.error("Unexpected error rendering registration page.")
        except Exception:
            pass


# Execute render at import to mimic Streamlit page behavior
_render()
