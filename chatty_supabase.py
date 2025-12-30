# Chatty Supabase
# Finley 2025
#
# Supabase integration for remote config, usage tracking, and device recovery

import json
import os
import time
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

from chatty_encryption import (
    encrypt_secrets, 
    decrypt_secrets, 
    generate_passphrase_hint,
    is_crypto_available
)

SUPABASE_URL = "https://bhwsnnqhzloipjeogtzl.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_6vooFKn2c72-50-Nejwdxg_MKg6WRHy"

def is_supabase_configured() -> bool:
    """Check if Supabase credentials have been set (not placeholders)."""
    return (
        SUPABASE_URL and 
        SUPABASE_ANON_KEY and 
        "YOUR_PROJECT_ID" not in SUPABASE_URL and
        "YOUR_ANON_PUBLIC_KEY" not in SUPABASE_ANON_KEY
    )

# Local file for storing auth tokens and device ID
SUPABASE_AUTH_FILE = "chatty_supabase_auth.json"


class SupabaseManager:
    """
    Manages Supabase authentication, device registration, and sync operations.
    Designed for graceful degradation - all operations fail silently if Supabase
    is unavailable or not configured.
    """
    
    def __init__(self, config_manager=None, secrets_manager=None):
        """
        Initialize the Supabase manager.
        
        Args:
            config_manager: Optional ConfigManager instance for config operations
            secrets_manager: Optional SecretsManager instance for secrets operations
        """
        self.client: Optional[Client] = None
        self.device_id: Optional[str] = None
        self.user_email: Optional[str] = None
        self.auth_file = SUPABASE_AUTH_FILE
        self.config_manager = config_manager
        self.secrets_manager = secrets_manager
        
        # Load saved auth state
        self._load_auth_state()
        
        # Initialize client if credentials available
        self._init_client()
    
    def _init_client(self) -> bool:
        """Initialize Supabase client if available and configured."""
        if not SUPABASE_AVAILABLE:
            return False
        
        if not is_supabase_configured():
            return False
        
        try:
            self.client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            
            # Try to restore session from saved tokens
            auth_data = self._load_auth_file()
            if auth_data and auth_data.get("refresh_token"):
                try:
                    # Attempt to refresh the session
                    self.client.auth.set_session(
                        auth_data.get("access_token", ""),
                        auth_data.get("refresh_token", "")
                    )
                    # Refresh to get new tokens
                    response = self.client.auth.refresh_session()
                    if response and response.session:
                        self._save_session(response.session)
                        return True
                except Exception as e:
                    print(f"Session refresh failed: {e}")
                    # Clear invalid auth state
                    self._clear_auth_state()
            
            return True
        except Exception as e:
            print(f"Failed to initialize Supabase client: {e}")
            return False
    
    def _load_auth_file(self) -> Optional[Dict[str, Any]]:
        """Load auth data from local file."""
        try:
            if os.path.exists(self.auth_file):
                with open(self.auth_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading Supabase auth file: {e}")
        return None
    
    def _save_auth_file(self, data: Dict[str, Any]) -> bool:
        """Save auth data to local file."""
        try:
            with open(self.auth_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving Supabase auth file: {e}")
            return False
    
    def _load_auth_state(self):
        """Load device ID and user email from saved auth state."""
        auth_data = self._load_auth_file()
        if auth_data:
            self.device_id = auth_data.get("device_id")
            self.user_email = auth_data.get("user_email")
    
    def _save_session(self, session) -> bool:
        """Save Supabase session to local file."""
        if not session:
            return False
        
        auth_data = {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": session.expires_at if hasattr(session, 'expires_at') else None,
            "device_id": self.device_id,
            "user_email": session.user.email if session.user else self.user_email
        }
        
        if session.user:
            self.user_email = session.user.email
        
        return self._save_auth_file(auth_data)
    
    def _clear_auth_state(self):
        """Clear all auth state (logout)."""
        self.device_id = None
        self.user_email = None
        try:
            if os.path.exists(self.auth_file):
                os.remove(self.auth_file)
        except Exception as e:
            print(f"Error removing auth file: {e}")
    
    def is_available(self) -> bool:
        """Check if Supabase is available and configured."""
        return (
            SUPABASE_AVAILABLE and 
            is_supabase_configured() and 
            self.client is not None
        )
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated with Supabase."""
        if not self.is_available():
            return False
        
        try:
            user = self.client.auth.get_user()
            return user is not None and user.user is not None
        except Exception:
            return False
    
    def is_device_linked(self) -> bool:
        """Check if this device is linked to a Supabase device record."""
        return self.device_id is not None and self.is_authenticated()
    
    def login(self, email: str, password: str) -> Tuple[bool, str]:
        """
        Authenticate user with email and password.
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            Tuple of (success, message)
        """
        if not self.is_available():
            return False, "Supabase is not configured"
        
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response and response.session:
                self._save_session(response.session)
                return True, "Login successful"
            else:
                return False, "Login failed: no session returned"
                
        except Exception as e:
            error_msg = str(e)
            if "Invalid login credentials" in error_msg:
                return False, "Invalid email or password"
            return False, f"Login failed: {error_msg}"
    
    def signup(self, email: str, password: str) -> Tuple[bool, str]:
        """
        Create a new user account.
        
        Args:
            email: User's email address
            password: User's password (min 6 characters)
            
        Returns:
            Tuple of (success, message)
        """
        if not self.is_available():
            return False, "Supabase is not configured"
        
        if len(password) < 6:
            return False, "Password must be at least 6 characters"
        
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if response and response.user:
                if response.session:
                    self._save_session(response.session)
                    return True, "Account created and logged in"
                else:
                    return True, "Account created. Please check your email to verify."
            else:
                return False, "Signup failed"
                
        except Exception as e:
            error_msg = str(e)
            if "already registered" in error_msg.lower():
                return False, "This email is already registered"
            return False, f"Signup failed: {error_msg}"
    
    def logout(self):
        """Log out and clear all auth state."""
        if self.is_available():
            try:
                self.client.auth.sign_out()
            except Exception as e:
                print(f"Error during Supabase sign out: {e}")
        
        self._clear_auth_state()
    
    def send_password_reset(self, email: str) -> Tuple[bool, str]:
        """
        Send password reset email.
        
        Args:
            email: User's email address
            
        Returns:
            Tuple of (success, message)
        """
        if not self.is_available():
            return False, "Supabase is not configured"
        
        try:
            self.client.auth.reset_password_email(email)
            return True, "Password reset email sent"
        except Exception as e:
            return False, f"Failed to send reset email: {e}"
    
    def get_user_devices(self) -> List[Dict[str, Any]]:
        """
        Get list of devices owned by the current user.
        
        Returns:
            List of device records (id, name, location, last_seen)
        """
        if not self.is_authenticated():
            return []
        
        try:
            response = self.client.table("devices").select(
                "id, name, location, current_version, last_seen, created_at"
            ).execute()
            
            return response.data if response.data else []
        except Exception as e:
            print(f"Error fetching devices: {e}")
            return []
    
    def register_new_device(
        self, 
        name: str, 
        location: str, 
        passphrase: str,
        config_data: Optional[Dict] = None,
        secrets_data: Optional[Dict] = None,
        current_version: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Register this device as a new device in Supabase.
        
        Args:
            name: Device name (e.g., "Living Room Assistant")
            location: Device location (e.g., "Mom's House")
            passphrase: Passphrase for encrypting secrets
            config_data: Optional config dict (will use ConfigManager if not provided)
            secrets_data: Optional secrets dict (will use SecretsManager if not provided)
            current_version: Optional version string
            
        Returns:
            Tuple of (success, message or device_id)
        """
        if not self.is_authenticated():
            return False, "Not authenticated"
        
        if not is_crypto_available():
            return False, "Encryption not available"
        
        try:
            # Get config data
            if config_data is None and self.config_manager:
                config_data = self.config_manager.config.copy()
            elif config_data is None:
                config_data = {}
            
            # Get secrets data
            if secrets_data is None and self.secrets_manager:
                secrets_data = self.secrets_manager.secrets.copy()
            elif secrets_data is None:
                secrets_data = {}
            
            # Get version
            if current_version is None:
                from chatty_config import CHATTY_FRIEND_VERSION_NUMBER
                current_version = CHATTY_FRIEND_VERSION_NUMBER
            
            # Encrypt secrets
            encrypted_secrets = encrypt_secrets(secrets_data, passphrase)
            passphrase_hint = generate_passphrase_hint(passphrase)
            
            # Insert device record
            response = self.client.table("devices").insert({
                "name": name,
                "location": location,
                "config_data": config_data,
                "secrets_encrypted": encrypted_secrets,
                "secrets_passphrase_hint": passphrase_hint,
                "current_version": current_version,
                "last_seen": datetime.utcnow().isoformat()
            }).execute()
            
            if response.data and len(response.data) > 0:
                device_id = response.data[0]["id"]
                self.device_id = device_id
                
                # Update auth file with device ID
                auth_data = self._load_auth_file() or {}
                auth_data["device_id"] = device_id
                self._save_auth_file(auth_data)
                
                return True, device_id
            else:
                return False, "Failed to create device record"
                
        except Exception as e:
            return False, f"Failed to register device: {e}"
    
    def link_device(
        self, 
        device_id: str, 
        passphrase: str
    ) -> Tuple[bool, str, Optional[Dict], Optional[Dict]]:
        """
        Link this device to an existing device record and download its config.
        
        Args:
            device_id: UUID of the device to link to
            passphrase: Passphrase to decrypt secrets
            
        Returns:
            Tuple of (success, message, config_data, secrets_data)
        """
        if not self.is_authenticated():
            return False, "Not authenticated", None, None
        
        try:
            # Fetch device record
            response = self.client.table("devices").select(
                "id, config_data, secrets_encrypted"
            ).eq("id", device_id).execute()
            
            if not response.data or len(response.data) == 0:
                return False, "Device not found", None, None
            
            device = response.data[0]
            
            # Decrypt secrets
            encrypted_secrets = device.get("secrets_encrypted")
            if encrypted_secrets:
                secrets_data = decrypt_secrets(encrypted_secrets, passphrase)
                if secrets_data is None:
                    return False, "Invalid passphrase", None, None
            else:
                secrets_data = {}
            
            config_data = device.get("config_data", {})
            
            # Store device ID locally
            self.device_id = device_id
            auth_data = self._load_auth_file() or {}
            auth_data["device_id"] = device_id
            self._save_auth_file(auth_data)
            
            return True, "Device linked successfully", config_data, secrets_data
            
        except Exception as e:
            return False, f"Failed to link device: {e}", None, None
    
    def sync_at_conversation_end(
        self, 
        usage_stats: Dict[str, Any],
        local_config: Optional[Dict] = None,
        local_secrets: Optional[Dict] = None,
        passphrase: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict], Optional[Dict]]:
        """
        Sync with Supabase at the end of a conversation.
        Try once, fail silently if unsuccessful.
        
        Args:
            usage_stats: Dict with 'cost' and 'message_count'
            local_config: Current local config (for volume preservation)
            local_secrets: Current local secrets (for upload if changed)
            passphrase: Passphrase for secrets encryption (only if uploading changes)
            
        Returns:
            Tuple of (success, new_config_if_any, new_secrets_if_any)
        """
        if not self.is_device_linked():
            return False, None, None
        
        try:
            # 1. Record usage activity
            self._record_activity(usage_stats)
            
            # 2. Update last_seen and current_version
            from chatty_config import CHATTY_FRIEND_VERSION_NUMBER
            self.client.table("devices").update({
                "last_seen": datetime.utcnow().isoformat(),
                "current_version": CHATTY_FRIEND_VERSION_NUMBER
            }).eq("id", self.device_id).execute()
            
            # 3. Check for config updates
            response = self.client.table("devices").select(
                "config_data, secrets_encrypted, config_pending, upgrade_pending"
            ).eq("id", self.device_id).execute()
            
            if not response.data or len(response.data) == 0:
                return True, None, None
            
            device = response.data[0]
            
            new_config = None
            new_secrets = None
            
            # 4. If config_pending, download new config
            if device.get("config_pending"):
                cloud_config = device.get("config_data", {})
                
                # Merge: cloud wins, except volume settings stay local
                if local_config and cloud_config:
                    new_config = self._merge_config(local_config, cloud_config)
                elif cloud_config:
                    new_config = cloud_config
                
                # Clear the pending flag
                self.client.table("devices").update({
                    "config_pending": False
                }).eq("id", self.device_id).execute()
            
            return True, new_config, new_secrets
            
        except Exception as e:
            print(f"Supabase sync failed (continuing anyway): {e}")
            return False, None, None
    
    def _merge_config(self, local_config: Dict, cloud_config: Dict) -> Dict:
        """
        Merge configs: cloud wins, except volume settings stay local.
        
        Args:
            local_config: Local configuration
            cloud_config: Cloud configuration
            
        Returns:
            Merged configuration
        """
        merged = cloud_config.copy()
        
        # Local volume settings win
        if "VOLUME" in local_config:
            merged["VOLUME"] = local_config["VOLUME"]
        if "SPEED" in local_config:
            merged["SPEED"] = local_config["SPEED"]
        
        return merged
    
    def _record_activity(self, usage_stats: Dict[str, Any]) -> bool:
        """Record device activity to Supabase."""
        if not self.device_id:
            return False
        
        try:
            self.client.table("device_activity").insert({
                "device_id": self.device_id,
                "session_end": datetime.utcnow().isoformat(),
                "message_count": usage_stats.get("message_count", 0),
                "cost": usage_stats.get("cost", 0)
            }).execute()
            return True
        except Exception as e:
            print(f"Failed to record activity: {e}")
            return False
    
    def check_upgrade_pending(self) -> bool:
        """
        Check if an upgrade is pending for this device.
        
        Returns:
            True if device should upgrade, False otherwise
        """
        if not self.is_device_linked():
            return False
        
        try:
            response = self.client.table("devices").select(
                "upgrade_pending, target_version, current_version"
            ).eq("id", self.device_id).execute()
            
            if response.data and len(response.data) > 0:
                device = response.data[0]
                
                # Check explicit flag
                if device.get("upgrade_pending"):
                    return True
                
                # Check version mismatch
                target = device.get("target_version")
                current = device.get("current_version")
                if target and current and target != current:
                    return True
            
            return False
        except Exception as e:
            print(f"Error checking upgrade status: {e}")
            return False
    
    def upload_config(
        self, 
        config_data: Dict, 
        secrets_data: Optional[Dict] = None,
        passphrase: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Upload local config (and optionally secrets) to Supabase.
        
        Args:
            config_data: Configuration dictionary to upload
            secrets_data: Optional secrets to upload (requires passphrase)
            passphrase: Passphrase for secrets encryption
            
        Returns:
            Tuple of (success, message)
        """
        if not self.is_device_linked():
            return False, "Device not linked"
        
        try:
            update_data = {
                "config_data": config_data,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Encrypt and include secrets if provided
            if secrets_data and passphrase:
                encrypted_secrets = encrypt_secrets(secrets_data, passphrase)
                update_data["secrets_encrypted"] = encrypted_secrets
                update_data["secrets_passphrase_hint"] = generate_passphrase_hint(passphrase)
            
            self.client.table("devices").update(update_data).eq(
                "id", self.device_id
            ).execute()
            
            return True, "Config uploaded successfully"
            
        except Exception as e:
            return False, f"Failed to upload config: {e}"


# Singleton instance for convenience
_supabase_manager: Optional[SupabaseManager] = None


def get_supabase_manager(
    config_manager=None, 
    secrets_manager=None
) -> SupabaseManager:
    """
    Get the singleton SupabaseManager instance.
    
    Args:
        config_manager: Optional ConfigManager to use
        secrets_manager: Optional SecretsManager to use
        
    Returns:
        SupabaseManager instance
    """
    global _supabase_manager
    
    if _supabase_manager is None:
        _supabase_manager = SupabaseManager(config_manager, secrets_manager)
    elif config_manager:
        _supabase_manager.config_manager = config_manager
    elif secrets_manager:
        _supabase_manager.secrets_manager = secrets_manager
    
    return _supabase_manager

