import json
import sys
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
import time
import hashlib
import random
import base64
import secrets

CONFIG_FILE = Path("config.json")

class SiteConfig(BaseModel):
    # Site Settings
    show_routes_in_nav: bool = True
    theme: str = "retro-console"
    show_privacy_policy: bool = True
    show_impressum: bool = True
    show_attribution: bool = True
    
    
    # Site Meta
    site_name: str = "Portfolio"
    site_description: str = "A personal portfolio built with FastAPI and SQLite."
    author_name: str = "System Administrator"
    copyright_year: int = 2024
    
    # URLs
    social_links: list = [
        {"name": "GITHUB", "url": "https://github.com/4-en"},
    ]
    
    # Legal / Impressum
    legal_name: str = "Max Mustermann"
    legal_address: str = "Musterstraße 1, 12345 Musterstadt, Germany"
    legal_email: str = "contact@domain.com"
    legal_phone: str = "+49 123 456789"
    
    # Admin Auth
    admin_user: str = "changeadmin"  # Default to be changed
    admin_pass: str = "changepass"  # Default to be changed
    admin_salt: str = "somesalt"  # Used for hashing the password
    
    @staticmethod
    def default_path():
        return CONFIG_FILE
    
    @staticmethod
    def create_default():
        """Creates a default config with random salt and current year."""
        config = SiteConfig()
        config.copyright_year = time.localtime().tm_year
        config.admin_salt = secrets.token_hex(16)  # Generate a random salt
        return config
    
    @staticmethod
    def load_from_file(filepath: Path = CONFIG_FILE):
        """Loads config from a JSON file."""
        if not filepath.exists():
            return None
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return SiteConfig(**data)
        
    def save_to_file(self, filepath: Path = CONFIG_FILE):
        """Saves the config to a JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=4))
    
def uncrawl(s:str) -> str:
    """Simple obfuscation to hide email and phone from basic crawlers."""
    s = s.replace("@", " ]at[ ").replace(".", " ]dot[ ")
    s = s.replace(",", " ]comma[ ")
    
    s = s.replace("+49", " ]DE[ ").replace("+1", " ]US[ ")
    s = s.replace("+44", " ]UK[ ").replace("+33", " ]FR[ ")
    
    s = reversed(s)
    
    # to base64
    s = "".join(s)
    s = base64.b64encode(s.encode()).decode()
    return s

def load_config() -> SiteConfig:
    """Loads config from file or creates default if missing."""
    if not CONFIG_FILE.exists():
        print(f"[!] Config file not found. Creating default: {CONFIG_FILE}")
        default_config = SiteConfig.create_default()
        
        default_config.save_to_file()
        print(f"[!] Please edit {CONFIG_FILE} and restart the server.")
        sys.exit(0) # Exit so user is forced to edit it

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            config = SiteConfig(**data)
        
        # check if all keys are present, if not fill in defaults
        key_was_missing = False
        for field in SiteConfig.model_fields:
            if field not in data:
                print(f"[!] Key '{field}' was missing in config. Added default value.")
                key_was_missing = True
                
        if key_was_missing:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(config.model_dump_json(indent=4))
            print(f"[!] Updated {CONFIG_FILE} with missing keys. Please review and restart if needed.")
            sys.exit(0) # Exit so user can review changes
        
        # Security Check
        
        if config.admin_user == "changeadmin":
            print("\n[SECURITY ALERT] You are using the default username 'changeadmin'.")
            print(f"Please change 'admin_user' in {CONFIG_FILE} immediately.\n")
            sys.exit(1) # Refuse to start
        
        if config.admin_pass == "changepass":
            print("\n[SECURITY ALERT] You are using the default password 'changepass'.")
            print(f"Please change 'admin_pass' in {CONFIG_FILE} immediately.\n")
            sys.exit(1) # Refuse to start
            
            
        # check if password is hashed (prefix: sha256$) if not, hash it with the salt
        if not config.admin_pass.startswith("sha256$"):
            sha_input = config.admin_pass + config.admin_salt
            hashed_pass = hashlib.sha256(sha_input.encode()).hexdigest()
            config.admin_pass = f"sha256${hashed_pass}"
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(config.model_dump_json(indent=4))
                
        config.legal_name = uncrawl(config.legal_name)
        config.legal_address = uncrawl(config.legal_address)
        config.legal_email = uncrawl(config.legal_email)
        config.legal_phone = uncrawl(config.legal_phone)
            
        return config
            
    except json.JSONDecodeError:
        print(f"[ERROR] Could not parse {CONFIG_FILE}. Please check syntax.")
        sys.exit(1)

