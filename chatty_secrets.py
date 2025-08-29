# Chatty Secrets
# Finley 2025

import json
import os
from typing import Optional, Dict, Any

class SecretsManager:
    """
    Centralized secrets management for Chatty Friend Voice Assistant.
    Loads API keys and sensitive configuration from chatty_secrets.json file.
    """
    
    def __init__(self, secrets_file: str = "chatty_secrets.json"):
        self.secrets_file = secrets_file
        self.secrets = {}
        self.required_secrets = {
            "chat_api_key": {
                "description": "OpenAI API key",
                "url": "https://platform.openai.com/api-keys",
                "example": "sk-proj-abc123... (OpenAI)",
                "required": True
            },
            "openweather_api_key": {
                "description": "OpenWeatherMap API key for weather information",
                "url": "https://openweathermap.org/api",
                "example": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                "required": False
            },
            "google_search_api_key": {
                "description": "Google Search API key for internet searches",
                "url": "https://www.googleapis.com/customsearch/v1?key=",
                "example": "abc123def456ghi789jkl012mno345pqr678",
                "required": False
            },
            "twilio_account_sid": {
                "description": "Twilio Account SID for SMS notifications",
                "url": "https://console.twilio.com/",
                "example": "your-twilio-sid",
                "required": False
            },
            "twilio_auth_token": {
                "description": "Twilio Auth Token for SMS notifications",
                "url": "https://console.twilio.com/",
                "example": "1234567890abcdef1234567890abcdef",
                "required": False
            },
            "twilio_phone_number": {
                "description": "Twilio phone number for SMS notifications (format: +1234567890)",
                "url": "https://console.twilio.com/",
                "example": "+1234567890",
                "required": False
            },
            "email_smtp_server": {
                "description": "SMTP server for email notifications (e.g., smtp.gmail.com)",
                "url": "https://support.google.com/mail/answer/7126229",
                "example": "smtp.gmail.com",
                "required": False
            },
            "email_smtp_port": {
                "description": "SMTP port for email notifications (usually 587 for TLS)",
                "url": "https://support.google.com/mail/answer/7126229",
                "example": "587",
                "required": False
            },
            "email_username": {
                "description": "Email username for notifications",
                "url": "https://support.google.com/mail/answer/7126229",
                "example": "your.email@gmail.com",
                "required": False
            },
            "email_password": {
                "description": "Email password or app-specific password for notifications",
                "url": "https://support.google.com/mail/answer/7126229",
                "example": "your_app_specific_password",
                "required": False
            },
        }
        
        self.load_secrets()

        # check the environment for secrets too
        for k in self.required_secrets:
            if k in os.environ and not self.secrets.get(k):
                self.secrets[k] = os.environ[k]
        
    def load_secrets(self) -> bool:
        """Load secrets from JSON file"""
        try:
            if os.path.exists(self.secrets_file):
                with open(self.secrets_file, 'r', encoding='utf-8') as f:
                    self.secrets = json.load(f)
                    if not isinstance(self.secrets, dict):
                        print(f"Warning: {self.secrets_file} should contain a JSON object")
                        self.secrets = {}
                        return False
                print(f"Loaded secrets from {self.secrets_file}")
                return True
            else:
                print(f"Secrets file {self.secrets_file} not found")
                return False
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {self.secrets_file}: {e}")
            return False
        except Exception as e:
            print(f"Error loading secrets from {self.secrets_file}: {e}")
            return False
    
    def save_secrets(self, secrets_json: str) -> tuple[bool, str]:
        """Save secrets from JSON string to file"""
        try:
            # Parse JSON string
            new_secrets = json.loads(secrets_json)
            if not isinstance(new_secrets, dict):
                return False, "Secrets must be a JSON object (dictionary)"
            
            # Merge with existing secrets (update/add new keys, preserve existing ones)
            merged_secrets = self.secrets.copy()  # Start with existing secrets
            merged_secrets.update(new_secrets)    # Add/update with new secrets

            # pop old keys that are no longer in the list
            pop_not_required = []
            for k in merged_secrets:
                if k not in self.required_secrets:
                    pop_not_required.append(k)  
            for k in pop_not_required:
                merged_secrets.pop(k)
            
            # Save merged secrets to file
            with open(self.secrets_file, 'w', encoding='utf-8') as f:
                json.dump(merged_secrets, f, indent=2)
            
            # Update in-memory secrets
            self.secrets = merged_secrets
            return True, "Secrets updated successfully"
            
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON format: {e}"
        except Exception as e:
            return False, f"Error saving secrets: {e}"
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value by key"""
        return self.secrets.get(key, default)

    def has_email_configured(self) -> bool:
        """Check if email configuration is present"""
        return all([
            self.get_secret("email_smtp_server"),
            self.get_secret("email_smtp_port"),
            self.get_secret("email_username"),
            self.get_secret("email_password")
        ])

    def has_escalation_contact_configured(self) -> bool:
        """Check if escalation contact configuration is present"""
        return self.has_email_configured() or all([
            self.get_secret("twilio_account_sid"),
            self.get_secret("twilio_auth_token"),
            self.get_secret("twilio_phone_number")
        ])