"""Streamlit Chatbot App for Refund Processing System."""

import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Load config file
config_path = "src/config.yaml"
if not os.path.exists(config_path):
    st.error(f"Configuration file '{config_path}' not found. Please create it with your model and credential settings.")
    st.stop()

from database_creation import create_database, load_csv_data
from src.agents import RefundProcessingSystem
from src.db_tools import get_product_info

AGENT_LABELS = {
    "supervisor": "Supervisor",
    "validation_agent": "Validation Agent",
    "policy_agent": "Policy Agent",
    "communication_agent": "Communication Agent",
    "system": "System",
}


def ensure_database_seeded():
    """Rebuild the SQLite DB from data/*.csv if it doesn't exist yet.

    refunds_agent.db is gitignored (derived, not source data), so a fresh
    deploy - e.g. a new Streamlit Cloud container after the daily synthetic
    orders workflow pushes an updated data/orders.csv - starts with no DB
    file at all. Rebuilding here picks up whatever CSVs shipped with this
    checkout automatically.
    """
    if not os.path.exists("refunds_agent.db"):
        with st.spinner("Seeding database from data/*.csv..."):
            create_database()
            load_csv_data()


def initialize_session_state():
    """Initialize Streamlit session state."""
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    if 'refund_system' not in st.session_state:
        ensure_database_seeded()
        with st.spinner("Initializing multi-agent system..."):
            st.session_state.refund_system = RefundProcessingSystem(config_path)

    if 'pending_orders' not in st.session_state:
        st.session_state.pending_orders = None


def add_message(role: str, content: str):
    """Add message to conversation."""
    timestamp = datetime.now().strftime("%I:%M %p")
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "timestamp": timestamp
    })


def display_messages():
    """Display conversation messages."""
    for message in st.session_state.messages:
        timestamp = message.get("timestamp", "")

        with st.chat_message(message["role"]):
            st.write(message["content"])
            if timestamp:
                label = "You" if message["role"] == "user" else "Support Agent"
                st.caption(f"{label} - {timestamp}")


def enrich_orders(orders):
    """Attach product name/category to each order for a friendlier picker table."""
    product_cache = {}
    rows = []
    for order in orders:
        product_id = order.get("product_id")
        if product_id not in product_cache:
            try:
                product_cache[product_id] = get_product_info.invoke({"product_id": product_id})
            except Exception:
                product_cache[product_id] = {}
        product = product_cache[product_id]

        delivery_date = order.get("delivery_date")
        rows.append({
            "Order ID": order.get("order_id"),
            "Product": product.get("name", product_id),
            "Category": product.get("category", "-"),
            "Order Date": (order.get("order_date") or "")[:10],
            "Delivery Date": delivery_date[:10] if delivery_date else "Not delivered",
            "Total": f"${order.get('total_amount', 0):,.2f}",
            "Status": order.get("status"),
        })
    return rows


def run_agent_turn(user_message: str):
    """Stream one user turn through the multi-agent workflow, rendering live progress."""
    with st.chat_message("assistant"):
        status = st.status("Agents are working on your request...", expanded=True)
        final_response = ""
        seen_orders = None

        for event in st.session_state.refund_system.stream_events(user_message):
            etype = event.get("type")
            agent_label = AGENT_LABELS.get(event.get("agent"), event.get("agent", ""))

            if etype == "tool_call":
                name = event.get("name") or ""
                if name.startswith("transfer_to_"):
                    target = AGENT_LABELS.get(name.replace("transfer_to_", ""), name)
                    status.update(label=f"{agent_label} is delegating to {target}...")
                    status.write(f"🔀 **{agent_label}** → delegating to **{target}**")
                else:
                    status.update(label=f"{agent_label} is working...")
                    status.write(f"🔧 **{agent_label}** is calling `{name}`")

            elif etype == "tool_result":
                name = event.get("name") or ""
                if not name.startswith("transfer_to_"):
                    status.write(f"✅ **{agent_label}** got a result from `{name}`")

            elif etype == "order_options":
                seen_orders = event.get("orders")
                status.write(f"📋 **{agent_label}** found {len(seen_orders)} order(s)")

            elif etype == "agent_text":
                preview = event["content"][:220]
                status.write(f"💬 **{agent_label}**: {preview}{'…' if len(event['content']) > 220 else ''}")

            elif etype == "final":
                final_response = event["content"]

        status.update(label="Done", state="complete", expanded=False)
        st.write(final_response)
        st.caption(f"Support Agent - {datetime.now().strftime('%I:%M %p')}")

    add_message("assistant", final_response)
    st.session_state.pending_orders = seen_orders


def render_order_picker():
    """Render a selectable table of orders instead of making the customer type an order ID."""
    orders = st.session_state.pending_orders
    if not orders:
        return

    st.markdown("#### Select an order")
    rows = enrich_orders(orders)
    df = pd.DataFrame(rows)

    selection = st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key="order_picker",
    )

    selected_rows = selection.selection.rows if selection and selection.selection else []
    if selected_rows:
        selected_order_id = rows[selected_rows[0]]["Order ID"]
        if st.button(f"Proceed with order {selected_order_id}", type="primary"):
            st.session_state.pending_orders = None
            # Avoid words like "proceed"/"confirm" here - the supervisor's own prompt
            # uses that language for the *post-decision* confirmation step, and a
            # customer message containing it gets misread as confirming a decision
            # that was never actually made, skipping the eligibility check entirely.
            synthetic_message = f"That's order {selected_order_id}. Please check if it's eligible for a return."
            add_message("user", synthetic_message)
            with st.chat_message("user"):
                st.write(synthetic_message)
            run_agent_turn(synthetic_message)
            st.rerun()


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Customer Service Chat",
        page_icon="💬",
        layout="centered"
    )

    initialize_session_state()

    st.title("💬 Customer Service Chat")
    st.subheader("Refund & Return Support")

    with st.sidebar:
        st.header("System Status")
        if hasattr(st.session_state, 'refund_system'):
            st.success("Multi-Agent System Ready")
        else:
            st.error("System Not Initialized")

        st.header("Session Controls")
        if st.button("Clear Conversation"):
            st.session_state.messages = []
            st.session_state.pending_orders = None
            if hasattr(st.session_state, 'refund_system') and hasattr(st.session_state.refund_system, 'conversation_history'):
                st.session_state.refund_system.conversation_history = []
            st.rerun()

    st.markdown("---")

    display_messages()
    render_order_picker()

    if prompt := st.chat_input("Type your message here..."):
        add_message("user", prompt)
        with st.chat_message("user"):
            st.write(prompt)
            st.caption(f"You - {datetime.now().strftime('%I:%M %p')}")
        run_agent_turn(prompt)
        st.rerun()

    st.markdown("---")
    st.caption("Powered by Multi-Agent LangGraph System | Customer Service Bot")


if __name__ == "__main__":
    main()
