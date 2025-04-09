import json
import os
from pathlib import Path
import base64
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class CredentialManager:
    """Manages secure storage of credentials."""

    APP_NAME = "ABS-Client"
    CONFIG_FILE = "config.json"
    CREDS_FILE = "credentials.enc"

    def __init__(self, data_dir=None):
        if data_dir:
            self.data_dir = data_dir
        else:
            cache_home = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
            self.data_dir = Path(cache_home)/"AudiobookShelfClient"

        self.config_dir = self.data_dir/"config"
        self.config_path = self.config_dir/self.CONFIG_FILE
        self.creds_path = self.config_dir/self.CREDS_FILE

        os.makedirs(self.config_dir, exist_ok=True)
        self.config = self._load_config()
        self.keyring_available = self._check_keyring_available()

        if self.keyring_available and self.creds_path.exists():
            self._migrate_to_keyring()

    def _check_keyring_available(self):
        """Check if keyring is available and working"""
        try:
            import keyring
            test_service = f"{self.APP_NAME}-test"
            test_user = "test_user"
            test_pass = "test_pass"

            keyring.set_password(test_service, test_user, test_pass)
            retrieved = keyring.get_password(test_service, test_user)
            keyring.delete_password(test_service, test_user)

            return retrieved == test_pass
        except Exception:
            return False

    def _generate_key(self, salt, device_id):
        """Generate encryption key from device specific info"""
        if not device_id:
            device_id = self._get_device_id()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            )

        key = base64.urlsafe_b64encode(kdf.derive(device_id.encode()))
        return key

    def _get_device_id(self):
        """Generate a relatively stable device ID"""
        try:
            if os.name == 'nt': # Windows
                import winreg
                reg_path = r'SOFTWARE\Microsoft\Cryptography'
                reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                mac_guid = winreg.QueryValueEx(reg_key, 'MachineGuid')[0]
                winreg.CloseKey(reg_key)
                return mac_guid
            elif os.name == 'posix':
                if os.path.exists('/etc/machine-id'):
                    with open('/etc/machine-id', 'r') as f:
                        return f.read().strip()

                if os.path.exists('/usr/sbin/system_profiler'):
                    import subprocess
                    result = subprocess.run(
                        ['/usr/sbin/system_profiler', 'SPHardwareDateType'],
                        capture_output=True, text=True
                    )
                    for line in result.stdout.splitlines():
                        if 'Hardware UUID' in line:
                            return line.split(':')[1].strip()
        except Exception:
            pass

        username = os.environ.get('USER') or os.environ.get('USERNAME') or 'user'
        home = os.path.expanduser('~')
        return f"{username}-{hashlib.sha256(home.encode()).hexdigest()[:8]}"
        

    def _load_config(self):
        """Load config from file or create default."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                return {"last_server": "", "remember_me": False, "username": "", "salt": ""}
        else:
            salt = base64.urlsafe_b64encode(os.urandom(16)).decode()
            return {"last_server": "", "remember_me": False, "username": "", "salt": salt}

    def _save_config(self):
        """Save config to file"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f)

    def _encrypt_password(self, password):
        """Encrypt password using Fernet symmetric encryption."""
        salt = self.config.get("salt", "")
        if not salt:
            salt = base64.urlsafe_b64encode(os.urandom(16)).decode()
            self.config["salt"] = salt
            self._save_config()
        else:
            salt = salt.encode() if isinstance(salt, str) else salt

        key = self._generate_key(salt.encode() if isinstance(salt, str) else salt, self._get_device_id())
        cipher = Fernet(key)
        encrypted = cipher.encrypt(password.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def _decrypt_password(self, encrypted_password):
        """Decrypt password using Fernet symmetric encryption"""
        try:
            salt = self.config.get("salt", "").encode()
            key = self._generate_key(salt, self._get_device_id())
            cipher = Fernet(key)
            decrypted = cipher.decrypt(base64.urlsafe_b64decode(encrypted_password))
            return decrypted.decode()
        except Exception:
            return ""

    def _save_fallback_credentials(self, server_url, username, password):
        """Save credentials to an encrypted file as fallback"""
        if not server_url or not username or not password:
            return
        encrypted_password = self._encrypt_password(password)
        creds = {}
        if self.creds_path.exists():
            try:
                with open(self.creds_path, 'r') as f:
                    creds = json.load(f)
            except Exception:
                creds = {}

        server_key = self._hash_server_url(server_url)
        if server_key not in creds:
            creds[server_key] = {}

        creds[server_key][username] = encrypted_password

        with open(self.creds_path, 'w') as f:
            json.dump(creds, f)

    def _get_fallback_credentials(self, server_url, username):
        """Get credentials from encrypted fallback file."""
        if not self.creds_path.exists() or not server_url or not username:
            return None

        try:
            with open(self.creds_path, 'r') as f:
                creds = json.load(f)

            server_key = self._hash_server_url(server_url)
            if server_key in creds and username in creds[server_key]:
                encrypted_password = creds[server_key][username]
                return self._decrypt_password(encrypted_password)
        except Exception:
            pass
        return None

    def _migrate_to_keyring(self):
        """Migrate credentials from fallback to keyring if possible."""
        if not self.keyring_available or not self.creds_path.exists():
            return

        try:
            import keyring
            with open(self.creds_path, 'r') as f:
                creds = json.load(f)

            for server_hash, users in creds.items():
                # Need to map from hash to url
                # Imperfect, since hash is one way...
                server_url = self.config.get("last_server", "")
                if server_hash == self._hash_server_url(server_url):
                    for username, encrypted_password in users.items():
                        password = self._decrypt_password(encrypted_password)
                        if password:
                            service_name = f"{self.APP_NAME}-{server_hash}"
                            keyring.set_password(service_name, username, password)
        except Exception:
            pass

    def save_credentials(self, server_url, username, password, remember=True):
        """Save user credentials securely"""
        self.config["last_server"] = server_url
        self.config["remember_me"] = remember
        self.config["username"] = username if remember else ""
        self._save_config()

        if remember and password:
            if self.keyring_available:
                try:
                    import keyring
                    service_name = f"{self.APP_NAME}-{self._hash_server_url(server_url)}"
                    keyring.set_password(service_name, username, password)
                except Exception:
                    self._save_fallback_credentials(server_url, username, password)
            else:
                self._save_fallback_credentials(server_url, username, password)

    def get_credentials(self):
        """Retrieve saved credentials"""
        server_url = self.config.get("last_server", "")
        username = self.config.get("username", "")
        remember_me = self.config.get("remember_me", False)

        password = ""
        if remember_me and server_url and username:
            if self.keyring_available:
                try:
                    import keyring
                    service_name = f"{self.APP_NAME}-{self._hash_server_url(server_url)}"
                    password = keyring.get_password(service_name, username)
                except Exception:
                    password = ""

            if not password:
                fallback_password = self._get_fallback_credentials(server_url, username)
                if fallback_password:
                    password = fallback_password
                    if self.keyring_available:
                        self.save_credentials(server_url, username, password, remember_me)

        return {
            "server_url": server_url,
            "username": username,
            "password": password,
            "remember_me": remember_me
            }

    def clear_credentials(self):
        """Clear saved credentials"""
        server_url = self.config.get("last_server", "")
        username = self.config.get("username", "")

        if self.keyring_available and server_url and username:
            try:
                import keyring
                service_name = f"{self.APP_NAME}-{self._hash_server_url(server_url)}"
                keyring.delete_password(service_name, username)
            except Exception:
                pass

        if self.creds_path.exists():
            try:
                with open(self.creds_path, 'r') as f:
                    creds = json.load(f)

                server_key = self._hash_server_url(server_url)
                if server_key in creds and username in creds[server_key]:
                    del creds[server_key][username]

                    if not creds[server_key]:
                        del creds[server_key]

                    with open(self.creds_path, 'w') as f:
                        json.dump(creds, f)
            except Exception:
                pass

        self.config["remember_me"] = False
        self.config["username"] = ""
        self._save_config()

    def _hash_server_url(self, server_url):
        """Create a hash of the server url to use as part of the service name"""
        return base64.urlsafe_b64encode(
            hashlib.sha256(server_url.encode()).digest()
        ).decode()[:16]

        
