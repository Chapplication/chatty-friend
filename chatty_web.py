# chatty_web.py
# Finley 2025

# web interface for chatty friend config

import streamlit as st
import time
import subprocess
import os
import re
import random
import asyncio
from datetime import datetime
from chatty_config import ConfigManager, default_config, CONTACT_TYPE_PRIMARY_SUPERVISOR
from chatty_secrets import SecretsManager
from tools.news_service import RSS_NEWS_FEEDS
import pytz
import subprocess

from chatty_wifi import IS_PI, IS_MAC, is_online, record_web_activity

# Import Supabase manager with graceful fallback
try:
    from chatty_supabase import SupabaseManager, get_supabase_manager, is_supabase_configured
    SUPABASE_CONFIGURED = is_supabase_configured()
except ImportError:
    SUPABASE_CONFIGURED = False
    SupabaseManager = None
    get_supabase_manager = None

# DO NOT COMMIT THIS True!!!
TESTING_PI_UI_MOCK_SYSTEM_CALLS = False
if TESTING_PI_UI_MOCK_SYSTEM_CALLS:
    IS_PI = True
    IS_MAC = False

# first time session state setup
if 'config_manager' not in st.session_state:
    st.session_state.config_manager = ConfigManager()

if 'secrets_manager' not in st.session_state:
    st.session_state.secrets_manager = SecretsManager()

if 'authentication_time' not in st.session_state:
    st.session_state.authentication_time = None

# timeout the login if no activity for 10 minutes on PI
if IS_PI and st.session_state.authentication_time:
    if time.time() - st.session_state.authentication_time > 600:  # 10 minutes
        st.session_state.authentication_time = None
    else:
        st.session_state.authentication_time = time.time()

record_web_activity()

def speak_text(text):
    """Use espeak to speak text on Pi"""
    if IS_PI and not TESTING_PI_UI_MOCK_SYSTEM_CALLS:
        try:
            subprocess.run(['espeak', text], check=False)
        except:
            pass

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate and format phone number"""
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    if digits.startswith('1') and len(digits) == 11:
        # US number with country code
        return f"+{digits}"
    elif len(digits) == 10:
        # US number without country code
        return f"+1{digits}"
    elif digits.startswith('+'):
        # Already has country code
        return phone
    else:
        return None

async def send_lost_password_email(config_manager, secrets_manager, new_password):
    """Send lost password email to primary contact"""
    try:
        # Get primary contacts
        primary_contacts = config_manager.get_contact_by_type(CONTACT_TYPE_PRIMARY_SUPERVISOR)
        if not primary_contacts:
            return False, "No primary contact configured"
        
        # Use first primary contact
        primary_contact = primary_contacts[0]
        if not primary_contact.get('email'):
            return False, "Primary contact has no email address"
        
        # Create a mock master state for email sending
        class MockMasterState:
            def __init__(self, secrets_manager):
                self.secrets_manager = secrets_manager
        
        mock_state = MockMasterState(secrets_manager)
        
        subject = "Chatty Friend Password Reset"
        message = f"""Hello,

A password reset was requested for your Chatty Friend device.

Your new password is: {new_password}

You can use this password to access the configuration interface.

If you did not request this password reset, please contact your administrator.

Best regards,
Chatty Friend System"""
        
        from chatty_communications import chatty_send_email
        await chatty_send_email(mock_state, primary_contact['email'], subject, message)
        return True, f"New password sent to {primary_contact['email']}"
        
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"

def render_improved_list_editor(
    section_key: str,
    config_key: str,
    title: str,
    instructions: str,
    item_label: str = "Entry",
    allow_reorder: bool = True
):
    """
    Renders an improved list editor with better UX
    """
    
    # Initialize session state keys
    edit_key = f"{section_key}_edit_mode"
    temp_key = f"{section_key}_temp_data"
    original_key = f"{section_key}_original"
    new_item_key = f"{section_key}_new_item"
    
    # Initialize edit mode
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False
    
    # Load data on first run or when not editing
    if temp_key not in st.session_state or not st.session_state[edit_key]:
        current_data = st.session_state.config_manager.get_config(config_key) or []
        st.session_state[temp_key] = current_data.copy()
        st.session_state[original_key] = current_data.copy()
    
    # Display mode toggle
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(title)
    with col2:
        if st.session_state[edit_key]:
            if st.button("👁️ View Mode", key=f"{section_key}_view_mode"):
                st.session_state[edit_key] = False
                # Clear the new item field when switching to view mode
                if new_item_key in st.session_state:
                    del st.session_state[new_item_key]
                st.rerun()
        else:
            if st.button("✏️ Edit Mode", key=f"{section_key}_edit_mode_btn"):
                st.session_state[edit_key] = True
                st.rerun()
    
    st.info(instructions)
    
    # Get current list
    items = st.session_state[temp_key]
    
    if st.session_state[edit_key]:
        # EDIT MODE
        st.markdown("### 📝 Edit Mode")
        
        # Add new item at top
        with st.container():
            new_item = st.text_area(
                f"Add New {item_label}",
                key=new_item_key,
                height=100,
                placeholder=f"Type your new {item_label.lower()} here..."
            )
            
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("➕ Add", key=f"{section_key}_add", type="primary"):
                    if new_item.strip():
                        st.session_state[temp_key].insert(0, new_item.strip())
                        # Instead of modifying the widget's session state, delete it
                        # This will cause it to be recreated fresh on the next run
                        del st.session_state[new_item_key]
                        st.success(f"Added new {item_label.lower()}!")
                        st.rerun()
        
        st.divider()
        
        # Edit existing items
        for i, item in enumerate(items):
            with st.container():
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    # Use text_area with unique key but no on_change
                    items[i] = st.text_area(
                        f"{item_label} {i+1}",
                        value=item,
                        key=f"{section_key}_item_{i}",
                        height=100
                    )
                
                with col2:
                    # Action buttons in a vertical layout
                    if st.button("🗑️", key=f"{section_key}_delete_{i}", help=f"Delete {item_label.lower()}"):
                        st.session_state[temp_key].pop(i)
                        st.rerun()
                    
                    if allow_reorder:
                        if i > 0 and st.button("⬆️", key=f"{section_key}_up_{i}", help="Move up"):
                            items[i], items[i-1] = items[i-1], items[i]
                            st.rerun()
                        
                        if i < len(items)-1 and st.button("⬇️", key=f"{section_key}_down_{i}", help="Move down"):
                            items[i], items[i+1] = items[i+1], items[i]
                            st.rerun()
        
        # Save/Cancel buttons
        st.divider()
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("💾 Save Changes", key=f"{section_key}_save", type="primary"):
                # Save to config
                success, message = st.session_state.config_manager.save_config({
                    config_key: st.session_state[temp_key]
                })
                if success:
                    st.session_state[edit_key] = False
                    st.session_state[original_key] = st.session_state[temp_key].copy()
                    # Clear the new item field
                    if new_item_key in st.session_state:
                        del st.session_state[new_item_key]
                    st.success("✅ Changes saved!")
                    st.rerun()
                else:
                    st.error(f"❌ Error: {message}")
        
        with col2:
            if st.button("❌ Cancel", key=f"{section_key}_cancel"):
                # Restore original
                st.session_state[temp_key] = st.session_state[original_key].copy()
                st.session_state[edit_key] = False
                # Clear the new item field
                if new_item_key in st.session_state:
                    del st.session_state[new_item_key]
                st.warning("Changes discarded")
                st.rerun()
        
        with col3:
            if st.button("🗑️ Clear All", key=f"{section_key}_clear"):
                if st.checkbox("Confirm clear all", key=f"{section_key}_confirm_clear"):
                    st.session_state[temp_key] = []
                    st.rerun()
    
    else:
        # VIEW MODE
        if not items:
            st.info(f"No {item_label.lower()}s added yet. Click 'Edit Mode' to add some!")
        else:
            for i, item in enumerate(items):
                with st.container():
                    st.markdown(f"**{item_label} {i+1}:**")
                    st.markdown(item)
                    if i < len(items) - 1:
                        st.divider()

# Unified Section Manager
class SectionManager:
    """Manages consistent save/lock behavior across all sections"""
    
    def __init__(self, section_id: str, auto_lock: bool = True):
        self.section_id = section_id
        self.auto_lock = auto_lock
        self.changes_key = f"{section_id}_has_changes"
        self.original_values_key = f"{section_id}_original_values"
        
    def track_field(self, field_name: str, current_value, widget_key: str = None):
        """Track a field for changes"""
        if self.original_values_key not in st.session_state:
            st.session_state[self.original_values_key] = {}
        
        # Store original value if not already stored
        if field_name not in st.session_state[self.original_values_key]:
            st.session_state[self.original_values_key][field_name] = current_value
        
        # Check if value has changed
        original = st.session_state[self.original_values_key][field_name]
        
        # Get the current widget value if widget_key provided
        if widget_key and widget_key in st.session_state:
            current_value = st.session_state[widget_key]
        
        has_changed = original != current_value
        
        # Update changes flag
        if self.changes_key not in st.session_state:
            st.session_state[self.changes_key] = False
        
        if has_changed and not st.session_state[self.changes_key]:
            st.session_state[self.changes_key] = True
            if self.auto_lock and not st.session_state.section_locked:
                lock_section()
                st.rerun()
        
        return has_changed
    
    def render_save_status(self):
        """Show consistent save status across all sections"""
        if st.session_state.get(self.changes_key, False):
            st.info("📝 You have unsaved changes")
        
        if st.session_state.section_locked:
            st.warning("🔒 Section is locked - use Save/Cancel buttons in sidebar")
    
    def reset(self):
        """Reset tracking for this section"""
        if self.original_values_key in st.session_state:
            del st.session_state[self.original_values_key]
        if self.changes_key in st.session_state:
            del st.session_state[self.changes_key]

# Sections that should save immediately
INSTANT_SAVE_SECTIONS = {'password', 'wifi', 'reset'}  
FORM_SECTIONS = {'ai', 'personality', 'content', 'voice_tech', 'secrets'}  
# Sections with change tracking
TRACKED_SECTIONS = {'basic', 'user_profile', 'notes', 'contacts', 'supervisor'}  



# Main app structure
st.set_page_config(
    page_title="Chatty Friend Configuration",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for responsive design
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #2e4057;
        margin-bottom: 2rem;
    }
    
    .config-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border: 1px solid #dee2e6;
    }
    
    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    
    .error-message {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
        margin: 1rem 0;
    }
    
    .warning-message {
        background: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #ffeaa7;
        margin: 1rem 0;
    }
    
    @media (max-width: 768px) {
        .main-header {
            font-size: 1.5rem;
        }
        .config-section {
            padding: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# Platform indicator
platform_text = "🖥️ Mac" if IS_MAC else "🥧 Raspberry Pi"
st.sidebar.text(f"Platform: {platform_text}")

# Pi trying to get on a network - get SSID and PW
if IS_PI and not st.session_state.authentication_time:
    if not is_online():

        st.markdown("<h1 class='main-header'>🌐 WiFi Connectivity</h1>", unsafe_allow_html=True)
        
        current_ssid = st.session_state.config_manager.get_config('WIFI_SSID')
        current_password = st.session_state.config_manager.get_config('WIFI_PASSWORD')
        
        # Hotspot mode UI
        st.markdown("<div class='warning-message'>📡 Hotspot Mode Active</div>", unsafe_allow_html=True)
        st.info("⚠️ This Pi requires 2.4GHz WiFi networks")
            
        with st.form("wifi_form"):
            st.subheader("WiFi Configuration")
            ssid = st.text_input("Network Name (SSID)", value=current_ssid or "", key="wifi_ssid")
            password = st.text_input("Password", type="password", value=current_password or "", key="wifi_password")
            
            col1, col2 = st.columns(2)
            with col1:
                save_wifi = st.form_submit_button("💾 Save WiFi and Reboot", type="primary")
            with col2:
                cancel = st.form_submit_button("❌ Cancel")
            
            if save_wifi:
                st.info("Device will reboot now. Please wait 2-3 minutes and refresh this page.")
                st.session_state.config_manager.save_config({
                    'WIFI_SSID': ssid,
                    'WIFI_PASSWORD': password
                })

                # reboot the Pi - startup will attach to wifi before this page runs again
                if not TESTING_PI_UI_MOCK_SYSTEM_CALLS:
                    subprocess.run(['sudo', 'reboot'], check=False)

    # we're online, require recent authentication
    else:
        st.markdown("<h1 class='main-header'>🔐 Authentication</h1>", unsafe_allow_html=True)
        
        password_hint = st.session_state.config_manager.get_config('CONFIG_PASSWORD_HINT') or "No hint available"
        
        st.info(f"💡 Hint: {password_hint}")
        
        with st.form("auth_form"):
            entered_password = st.text_input("Password", type="password", key="auth_password")
            login_button = st.form_submit_button("🔓 Login", type="primary")
            
            if login_button:
                stored_password = st.session_state.config_manager.get_config('CONFIG_PASSWORD')
                if entered_password == stored_password:
                    st.session_state.authentication_time = time.time()
                    st.success("✅ Authentication successful!")
                    st.rerun()
                else:
                    st.error("❌ Invalid password")
    
        # Check conditions for lost password button
        primary_contacts = st.session_state.config_manager.get_contact_by_type(CONTACT_TYPE_PRIMARY_SUPERVISOR)
        has_primary_contact = primary_contacts and len(primary_contacts) > 0 and primary_contacts[0].get('email')
        has_email_config = st.session_state.secrets_manager.has_email_configured()
        
        if has_primary_contact and has_email_config:
            st.divider()
            st.write("**Lost Password?**")
            
            if st.button("📧 Reset Password", key="lost_password_button"):
                # Generate random 6-digit password
                new_password = f"{random.randint(0, 999999):06d}"
                
                try:
                    # Send email asynchronously
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    email_success, email_message = loop.run_until_complete(
                        send_lost_password_email(st.session_state.config_manager, 
                                                st.session_state.secrets_manager, 
                                                new_password)
                    )
                    loop.close()
                    
                    if email_success:
                        # Save new password
                        st.session_state.config_manager.save_config({
                            'CONFIG_PASSWORD': new_password
                        })
                        
                        check_email = primary_contacts[0].get('email')[0:2]+"*****"+primary_contacts[0].get('email')[-2:]
                        st.success(f"✅ Password reset successful!")
                        st.info("Please check your email ["+check_email+"] for the new password.")
                    else:
                        st.error(f"❌ Failed to send reset email: {email_message}")
                        
                except Exception as e:
                    st.error(f"❌ Failed to reset password: {str(e)}")

else:  # we have wifi and authentication!
    st.markdown("<h1 class='main-header'>⚙️ Chatty Friend Configuration</h1>", unsafe_allow_html=True)
    st.session_state.last_activity = time.time()
        
    # Simple vertical navigation system
    sections = [
        {'id': 'basic', 'name': '👤 Basic Settings', 'desc': 'Name, timezone, voice settings'},
        {'id': 'user_profile', 'name': '📝 What Chatty Knows About You', 'desc': 'Biographical information and facts that Chatty should know'},
        {'id': 'notes', 'name': '📋 Pre-Escalation Notes', 'desc': 'You can enter notes here, or review observations made by the suppervisor AI.'},
        {'id': 'contacts', 'name': '👥 Contacts that Chatty can Reach', 'desc': 'Manage contacts such as primary providers, casual users, etc.'},
        {'id': 'password', 'name': '🔑 Password', 'desc': 'Change password'},
        {'id': 'supervisor', 'name': '👥 Supervisor Setup', 'desc': 'Instructions for the conversation supervisor'},
        {'id': 'wifi', 'name': '📡 WiFi', 'desc': 'WiFi configuration'},
        {'id': 'remote_config', 'name': '☁️ Remote Configuration', 'desc': 'Supabase cloud sync and device backup'},
        {'id': 'ai', 'name': '🤖 AI Settings', 'desc': 'AI model configuration'},
        {'id': 'personality', 'name': '🎭 Chatty Personality', 'desc': 'Setup the personality that Chatty will use to engage with the user'},
        {'id': 'content', 'name': '📰 Chatty Content Settings', 'desc': 'News provider settings'},
        {'id': 'voice_tech', 'name': '🔧 Voice Technical Config', 'desc': 'VAD and wake word settings'},
        {'id': 'secrets', 'name': '🔐 Secrets', 'desc': 'API keys and secrets (write only)'},
        {'id': 'reset', 'name': '💀 DANGER! Reset', 'desc': 'Reset to defaults'}
    ]
    
    # Initialize current section
    if 'current_section' not in st.session_state:
        st.session_state.current_section = 'basic'
    
    if 'section_locked' not in st.session_state:
        st.session_state.section_locked = False
    
    if 'has_unsaved_changes' not in st.session_state:
        st.session_state.has_unsaved_changes = False
    
    def lock_section():
        st.session_state.section_locked = True
        st.session_state.has_unsaved_changes = True
    
    def unlock_section():
        st.session_state.section_locked = False
        st.session_state.has_unsaved_changes = False
    
    def save_current_section():
        """Save the current section's data"""
        section_id = st.session_state.current_section
        try:
            config_updates = {}
            
            if section_id == 'basic':
                time_zone = st.session_state.get('time_zone', '')
                config_updates.update({
                    'USER_NAME': st.session_state.get('user_name', 'User'),
                    'LANGUAGE': st.session_state.get('user_language', 'English'),
                    'TIME_ZONE': time_zone,
                    'WAKE_WORD_MODEL': st.session_state.get('profile_wake_word', st.session_state.config_manager.default_config['WAKE_WORD_MODEL']),
                    'SPEED': st.session_state.get('profile_speed', st.session_state.config_manager.default_config['SPEED']),
                    'VOLUME': st.session_state.get('profile_volume', st.session_state.config_manager.default_config['VOLUME']),
                    'MAX_PROFILE_ENTRIES': st.session_state.get('max_profile_entries', st.session_state.config_manager.default_config['MAX_PROFILE_ENTRIES']),
                    'SECONDS_TO_WAIT_FOR_MORE_VOICE': st.session_state.get('seconds_to_wait', st.session_state.config_manager.default_config['SECONDS_TO_WAIT_FOR_MORE_VOICE']),
                    'ASSISTANT_EAGERNESS_TO_REPLY': st.session_state.get('eagerness', st.session_state.config_manager.default_config['ASSISTANT_EAGERNESS_TO_REPLY']),
                    'AUTO_GO_TO_SLEEP_TIME_SECONDS': st.session_state.get('sleep_time', st.session_state.config_manager.default_config['AUTO_GO_TO_SLEEP_TIME_SECONDS'])
                })

                if time_zone: 
                    try:
                        os.system(f"sudo timedatectl set-timezone {time_zone}")
                    except Exception as e:
                        st.error(f"❌ Failed to set timezone: {str(e)}")

            elif section_id == 'user_profile':
                config_updates.update({
                    'USER_PROFILE': st.session_state.get('modal_user_profile', [])
                })
            elif section_id == 'notes':
                config_updates.update({
                    'PRIOR_PRE_ESCALATION_NOTES': st.session_state.get('modal_notes', [])
                })
            elif section_id == 'contacts':
                config_updates.update({
                    'CONTACTS': st.session_state.get('modal_contacts', [])
                })
            elif section_id == 'supervisor':
                config_updates.update({
                    'AUTO_SUMMARIZE_EVERY_N_MESSAGES': st.session_state.get('auto_summarize', st.session_state.config_manager.default_config['AUTO_SUMMARIZE_EVERY_N_MESSAGES']),
                    'AUTO_SUMMARIZE_MAX_TOKENS': st.session_state.get('auto_summarize_max_tokens', st.session_state.config_manager.default_config.get('AUTO_SUMMARIZE_MAX_TOKENS', 50000)),
                    'SUPERVISOR_INSTRUCTIONS': st.session_state.get('supervisor_instructions', ''),
                    'DAILY_COST_LIMIT': st.session_state.get('daily_cost_limit') if st.session_state.get('daily_cost_limit', 0.0) > 0 else None,
                    'MONTHLY_COST_LIMIT': st.session_state.get('monthly_cost_limit') if st.session_state.get('monthly_cost_limit', 0.0) > 0 else None,
                    'COST_ALERT_THRESHOLD': st.session_state.get('cost_alert_threshold') if st.session_state.get('cost_alert_threshold', 0.0) > 0 else None
                })
            elif section_id == 'password':
                new_password = st.session_state.get('new_password', '')
                confirm_password = st.session_state.get('confirm_password', '')
                if new_password and new_password == confirm_password:
                    alt_hint = new_password[0]+"...."+new_password[-1]
                    config_updates.update({
                        'CONFIG_PASSWORD': new_password,
                        'CONFIG_PASSWORD_HINT': st.session_state.get('password_hint', alt_hint)
                    })
                else:
                    return False, "Passwords do not match or are empty"
            elif section_id == 'wifi':
                new_ssid = st.session_state.get('new_wifi_ssid', '').strip()
                new_wifi_password = st.session_state.get('new_wifi_password', '').strip()
                if new_ssid and new_wifi_password:
                    config_updates.update({
                        'WIFI_SSID': new_ssid,
                        'WIFI_PASSWORD': new_wifi_password
                    })
                else:
                    return False, "Please enter both SSID and password"
            elif section_id == 'ai':
                realtime_model = st.session_state.get('realtime_model', '').strip()
                transcription_model = st.session_state.get('transcription_model', '').strip()
                supervisor_model = st.session_state.get('supervisor_model', '').strip()
                ws_url = st.session_state.get('ws_url', '').strip()
                if realtime_model and transcription_model and ws_url:
                    config_updates.update({
                        'REALTIME_MODEL': realtime_model,
                        'AUDIO_TRANSCRIPTION_MODEL': transcription_model,
                        'SUPERVISOR_MODEL': supervisor_model,
                        'WS_URL': ws_url
                    })
                else:
                    return False, "Please fill in all required AI model fields"
            elif section_id == 'personality':
                config_updates.update({
                    'VOICE_ASSISTANT_SYSTEM_PROMPT': st.session_state.get('system_prompt', ''),
                    'VOICE': st.session_state.get('selected_voice', 'alloy'),
                    'VOLUME': st.session_state.get('volume_setting', 50),
                    'SPEED': st.session_state.get('speed_setting', 50),
                    'ASSISTANT_EAGERNESS_TO_REPLY': st.session_state.get('eagerness_setting', 50)
                })
            elif section_id == 'content':
                config_updates.update({
                    'NEWS_PROVIDER': st.session_state.get('news_provider', 'BBC')
                })
            elif section_id == 'voice_tech':
                noise_gate = st.session_state.get('noise_gate_threshold', 0.0)
                config_updates.update({
                    'VAD_THRESHOLD': st.session_state.get('vad_threshold', 0.3),
                    'SECONDS_TO_WAIT_FOR_MORE_VOICE': st.session_state.get('voice_wait_time', 1.0),
                    'WAKE_ENTRY_THRESHOLD': st.session_state.get('wake_entry_threshold', 0.35),
                    'WAKE_CONFIRM_PEAK': st.session_state.get('wake_confirm_peak', 0.45),
                    'WAKE_CONFIRM_CUMULATIVE': st.session_state.get('wake_confirm_cumulative', 1.2),
                    'NOISE_TARGET_FLOOR': st.session_state.get('noise_target_floor', 120.0),
                    'NOISE_MAX_INJECTION': st.session_state.get('noise_max_injection', 85.0),
                    'NOISE_GATE_THRESHOLD': noise_gate if noise_gate > 0 else None
                })
            elif section_id == 'secrets':
                secrets_input = st.session_state.get('secrets_json', '').strip()
                if secrets_input:
                    success, message = st.session_state.secrets_manager.save_secrets(secrets_input)
                    return success, message
                else:
                    return False, "Please enter secrets configuration"
            
            success, message = st.session_state.config_manager.save_config(config_updates)
            return success, message
            
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    # Create layout: sidebar navigation + main content
    col1, col2 = st.columns([1, 3])
    
    # Navigation sidebar
    with col1:
        st.subheader("Configuration Sections")
        
        for section in sections:
            # Show current section differently 
            is_current = section['id'] == st.session_state.current_section
            
            # Button styling
            if is_current:
                if st.session_state.has_unsaved_changes:
                    button_text = f"🔒 {section['name']} (editing)"
                    button_type = "primary"
                else:
                    button_text = f"📍 {section['name']}"
                    button_type = "primary"
            else:
                button_text = section['name']
                button_type = "secondary"
            
            if st.button(button_text, key=f"nav_{section['id']}", type=button_type, use_container_width=True):
                # If switching away from a locked section, unlock it (effectively canceling changes)
                if st.session_state.section_locked and not is_current:
                    # Cancel any changes by clearing relevant session state keys
                    old_section = st.session_state.current_section
                    section_keys = {
                        'basic': ['user_name', 'user_language', 'time_zone', 'profile_wake_word', 'profile_speed', 'profile_volume', 
                                 'max_profile_entries', 'seconds_to_wait', 'eagerness', 'sleep_time', 'initial_basic_values'],
                        'user_profile': ['modal_user_profile', 'original_user_profile', 'new_profile_entry'],
                        'notes': ['modal_notes', 'new_note_entry'],
                        'contacts': ['modal_contacts'],
                        'supervisor': ['auto_summarize', 'supervisor_instructions'],
                        'password': ['new_password', 'confirm_password', 'password_hint'],
                        'wifi': ['new_wifi_ssid', 'new_wifi_password'],
                        'remote_config': ['supabase_email', 'supabase_password', 'device_name', 'device_location', 'device_passphrase', 'selected_device_id'],
                        'ai': ['realtime_model', 'transcription_model', 'supervisor_model', 'ws_url'],
                        'personality': ['system_prompt', 'selected_voice', 'volume_setting', 'speed_setting', 'eagerness_setting'],
                        'content': ['news_provider'],
                        'voice_tech': ['vad_threshold', 'wake_word_threshold', 'voice_wait_time'],
                        'secrets': ['secrets_json'],
                        'reset': []
                    }
                    
                    keys_to_clear = section_keys.get(old_section, [])
                    for key in keys_to_clear:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    unlock_section()
                
                st.session_state.current_section = section['id']
                st.rerun()
            
            # Show description for current section
            if is_current:
                st.caption(section['desc'])
        
        # Save/Cancel buttons (only show if section is locked)
        if st.session_state.section_locked and st.session_state.current_section in TRACKED_SECTIONS:
            st.divider()
            st.write("**Actions:**")
            
            if st.button("💾 Save Changes", type="primary", key="save_section", use_container_width=True):
                success, message = save_current_section()
                st.write(f"DEBUG: Save result - Success: {success}, Message: {message}")  # Debug line
                if success:
                    unlock_section()
                    st.success("✅ Changes saved!")
                    st.rerun()
                else:
                    st.error(f"❌ Save failed: {message}")
            
            if st.button("❌ Cancel Changes", key="cancel_section", use_container_width=True):
                # Clear form inputs based on current section
                current_section_id = st.session_state.current_section
                
                # Define keys to clear for each section
                section_keys = {
                    'basic': ['user_name', 'user_language', 'time_zone', 'profile_wake_word', 'profile_speed', 'profile_volume', 
                             'max_profile_entries', 'seconds_to_wait', 'eagerness', 'sleep_time', 'initial_basic_values'],
                    'user_profile': ['modal_user_profile', 'original_user_profile', 'new_profile_entry'],
                    'notes': ['modal_notes', 'new_note_entry'],
                    'contacts': ['modal_contacts'],
                    'supervisor': ['auto_summarize', 'supervisor_instructions'],
                    'password': ['new_password', 'confirm_password', 'password_hint'],
                    'wifi': ['new_wifi_ssid', 'new_wifi_password'],
                    'remote_config': ['supabase_email', 'supabase_password', 'device_name', 'device_location', 'device_passphrase', 'selected_device_id'],
                    'ai': ['realtime_model', 'transcription_model', 'supervisor_model', 'ws_url'],
                    'personality': ['system_prompt', 'selected_voice', 'volume_setting', 'speed_setting', 'eagerness_setting'],
                    'content': ['news_provider'],
                    'voice_tech': ['vad_threshold', 'wake_word_threshold', 'voice_wait_time'],
                    'secrets': ['secrets_json'],
                    'reset': []
                }
                
                # Clear keys for current section
                keys_to_clear = section_keys.get(current_section_id, [])
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                
                # Also clear any widget keys that might contain data for the current section
                all_keys = list(st.session_state.keys())
                for key in all_keys:
                    # Clear any keys that start with patterns related to current section
                    if (current_section_id == 'user_profile' and key.startswith(('profile_entry_', 'delete_profile_'))) or \
                       (current_section_id == 'notes' and key.startswith(('note_', 'delete_note_'))) or \
                       (current_section_id == 'contacts' and key.startswith(('contact_', 'delete_contact_'))):
                        del st.session_state[key]
                
                # Force complete refresh by clearing the current section's cached initial values 
                # This will force the widgets to reload with fresh initial values from config
                if current_section_id == 'basic':
                    if 'initial_basic_values' in st.session_state:
                        del st.session_state['initial_basic_values']
                
                unlock_section()
                st.warning("🔄 Changes cancelled!")
                st.rerun()
    
    # Main content area
    with col2:
        current_section = st.session_state.current_section
    
        # Display current section title
        section_titles = {
            'basic': '👤 Basic Profile',
            'user_profile': '📝 What Chatty Knows About You', 
            'notes': '📋 Pre-Escalation Notes',
            'contacts': '👥 Contacts that Chatty can Reach',
            'password': '🔑 Change Password',
            'supervisor': '👥 Supervisor Setup',
            'wifi': '📡 WiFi Configuration',
            'remote_config': '☁️ Remote Configuration',
            'ai': '🤖 AI Model Configuration',
            'personality': '🎭 Chatty Personality',
            'content': '📰 Chatty Content Settings',
            'voice_tech': '🔧 Voice Technical Config',
            'secrets': '🔐 Secrets',
            'reset': '💀 DANGER! Reset'
        }
        
        st.subheader(section_titles.get(current_section, current_section.title()))
    
    if current_section == 'basic':  # Basic Profile Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("Basic Profile Information")
        
        # Store initial values in session state (only once per session)
        if 'initial_basic_values' not in st.session_state:
            st.session_state.initial_basic_values = {
                'user_name': st.session_state.config_manager.get_config('USER_NAME') or "User",
                'user_language': st.session_state.config_manager.get_config('LANGUAGE') or "English",
                'time_zone': st.session_state.config_manager.get_config('TIME_ZONE') or '',
                'wake_word': st.session_state.config_manager.get_config('WAKE_WORD_MODEL') or 'amanda',
                'speed': st.session_state.config_manager.get_percent_config_as_0_to_100_int('SPEED') or 60,
                'volume': st.session_state.config_manager.get_percent_config_as_0_to_100_int('VOLUME') or 50,
                'max_entries': st.session_state.config_manager.get_config('MAX_PROFILE_ENTRIES') or 100,
                'wait_time': float(st.session_state.config_manager.get_config('SECONDS_TO_WAIT_FOR_MORE_VOICE') or 1.0),
                'eagerness': st.session_state.config_manager.get_config('ASSISTANT_EAGERNESS_TO_REPLY') or 50,
                'sleep_time': st.session_state.config_manager.get_config('AUTO_GO_TO_SLEEP_TIME_SECONDS') or 1800
            }
        
        initial_values = st.session_state.initial_basic_values
        
        # Basic profile info
        user_name = st.text_input(
            "Name",
            value=initial_values['user_name'],
            key="user_name",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        user_language = st.text_input(
            "Language",
            value=initial_values['user_language'],
            key="user_language",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        # Time zone selection
        timezones = [''] + list(pytz.all_timezones)
        tz_index = timezones.index(initial_values['time_zone']) if initial_values['time_zone'] in timezones else 0
        
        time_zone = st.selectbox(
            "Time Zone",
            options=timezones,
            index=tz_index,
            key="time_zone",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        # Voice settings
        wake_word_choices = st.session_state.config_manager.get_config('WAKE_WORD_MODEL_CHOICES') or default_config['WAKE_WORD_MODEL_CHOICES']
        wake_word_index = wake_word_choices.index(initial_values['wake_word']) if initial_values['wake_word'] in wake_word_choices else 0
        
        voice = st.selectbox(
            "Assistant Name (Wake Word) !! Changes Take Effect After Save and Restart !!",
            options=wake_word_choices,
            index=wake_word_index,
            key="profile_wake_word",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        speed = st.slider(
            "Speech Speed (lower = slower)",
            min_value=0, max_value=100,
            value=initial_values['speed'],
            key="profile_speed",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        volume = st.slider(
            "Speech Volume (lower = quieter)",
            min_value=0, max_value=100,
            value=initial_values['volume'],
            key="profile_volume",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        # Advanced settings
        max_profile_entries = st.number_input(
            "Max Profile Entries",
            min_value=10, max_value=10000,
            value=initial_values['max_entries'],
            key="max_profile_entries",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        seconds_to_wait = st.number_input(
            "Seconds to Wait for More Voice",
            min_value=0.1, max_value=5.0, step=0.1,
            value=initial_values['wait_time'],
            key="seconds_to_wait",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        eagerness = st.slider(
            "Assistant Eagerness to Reply (0=very eager, 100=patient)",
            min_value=0, max_value=100,
            value=initial_values['eagerness'],
            key="eagerness",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        sleep_time = st.number_input(
            "Auto Sleep Time (seconds)",
            min_value=60, max_value=7200,
            value=initial_values['sleep_time'],
            key="sleep_time",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        # Show lock status
        if st.session_state.section_locked:
            st.info("🔒 Section is locked - use Save/Cancel buttons in sidebar to save changes or switch sections")
        
        # No more buttons - everything is in separate tabs now
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'user_profile':
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        
        render_improved_list_editor(
            section_key="user_profile",
            config_key="USER_PROFILE",
            title="📝 What Chatty Knows About You",
            instructions="Tell Chatty about the user in short paragraphs or sentences. Click 'Edit Mode' to make changes.",
            item_label="Profile Entry"
        )
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'supervisor':  # Supervisor Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("Supervisor Profile")
        st.info("💡 The supervisor is an AI that reviews interactions between the user and Chatty.  It will send summaries to the first contact marked as 'primary' and escalations to all contacts depending on what it is told to look for.")
        
        auto_summarize = st.number_input(
            "Auto Summarize Every N Messages",
            min_value=10, max_value=2000,
            value=int(st.session_state.config_manager.get_config('AUTO_SUMMARIZE_EVERY_N_MESSAGES') or st.session_state.config_manager.default_config.get('AUTO_SUMMARIZE_EVERY_N_MESSAGES', 100)),
            help="All chats are summarized when finished, or when they continue for up to this many messages.",
            key="auto_summarize",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        auto_summarize_max_tokens = st.number_input(
            "Auto Summarize After Token Usage",
            min_value=10000, max_value=500000, step=10000,
            value=int(st.session_state.config_manager.get_config('AUTO_SUMMARIZE_MAX_TOKENS') or st.session_state.config_manager.default_config.get('AUTO_SUMMARIZE_MAX_TOKENS', 50000)),
            help="Automatically summarize conversations when estimated token usage exceeds this value. Helps control costs by keeping context windows manageable. Default: 50,000 tokens (~$0.50-1.00 depending on model).",
            key="auto_summarize_max_tokens",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        supervisor_instructions = st.text_area(
            "Supervisor Instructions",
            value=st.session_state.config_manager.get_config('SUPERVISOR_INSTRUCTIONS') or "",
            help="Instructions for the supervisor describing important things to watch out for, and observations to make in summaries and in follow-up notes.",
            height=150,
            key="supervisor_instructions",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        st.markdown("---")
        st.markdown("### 💰 Cost Management")
        st.info("💡 Set cost limits and alerts to monitor API usage. Limits are informational only and won't stop conversations.")
        
        daily_cost_limit = st.number_input(
            "Daily Cost Limit ($)",
            min_value=0.0, max_value=1000.0, step=1.0,
            value=float(st.session_state.config_manager.get_config('DAILY_COST_LIMIT') or 0.0) if st.session_state.config_manager.get_config('DAILY_COST_LIMIT') is not None else 0.0,
            help="Maximum daily cost in dollars. Set to 0 to disable. When reached, a warning will be logged but conversations will continue.",
            key="daily_cost_limit",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        monthly_cost_limit = st.number_input(
            "Monthly Cost Limit ($)",
            min_value=0.0, max_value=10000.0, step=10.0,
            value=float(st.session_state.config_manager.get_config('MONTHLY_COST_LIMIT') or 0.0) if st.session_state.config_manager.get_config('MONTHLY_COST_LIMIT') is not None else 0.0,
            help="Maximum monthly cost in dollars. Set to 0 to disable. When reached, a warning will be logged.",
            key="monthly_cost_limit",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        cost_alert_threshold = st.number_input(
            "Cost Alert Threshold ($)",
            min_value=0.0, max_value=1000.0, step=1.0,
            value=float(st.session_state.config_manager.get_config('COST_ALERT_THRESHOLD') or 0.0) if st.session_state.config_manager.get_config('COST_ALERT_THRESHOLD') is not None else 0.0,
            help="Send email alert to primary contact when daily cost exceeds this amount. Set to 0 to disable alerts. Alerts are sent once per day.",
            key="cost_alert_threshold",
            on_change=lambda: lock_section() if not st.session_state.section_locked else None
        )
        
        # Show lock status
        if st.session_state.section_locked:
            st.info("🔒 Section is locked - use Save/Cancel buttons in sidebar to save changes or switch sections")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'notes':
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        
        render_improved_list_editor(
            section_key="notes",
            config_key="PRIOR_PRE_ESCALATION_NOTES",
            title="📋 Pre-Escalation Notes",
            instructions="This area holds notes that you AND the AI supervisor create to document observations about the user's experience.  Use this area to hold notes that are not actively part of the Chatty Friend conversation but should be kept in context for escalation of concerns over time.  Remove notes created by the supervisor that are not appropriate for ongoing consideration if needed.",
            item_label="Note"
        )
        
        st.markdown("</div>", unsafe_allow_html=True)
            
    elif current_section == 'contacts':  # Contacts Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("👥 Manage Contacts")
        
        # Instructions
        st.info("💡 **Instructions:** Add or edit contact information. Contacts marked as 'primary' can receive activity summaries. Be sure to click **SAVE CONTACTS** when done!")
        
        # Initialize contacts in session state if not exists
        if 'modal_contacts' not in st.session_state:
            st.session_state.modal_contacts = st.session_state.config_manager.get_config('CONTACTS') or []
        
        contacts = st.session_state.modal_contacts
        
        # Display existing contacts
        for i, contact in enumerate(contacts):
            st.write(f"**Contact {i+1}**")
            col1, col2, col3, col4, col5 = st.columns([2, 2, 3, 2, 1])
            
            with col1:
                contact['name'] = st.text_input("Name", value=contact.get('name', ''), key=f"contact_name_{i}")
            
            with col2:
                contact['type'] = st.selectbox("Type", ['primary', 'other'], 
                                               index=0 if contact.get('type') == 'primary' else 1,
                                               key=f"contact_type_{i}")
            
            with col3:
                contact['email'] = st.text_input("Email", value=contact.get('email', ''), key=f"contact_email_{i}")
            
            with col4:
                contact['phone'] = st.text_input("Phone", value=contact.get('phone', ''), key=f"contact_phone_{i}")
            
            with col5:
                st.write("")  # Spacing
                if st.button("🗑️", key=f"delete_contact_{i}", help="Delete contact"):
                    st.session_state.modal_contacts.pop(i)
                    st.rerun()
            
            st.divider()
        
        # Add new contact button
        if st.button("➕ Add Contact", key="add_contact"):
            st.session_state.modal_contacts.append({'name': '', 'type': 'other', 'email': '', 'phone': ''})
            st.rerun()
        
        if st.button("💾 Save Contacts", type="primary", key="save_contacts"):
            success, message = st.session_state.config_manager.save_config({
                'CONTACTS': st.session_state.modal_contacts
            })
            if success:
                st.success("✅ Contacts saved!")
            else:
                st.error(f"❌ Error saving contacts: {message}")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'password':  # Password Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("🔑 Change Password")
        
        # Instructions
        st.info("💡 **Instructions:** Enter a new password below. The password is used to access this configuration interface.")
        
        new_password = st.text_input("New Password", type="password", key="new_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        hint = st.text_input("Password Hint (optional)", key="password_hint")
        
        if st.button("🔑 Change Password", type="primary", key="change_password_action"):
            if new_password and new_password == confirm_password:
                success, message = st.session_state.config_manager.save_config({
                    'CONFIG_PASSWORD': new_password,
                    'CONFIG_PASSWORD_HINT': hint
                })
                if success:
                    st.success("✅ Password changed successfully!")
                else:
                    st.error(f"❌ Error changing password: {message}")
            elif not new_password:
                st.warning("⚠️ Please enter a password")
            else:
                st.error("❌ Passwords do not match")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'wifi':  # WiFi Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("📡 WiFi Configuration")
        
        if IS_PI:
            current_ssid = st.session_state.config_manager.get_config('WIFI_SSID')
            if current_ssid:
                st.success(f"✅ Current WiFi: {current_ssid}")
            else:
                st.warning("No WiFi configured")
            
            st.info("⚠️ Changing WiFi will restart the system")
            
            with st.form("wifi_change_form"):
                new_ssid = st.text_input("Network Name (SSID)", key="new_wifi_ssid")
                new_password = st.text_input("Password", type="password", key="new_wifi_password")
                
                if st.form_submit_button("📡 Save & Restart", type="primary"):
                    if new_ssid.strip() and new_password.strip():
                        # Save WiFi configuration
                        success, message = st.session_state.config_manager.save_config({
                            'WIFI_SSID': new_ssid.strip(),
                            'WIFI_PASSWORD': new_password.strip()
                        })
                        
                        if success:
                            st.success("✅ WiFi settings saved! System will restart...")
                            time.sleep(2)
                            # On Pi, restart the system
                            if not TESTING_PI_UI_MOCK_SYSTEM_CALLS:
                                subprocess.run(['sudo', 'reboot'], check=False)
                        else:
                            st.error(f"❌ Error saving WiFi settings: {message}")
                    else:
                        st.error("❌ Please enter both SSID and password")
        else:
            st.info("Network configuration is only available on Raspberry Pi")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'remote_config':  # Remote Configuration Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("☁️ Remote Configuration")
        
        if not SUPABASE_CONFIGURED:
            st.warning("⚠️ Supabase is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY environment variables to enable cloud sync.")
            st.info("💡 Cloud sync allows you to:\n- Backup device configuration\n- Restore settings after hardware replacement\n- Track usage statistics remotely")
        else:
            # Initialize Supabase manager in session state
            if 'supabase_manager' not in st.session_state:
                st.session_state.supabase_manager = get_supabase_manager(
                    st.session_state.config_manager,
                    st.session_state.secrets_manager
                )
            
            supabase = st.session_state.supabase_manager
            
            # State 1: Not authenticated - show login/signup
            if not supabase.is_authenticated():
                st.info("💡 Sign in to enable cloud backup and remote configuration for this device.")
                
                tab_login, tab_signup, tab_reset = st.tabs(["Login", "Create Account", "Reset Password"])
                
                with tab_login:
                    with st.form("supabase_login_form"):
                        email = st.text_input("Email", key="login_email")
                        password = st.text_input("Password", type="password", key="login_password")
                        
                        if st.form_submit_button("🔓 Login", type="primary"):
                            if email and password:
                                success, message = supabase.login(email, password)
                                if success:
                                    st.success(f"✅ {message}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                            else:
                                st.warning("Please enter email and password")
                
                with tab_signup:
                    with st.form("supabase_signup_form"):
                        new_email = st.text_input("Email", key="signup_email")
                        new_password = st.text_input("Password (min 6 characters)", type="password", key="signup_password")
                        confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm")
                        
                        if st.form_submit_button("📝 Create Account", type="primary"):
                            if not new_email:
                                st.warning("Please enter an email address")
                            elif len(new_password) < 6:
                                st.warning("Password must be at least 6 characters")
                            elif new_password != confirm_password:
                                st.error("Passwords do not match")
                            else:
                                success, message = supabase.signup(new_email, new_password)
                                if success:
                                    st.success(f"✅ {message}")
                                    st.info("📧 **Check your email!** Click the confirmation link to verify your account, then come back here and log in.")
                                else:
                                    st.error(f"❌ {message}")
                
                with tab_reset:
                    with st.form("supabase_reset_form"):
                        reset_email = st.text_input("Email", key="reset_email")
                        
                        if st.form_submit_button("📧 Send Reset Email"):
                            if reset_email:
                                success, message = supabase.send_password_reset(reset_email)
                                if success:
                                    st.success(f"✅ {message}")
                                else:
                                    st.error(f"❌ {message}")
                            else:
                                st.warning("Please enter your email address")
            
            # State 2: Authenticated but no device linked
            elif not supabase.is_device_linked():
                st.success(f"✅ Logged in as: {supabase.user_email}")
                
                if st.button("🚪 Logout", key="logout_no_device"):
                    supabase.logout()
                    st.rerun()
                
                st.divider()
                st.subheader("Link This Device")
                st.info("💡 Choose to link to an existing device backup or register this as a new device.")
                
                # Fetch user's devices
                devices = supabase.get_user_devices()
                
                if devices:
                    st.markdown("### Existing Device Backups")
                    
                    # Create a selectbox for existing devices
                    device_options = {d['id']: f"{d['name']} ({d['location']})" for d in devices}
                    device_options['new'] = "➕ Register as New Device"
                    
                    selected = st.selectbox(
                        "Select a device to link to:",
                        options=list(device_options.keys()),
                        format_func=lambda x: device_options[x],
                        key="selected_device_id"
                    )
                    
                    if selected and selected != 'new':
                        # Link to existing device
                        selected_device = next((d for d in devices if d['id'] == selected), None)
                        if selected_device:
                            st.info(f"**Device:** {selected_device['name']}\n\n**Location:** {selected_device['location']}\n\n**Last seen:** {selected_device.get('last_seen', 'Never')}")
                            
                            with st.form("link_device_form"):
                                passphrase = st.text_input(
                                    "Enter your passphrase to decrypt settings:",
                                    type="password",
                                    key="link_passphrase"
                                )
                                
                                if st.form_submit_button("🔗 Link to This Device", type="primary"):
                                    if passphrase:
                                        success, message, config_data, secrets_data = supabase.link_device(
                                            selected, passphrase
                                        )
                                        if success:
                                            # Apply downloaded config (cloud wins, volume local)
                                            if config_data:
                                                local_config = st.session_state.config_manager.config.copy()
                                                merged = config_data.copy()
                                                merged["VOLUME"] = local_config.get("VOLUME", merged.get("VOLUME"))
                                                merged["SPEED"] = local_config.get("SPEED", merged.get("SPEED"))
                                                st.session_state.config_manager.save_config(merged)
                                            
                                            # Apply downloaded secrets
                                            if secrets_data:
                                                import json
                                                st.session_state.secrets_manager.save_secrets(json.dumps(secrets_data))
                                            
                                            st.success("✅ Device linked successfully! Configuration restored.")
                                            st.rerun()
                                        else:
                                            st.error(f"❌ {message}")
                                    else:
                                        st.warning("Please enter your passphrase")
                    
                    if selected == 'new':
                        st.markdown("### Register as New Device")
                else:
                    st.markdown("### Register This Device")
                    st.info("No existing devices found. Register this device to enable cloud backup.")
                
                # Show new device registration form
                if not devices or (st.session_state.get('selected_device_id') == 'new'):
                    with st.form("register_device_form"):
                        device_name = st.text_input(
                            "Device Name",
                            placeholder="e.g., Living Room Assistant",
                            key="device_name"
                        )
                        device_location = st.text_input(
                            "Device Location",
                            placeholder="e.g., Mom's House",
                            key="device_location"
                        )
                        passphrase = st.text_input(
                            "Create a Passphrase",
                            type="password",
                            help="This passphrase encrypts your API keys. You'll need it to restore settings on a new device.",
                            key="device_passphrase"
                        )
                        passphrase_confirm = st.text_input(
                            "Confirm Passphrase",
                            type="password",
                            key="device_passphrase_confirm"
                        )
                        
                        st.warning("⚠️ **Important:** Remember your passphrase! It's required to restore your settings on a replacement device.")
                        
                        if st.form_submit_button("☁️ Register & Upload", type="primary"):
                            if not device_name:
                                st.error("Please enter a device name")
                            elif not passphrase:
                                st.error("Please create a passphrase")
                            elif passphrase != passphrase_confirm:
                                st.error("Passphrases do not match")
                            else:
                                success, result = supabase.register_new_device(
                                    device_name,
                                    device_location,
                                    passphrase,
                                    st.session_state.config_manager.config,
                                    st.session_state.secrets_manager.secrets
                                )
                                if success:
                                    st.success(f"✅ Device registered successfully!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result}")
            
            # State 3: Authenticated and device linked
            else:
                st.success(f"✅ Logged in as: {supabase.user_email}")
                st.success(f"✅ Device linked: {supabase.device_id[:8]}...")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔄 Sync Now", key="manual_sync"):
                        try:
                            usage = {"cost": 0, "message_count": 0}
                            success, new_config, _ = supabase.sync_at_conversation_end(
                                usage,
                                st.session_state.config_manager.config
                            )
                            if success:
                                if new_config:
                                    st.session_state.config_manager.save_config(new_config)
                                    st.success("✅ Synced and applied new configuration!")
                                else:
                                    st.success("✅ Synced successfully!")
                                
                                if supabase.check_upgrade_pending():
                                    st.warning("⚠️ A software upgrade is available. Restart the device to apply.")
                            else:
                                st.warning("⚠️ Sync encountered an issue but device continues to work offline.")
                        except Exception as e:
                            st.error(f"❌ Sync failed: {e}")
                
                with col2:
                    if st.button("🚪 Logout", key="logout_linked"):
                        supabase.logout()
                        st.rerun()
                
                st.divider()
                
                # Upload current config
                st.subheader("Upload Configuration")
                st.info("💡 Upload your current settings to the cloud for backup.")
                
                with st.form("upload_config_form"):
                    passphrase = st.text_input(
                        "Enter passphrase to encrypt secrets:",
                        type="password",
                        key="upload_passphrase"
                    )
                    
                    if st.form_submit_button("☁️ Upload Current Config", type="primary"):
                        if passphrase:
                            success, message = supabase.upload_config(
                                st.session_state.config_manager.config,
                                st.session_state.secrets_manager.secrets,
                                passphrase
                            )
                            if success:
                                st.success(f"✅ {message}")
                            else:
                                st.error(f"❌ {message}")
                        else:
                            st.warning("Please enter your passphrase")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'ai':  # AI Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("🤖 AI Model Configuration")
        st.warning("⚠️ Don't edit these settings unless you know what you're doing!")
        
        with st.form("ai_settings_form"):
            from chatty_config import ConfigManager
            default_config = ConfigManager().default_config
            
            realtime_model = st.text_input(
                "Realtime Model",
                value=st.session_state.config_manager.get_config('REALTIME_MODEL') or default_config['REALTIME_MODEL'],
                key="realtime_model"
            )
            
            transcription_model = st.text_input(
                "Audio Transcription Model",
                value=st.session_state.config_manager.get_config('AUDIO_TRANSCRIPTION_MODEL') or default_config['AUDIO_TRANSCRIPTION_MODEL'],
                key="transcription_model"
            )
            
            supervisor_model = st.text_input(
                "Supervisor Model",
                value=st.session_state.config_manager.get_config('SUPERVISOR_MODEL') or default_config['SUPERVISOR_MODEL'],
                key="supervisor_model"
            )
            
            ws_url = st.text_input(
                "WebSocket URL",
                value=st.session_state.config_manager.get_config('WS_URL') or default_config['WS_URL'],
                key="ws_url"
            )
            
            if st.form_submit_button("💾 Save AI Settings", type="primary"):
                if realtime_model.strip() and transcription_model.strip() and ws_url.strip():
                    success, message = st.session_state.config_manager.save_config({
                        'REALTIME_MODEL': realtime_model.strip(),
                        'AUDIO_TRANSCRIPTION_MODEL': transcription_model.strip(),
                        'SUPERVISOR_MODEL': supervisor_model.strip(),
                        'WS_URL': ws_url.strip()
                    })
                    if success:
                        st.success("✅ AI settings saved!")
                    else:
                        st.error(f"❌ Error saving AI settings: {message}")
                else:
                    st.error("❌ Please fill in all required fields")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'personality':  # Personality Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("🎭 Assistant Personality")
        
        # System prompt
        current_prompt = st.session_state.config_manager.get_config('VOICE_ASSISTANT_SYSTEM_PROMPT') or ""
        
        system_prompt = st.text_area(
            "System Prompt",
            value=current_prompt,
            height=200,
            help="This defines how the assistant behaves and responds",
            key="system_prompt"
        )
        
        # Voice settings
        st.subheader("🎵 Voice Settings")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            voice_choices = st.session_state.config_manager.get_config('VOICE_CHOICES') or ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
            current_voice = st.session_state.config_manager.get_config('VOICE') or 'alloy'
            voice_index = voice_choices.index(current_voice) if current_voice in voice_choices else 0
            
            selected_voice = st.selectbox(
                "Voice",
                options=voice_choices,
                index=voice_index,
                key="selected_voice"
            )
        
        with col2:
            volume = st.slider(
                "Volume",
                min_value=0, max_value=100,
                value=int(st.session_state.config_manager.get_config('VOLUME') or 50),
                key="volume_setting"
            )
        
        with col3:
            speed = st.slider(
                "Speed",
                min_value=0, max_value=100,
                value=int(st.session_state.config_manager.get_config('SPEED') or 50),
                key="speed_setting"
            )
        
        # Eagerness setting
        eagerness = st.slider(
            "Assistant Eagerness to Reply",
            min_value=0, max_value=100,
            value=int(st.session_state.config_manager.get_config('ASSISTANT_EAGERNESS_TO_REPLY') or 50),
            help="How quickly the assistant jumps into conversations",
            key="eagerness_setting"
        )
        
        if st.button("💾 Save Personality Settings", type="primary", key="save_personality"):
            success, message = st.session_state.config_manager.save_config({
                'VOICE_ASSISTANT_SYSTEM_PROMPT': system_prompt,
                'VOICE': selected_voice,
                'VOLUME': volume,
                'SPEED': speed,
                'ASSISTANT_EAGERNESS_TO_REPLY': eagerness
            })
            if success:
                st.success("✅ Personality settings saved!")
            else:
                st.error(f"❌ Error saving settings: {message}")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'content':  # Content Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("Content Settings")
        
        news_providers = list(RSS_NEWS_FEEDS.keys())
        current_provider = st.session_state.config_manager.get_config('NEWS_PROVIDER') or 'BBC'
        provider_index = news_providers.index(current_provider) if current_provider in news_providers else 0
        
        news_provider = st.selectbox(
            "News Provider",
            options=news_providers,
            index=provider_index,
            key="news_provider"
        )
        
        if st.button("💾 Save Content Settings", type="primary", key="save_content"):
            config_updates = {
                'NEWS_PROVIDER': news_provider
            }
            success, message = st.session_state.config_manager.save_config(config_updates)
            if success:
                st.success("✅ Content settings saved!")
            else:
                st.error(f"❌ Error saving settings: {message}")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'voice_tech':  # Voice Tech Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("Voice Technology Settings")
        
        st.warning("Don't edit these settings unless you know what you're doing!")
        
        # Voice Activity Detection
        vad_threshold = st.number_input(
            "Voice Activity Detection Threshold",
            min_value=0.0, max_value=1.0, step=0.01,
            value=float(st.session_state.config_manager.get_config('VAD_THRESHOLD') or 0.3),
            help="Sensitivity for detecting when you start speaking (lower = more sensitive)",
            key="vad_threshold"
        )
        
        # Voice wait time
        voice_wait_time = st.number_input(
            "Seconds to Wait for More Voice",
            min_value=0.1, max_value=5.0, step=0.1,
            value=float(st.session_state.config_manager.get_config('SECONDS_TO_WAIT_FOR_MORE_VOICE') or 1.0),
            help="How long to wait for more speech before processing",
            key="voice_wait_time"
        )
        
        st.markdown("---")
        st.markdown("### Wake Word Detection (Cluster-Based)")
        st.info("These settings control how wake words are detected using cluster-based scoring. The system tracks scores over multiple frames and confirms detection via peak or cumulative thresholds.")
        
        # Wake Entry Threshold
        wake_entry_threshold = st.number_input(
            "Wake Entry Threshold",
            min_value=0.1, max_value=0.6, step=0.01,
            value=float(st.session_state.config_manager.get_config('WAKE_ENTRY_THRESHOLD') or 0.35),
            help="Score threshold to start tracking a potential wake word. Lower = more sensitive but more false positives.",
            key="wake_entry_threshold"
        )
        
        # Wake Confirm Peak
        wake_confirm_peak = st.number_input(
            "Wake Confirm Peak",
            min_value=0.2, max_value=0.8, step=0.01,
            value=float(st.session_state.config_manager.get_config('WAKE_CONFIRM_PEAK') or 0.45),
            help="Peak score required to confirm detection. If any frame reaches this, wake word is confirmed.",
            key="wake_confirm_peak"
        )
        
        # Wake Confirm Cumulative
        wake_confirm_cumulative = st.number_input(
            "Wake Confirm Cumulative",
            min_value=0.5, max_value=3.0, step=0.1,
            value=float(st.session_state.config_manager.get_config('WAKE_CONFIRM_CUMULATIVE') or 1.2),
            help="Alternative: cumulative score threshold for detection. Catches sustained moderate scores that don't peak high.",
            key="wake_confirm_cumulative"
        )
        
        st.markdown("---")
        st.markdown("### Auto-Noise Injection")
        st.info("Auto-noise helps wake word detection in quiet rooms by injecting synthetic noise to reach a target floor. Real acoustic noise actually helps model recognition.")
        
        # Noise Target Floor
        noise_target_floor = st.number_input(
            "Noise Target Floor (RMS)",
            min_value=50.0, max_value=200.0, step=10.0,
            value=float(st.session_state.config_manager.get_config('NOISE_TARGET_FLOOR') or 120.0),
            help="Target ambient noise floor. Auto-noise adds synthetic noise to reach this level in quiet environments.",
            key="noise_target_floor"
        )
        
        # Noise Max Injection
        noise_max_injection = st.number_input(
            "Noise Max Injection (RMS)",
            min_value=0.0, max_value=150.0, step=5.0,
            value=float(st.session_state.config_manager.get_config('NOISE_MAX_INJECTION') or 85.0),
            help="Maximum synthetic noise to inject. Capped to avoid over-injection which can hurt recognition.",
            key="noise_max_injection"
        )
        
        st.markdown("---")
        st.markdown("### Audio Processing")
        st.info("Additional audio processing settings. Disabled by default for optimal Raspberry Pi performance.")
        
        # Noise Gate Threshold
        noise_gate_threshold = st.number_input(
            "Noise Gate Threshold",
            min_value=0.0, max_value=5000.0, step=100.0,
            value=float(st.session_state.config_manager.get_config('NOISE_GATE_THRESHOLD') or 0.0) if st.session_state.config_manager.get_config('NOISE_GATE_THRESHOLD') is not None else 0.0,
            help="Enable noise gate to reduce background noise. Set to 0 to disable (recommended for RPi). Higher values = more aggressive noise filtering.",
            key="noise_gate_threshold"
        )
        
        if st.button("Save Voice Tech Settings", type="primary", key="save_voice_tech"):
            success, message = st.session_state.config_manager.save_config({
                'VAD_THRESHOLD': vad_threshold,
                'SECONDS_TO_WAIT_FOR_MORE_VOICE': voice_wait_time,
                'WAKE_ENTRY_THRESHOLD': wake_entry_threshold,
                'WAKE_CONFIRM_PEAK': wake_confirm_peak,
                'WAKE_CONFIRM_CUMULATIVE': wake_confirm_cumulative,
                'NOISE_TARGET_FLOOR': noise_target_floor,
                'NOISE_MAX_INJECTION': noise_max_injection,
                'NOISE_GATE_THRESHOLD': noise_gate_threshold if noise_gate_threshold > 0 else None
            })
            if success:
                st.success("Voice tech settings saved!")
            else:
                st.error(f"Error saving settings: {message}")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'secrets':  # Secrets Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("🔐 Update Secrets")
        
        st.info("💡 **Instructions:** Update API keys and sensitive configuration. Only the keys are shown for security - values are hidden.")
        
        # Show current secrets (keys only)
        secrets_manager = st.session_state.secrets_manager if hasattr(st.session_state, 'secrets_manager') else None
        
        if secrets_manager:
            st.write("**Current API Keys:**")
            for key in secrets_manager.required_secrets.keys():
                has_value = bool(secrets_manager.get_secret(key))
                status = "✅ Configured" if has_value else "❌ Not configured"
                st.write(f"- {key}: {status}")
        
        st.write("**Update Secrets (JSON format):**")
        secrets_input = st.text_area(
            "JSON Configuration",
            height=300,
            placeholder='{\n  "chat_api_key": "sk-proj-...",\n  "openweather_api_key": "your-key-here"\n}',
            key="secrets_json"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Save Secrets", type="primary", key="save_secrets"):
                if secrets_input.strip():
                    if secrets_manager:
                        success, message = secrets_manager.save_secrets(secrets_input)
                        if success:
                            st.success("✅ Secrets updated successfully!")
                        else:
                            st.error(f"❌ Error updating secrets: {message}")
                    else:
                        st.error("❌ Secrets manager not available")
                else:
                    st.warning("⚠️ Please enter secrets configuration")
        
        with col2:
            if st.button("🔄 Revert Changes", key="revert_secrets"):
                st.session_state.secrets_json = ""
                st.success("✅ Input cleared!")
                st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif current_section == 'reset':  # Reset Section
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.subheader("🔄 Reset to Defaults")
        
        st.error("⚠️ **DANGER ZONE** ⚠️")
        st.warning("This will reset ALL configuration settings to their default values!")
        st.info("💡 **Note:** This will not affect your API keys or secrets - only configuration settings.")
        
        with st.form("reset_form"):
            # Step 1: Checkbox
            confirm_reset = st.checkbox("I understand this will reset all settings")
            
            # Step 2: Type confirmation
            st.write("**Type the word** `RESET` **below to confirm:**")
            typed_confirmation = st.text_input("Type RESET here:")
            
            # Step 3: Show what will be preserved
            if confirm_reset:
                st.info("**These settings will be preserved:**")
                st.write("- CONFIG_PASSWORD")
                st.write("- CONFIG_PASSWORD_HINT")
                st.write("- All API keys and secrets")
            
            # Reset button
            submitted = st.form_submit_button(
                "🔄 Reset to Defaults", 
                type="primary"
            )
            
            if submitted:
                if not confirm_reset:
                    st.error("❌ Please check the confirmation box")
                elif typed_confirmation != "RESET":
                    st.error("❌ Please type RESET exactly")
                else:
                    # Do the reset
                    from chatty_config import ConfigManager
                    default_config = ConfigManager().default_config
                    
                    # Preserve certain settings
                    preserve_keys = ['CONFIG_PASSWORD', 'CONFIG_PASSWORD_HINT']
                    preserved = {key: st.session_state.config_manager.get_config(key) 
                                for key in preserve_keys 
                                if st.session_state.config_manager.get_config(key)}
                    
                    # Merge defaults with preserved settings
                    reset_config = {**default_config, **preserved}
                    
                    # Just save the reset config normally
                    success, message = st.session_state.config_manager.save_config(reset_config)
                    if success:
                        st.success("✅ Configuration reset to defaults!")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ Error resetting configuration: {message}")
        
        # System restart section
        if IS_PI:
            st.divider()
            st.subheader("🔄 System Restart")
            st.info("💡 Restart the entire system (Raspberry Pi only)")
            
            if st.button("🔄 Restart System", key="restart_system", type="secondary"):
                st.warning("🔄 System is restarting...")
                time.sleep(2)
                if not TESTING_PI_UI_MOCK_SYSTEM_CALLS:
                    subprocess.run(['sudo', 'reboot'], check=False)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    else:
        # Show current section content
        st.markdown("<div class='config-section'>", unsafe_allow_html=True)
        st.info(f"🚧 **{section_titles.get(current_section, current_section.title())}** section content will be displayed here.")
        st.write("Configuration forms for this section will be implemented based on the section requirements.")
        st.markdown("</div>", unsafe_allow_html=True)

# Simple vertical navigation system - sections lock when edited and require save/cancel to switch
