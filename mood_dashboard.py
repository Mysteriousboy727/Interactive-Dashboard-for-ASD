import hashlib
import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st

LOG_FILE = "mood_log.csv"
USERS_FILE = "users.json"

# Default users (for initial setup)
DEFAULT_USERS = {
    "parent1": {
        "password_hash": hashlib.sha256("parent123".encode()).hexdigest(),
        "role": "parent",
        "name": "Parent 1"
    },
    "parent2": {
        "password_hash": hashlib.sha256("parent123".encode()).hexdigest(),
        "role": "parent",
        "name": "Parent 2"
    },
    "doctor1": {
        "password_hash": hashlib.sha256("doctor123".encode()).hexdigest(),
        "role": "doctor",
        "name": "Dr. Smith"
    },
    "doctor2": {
        "password_hash": hashlib.sha256("doctor123".encode()).hexdigest(),
        "role": "doctor",
        "name": "Dr. Johnson"
    }
}


def init_users_file():
    """Initialize users file with default users if it doesn't exist."""
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_USERS, f, indent=2)


def load_users():
    """Load user credentials from file."""
    init_users_file()
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_password(username: str, password: str) -> bool:
    """Verify username and password."""
    users = load_users()
    if username not in users:
        return False
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return users[username]["password_hash"] == password_hash


def get_user_role(username: str) -> str | None:
    """Get user role if user exists."""
    users = load_users()
    if username in users:
        return users[username]["role"]
    return None


def get_user_name(username: str) -> str:
    """Get user's display name."""
    users = load_users()
    if username in users:
        return users[username].get("name", username)
    return username


def is_authenticated() -> bool:
    """Check if user is authenticated."""
    return st.session_state.get("authenticated", False)


def login(username: str, password: str) -> bool:
    """Attempt to log in user."""
    if verify_password(username, password):
        st.session_state["authenticated"] = True
        st.session_state["username"] = username
        st.session_state["user_role"] = get_user_role(username)
        st.session_state["user_name"] = get_user_name(username)
        return True
    return False


def logout():
    """Log out current user."""
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["user_role"] = None
    st.session_state["user_name"] = None


def load_data() -> pd.DataFrame:
    """Load existing mood log from CSV, if present."""
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE, parse_dates=["timestamp"])
        # basic sanity check
        expected_cols = {"timestamp", "mood", "temperature_c"}
        if not expected_cols.issubset(df.columns):
            return pd.DataFrame(columns=["timestamp", "mood", "temperature_c"])
        return df
    return pd.DataFrame(columns=["timestamp", "mood", "temperature_c"])


def save_event(mood: str, temperature_c: float, df: pd.DataFrame, username: str = None) -> pd.DataFrame:
    """Append a new mood event and persist to CSV."""
    new_row = {
        "timestamp": datetime.now(),
        "mood": mood,
        "temperature_c": temperature_c,
    }
    if username:
        new_row["recorded_by"] = username
    new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    new_df.to_csv(LOG_FILE, index=False)
    return new_df


def sensor_available() -> bool:
    """
    Check if a DS18B20 1‑Wire sensor folder is present.
    This prevents confusing warnings on systems without the sensor
    (e.g. Windows laptops during development).
    """
    base_dir = "/sys/bus/w1/devices"
    if not os.path.isdir(base_dir):
        return False
    try:
        return any(d.startswith("28-") for d in os.listdir(base_dir))
    except Exception:
        return False


def try_read_ds18b20() -> float | None:
    """
    Try to read temperature from a DS18B20 1‑Wire sensor.
    Returns temperature in °C or None if not available.
    """
    base_dir = "/sys/bus/w1/devices"
    try:
        device_folders = [
            d for d in os.listdir(base_dir) if d.startswith("28-")
        ]
        if not device_folders:
            return None
        device_file = os.path.join(device_folders[0], "w1_slave")
        device_path = os.path.join(base_dir, device_file)
        with open(device_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if not lines or not lines[0].strip().endswith("YES"):
            return None
        equals_pos = lines[1].find("t=")
        if equals_pos == -1:
            return None
        temp_string = lines[1][equals_pos + 2 :]
        return float(temp_string) / 1000.0
    except Exception:
        # Any error → just report sensor as unavailable
        return None


def get_temperature(sidebar_choice: str) -> float:
    """
    Obtain temperature based on user selection:
    - If sensor is selected and works, use it.
    - Otherwise, fall back to manual entry.
    """
    if sidebar_choice == "Temperature sensor (DS18B20, if available)":
        sensor_temp = try_read_ds18b20()
        if sensor_temp is not None:
            st.sidebar.success(f"Sensor temperature: {sensor_temp:.1f} °C")
            return sensor_temp
        st.sidebar.warning(
            "Could not read from DS18B20 sensor. "
            "Please enter temperature manually below."
        )

    # Manual input (either chosen directly or used as fallback)
    manual_temp = st.sidebar.number_input(
        "Manual temperature (°C)",
        min_value=-20.0,
        max_value=60.0,
        value=25.0,
        step=0.1,
    )
    return float(manual_temp)


def plot_mood_timeline(df: pd.DataFrame) -> None:
    """Plot a time‑based view of mood events."""
    import altair as alt

    df = df.copy()
    df["mood_value"] = df["mood"].map({"happy": 1, "sad": 0})

    chart = (
        alt.Chart(df)
        .mark_circle(size=90)
        .encode(
            x=alt.X("timestamp:T", title="Time"),
            y=alt.Y(
                "mood_value:Q",
                title="Mood",
                axis=alt.Axis(values=[0, 1], labelExpr='datum.value == 1 ? "Happy" : "Sad"'),
            ),
            color=alt.Color(
                "mood:N",
                title="Mood",
                scale=alt.Scale(domain=["happy", "sad"], range=["#16a34a", "#dc2626"]),
            ),
            tooltip=[
                alt.Tooltip("timestamp:T", title="Time"),
                alt.Tooltip("mood:N", title="Mood"),
                alt.Tooltip("temperature_c:Q", title="Temp (°C)", format=".1f"),
            ],
        )
        .properties(height=300)
    )

    st.subheader("Mood over time")
    st.altair_chart(chart, use_container_width=True)


def show_summary_stats(df: pd.DataFrame) -> None:
    """Display simple counts of happy vs sad events."""
    st.subheader("Summary")
    counts = df["mood"].value_counts().to_dict()
    happy_count = counts.get("happy", 0)
    sad_count = counts.get("sad", 0)

    col1, col2 = st.columns(2)
    col1.metric("Happy events", happy_count)
    col2.metric("Sad events", sad_count)


def show_advanced_stats(df: pd.DataFrame) -> None:
    """Show advanced statistics for doctors."""
    st.subheader("Advanced Statistics")
    
    if df.empty:
        st.info("No data available for analysis.")
        return
    
    df = df.copy()
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.day_name()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        avg_temp = df["temperature_c"].mean()
        st.metric("Average Temperature", f"{avg_temp:.1f} °C")
    
    with col2:
        happy_rate = (df["mood"] == "happy").mean() * 100
        st.metric("Overall Happy Rate", f"{happy_rate:.1f}%")
    
    with col3:
        total_days = df["date"].nunique()
        st.metric("Days Tracked", total_days)
    
    # Mood by day of week
    st.markdown("#### Mood by Day of Week")
    mood_by_day = df.groupby("day_of_week")["mood"].apply(
        lambda x: (x == "happy").mean() * 100
    ).sort_values(ascending=False)
    
    mood_df = pd.DataFrame({
        "Day": mood_by_day.index,
        "Happy Rate (%)": mood_by_day.values
    })
    st.dataframe(mood_df, use_container_width=True, hide_index=True)
    
    # Mood by hour
    st.markdown("#### Mood by Hour of Day")
    mood_by_hour = df.groupby("hour")["mood"].apply(
        lambda x: (x == "happy").mean() * 100
    ).reset_index()
    mood_by_hour.columns = ["Hour", "Happy Rate (%)"]
    
    import altair as alt
    chart = (
        alt.Chart(mood_by_hour)
        .mark_line(point=True)
        .encode(
            x=alt.X("Hour:Q", title="Hour of Day"),
            y=alt.Y("Happy Rate (%):Q", title="Happy Rate (%)"),
        )
        .properties(height=250)
    )
    st.altair_chart(chart, use_container_width=True)


def predict_mood(df: pd.DataFrame) -> None:
    """
    Very simple, interpretable prediction:
    - Look at historical mood by hour of day.
    - Estimate probability of being happy at current hour.
    """
    if df.empty:
        st.info("Collect more data to enable mood prediction.")
        return

    df = df.copy()
    df["hour"] = df["timestamp"].dt.hour
    df["is_happy"] = df["mood"] == "happy"

    probs = df.groupby("hour")["is_happy"].mean().reset_index(name="happy_prob")

    current_hour = datetime.now().hour
    row = probs[probs["hour"] == current_hour]

    st.subheader("Simple mood prediction")

    if row.empty:
        st.info(
            "No historical data for this time of day yet. "
            "Keep recording events to build up a pattern."
        )
        return

    happy_prob = float(row["happy_prob"].iloc[0])
    st.metric(
        "Chance of being happy this hour",
        f"{happy_prob * 100:.0f}%",
    )

    if happy_prob >= 0.6:
        st.success(
            "Based on previous data at this time of day, "
            "the patient has usually been **happy**."
        )
    elif happy_prob <= 0.4:
        st.warning(
            "Based on previous data at this time of day, "
            "the patient has often been **sad**. "
            "You may want to prepare supportive activities."
        )
    else:
        st.info(
            "Past mood at this time of day has been mixed, "
            "so prediction is uncertain."
        )


def show_login_page():
    """Display login page."""
    st.set_page_config(
        page_title="ASD Mood Dashboard - Login",
        layout="centered",
    )
    
    st.title("🔐 ASD Mood & Environment Dashboard")
    st.markdown("### Please log in to continue")
    
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login", use_container_width=True, type="primary")
        
        if submit:
            if login(username, password):
                st.success("Login successful! Redirecting...")
                st.rerun()
            else:
                st.error("❌ Invalid username or password. Please try again.")
    
    st.markdown("---")
    st.markdown("### Default Accounts")
    st.info("""
    **Parents:**
    - Username: `parent1` or `parent2`
    - Password: `parent123`
    
    **Doctors:**
    - Username: `doctor1` or `doctor2`
    - Password: `doctor123`
    """)


def show_parent_dashboard():
    """Show dashboard for parent role."""
    st.set_page_config(
        page_title="ASD Mood Dashboard - Parent View",
        layout="wide",
    )
    
    # Header with logout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("ASD Mood & Environment Dashboard")
        st.caption(f"Welcome, {st.session_state.get('user_name', 'Parent')} (Parent View)")
    with col2:
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
    
    if "mood_data" not in st.session_state:
        st.session_state["mood_data"] = load_data()

    st.sidebar.header("Environment")

    # Only show the DS18B20 option if we are actually on a system
    # where the sensor folder exists (e.g. Raspberry Pi with 1‑Wire enabled).
    options = ["Manual entry"]
    if sensor_available():
        options.insert(0, "Temperature sensor (DS18B20, if available)")

    temp_source = st.sidebar.radio(
        "Temperature source",
        options,
        index=0,
    )

    current_temp = get_temperature(temp_source)

    st.sidebar.markdown("---")
    st.sidebar.metric("Current temperature (°C)", f"{current_temp:.1f}")

    st.markdown("### Record mood")
    st.write(
        "Use the **Left (Happy)** and **Right (Sad)** buttons to log how the "
        "patient feels **right now**. Each press stores the time and temperature."
    )

    col_left, col_right = st.columns(2)
    with col_left:
        if st.button("Left – Happy 😊", use_container_width=True, type="primary"):
            st.session_state["mood_data"] = save_event(
                mood="happy",
                temperature_c=current_temp,
                df=st.session_state["mood_data"],
                username=st.session_state.get("username"),
            )
            st.success("Recorded: **happy**")
            st.rerun()

    with col_right:
        if st.button("Right – Sad 🙁", use_container_width=True):
            st.session_state["mood_data"] = save_event(
                mood="sad",
                temperature_c=current_temp,
                df=st.session_state["mood_data"],
                username=st.session_state.get("username"),
            )
            st.info("Recorded: **sad**")
            st.rerun()

    df = st.session_state["mood_data"]

    if not df.empty:
        plot_mood_timeline(df)
        show_summary_stats(df)
        predict_mood(df)
    else:
        st.info("No mood events recorded yet. Press one of the buttons above to begin.")


def show_doctor_dashboard():
    """Show dashboard for doctor role."""
    st.set_page_config(
        page_title="ASD Mood Dashboard - Doctor View",
        layout="wide",
    )
    
    # Header with logout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("ASD Mood & Environment Dashboard")
        st.caption(f"Welcome, {st.session_state.get('user_name', 'Doctor')} (Doctor View)")
    with col2:
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
    
    if "mood_data" not in st.session_state:
        st.session_state["mood_data"] = load_data()

    df = st.session_state["mood_data"]

    # Doctor can view and analyze, but not record (parents record)
    st.info("👨‍⚕️ **Doctor View**: You can view and analyze all mood data. Parents record the mood events.")

    if df.empty:
        st.warning("No mood events recorded yet. Ask parents to start recording events.")
        return

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Advanced Analysis", "🔮 Predictions", "💾 Export Data"])

    with tab1:
        plot_mood_timeline(df)
        show_summary_stats(df)

    with tab2:
        show_advanced_stats(df)
        
        # Show who recorded what
        if "recorded_by" in df.columns:
            st.markdown("#### Recording Activity by User")
            recorder_stats = df["recorded_by"].value_counts()
            st.dataframe(
                pd.DataFrame({
                    "User": recorder_stats.index,
                    "Events Recorded": recorder_stats.values
                }),
                use_container_width=True,
                hide_index=True
            )

    with tab3:
        predict_mood(df)

    with tab4:
        st.subheader("Export Data")
        st.write("Download the mood log data for further analysis.")
        
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"mood_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )


def main() -> None:
    """Main application entry point."""
    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    # Check authentication
    if not is_authenticated():
        show_login_page()
    else:
        # Show role-specific dashboard
        role = st.session_state.get("user_role")
        if role == "doctor":
            show_doctor_dashboard()
        else:  # parent or default
            show_parent_dashboard()


if __name__ == "__main__":
    main()
