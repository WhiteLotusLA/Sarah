"""
Encryption module for protecting sensitive data
"""

import os
import base64
import secrets
from typing import Union, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import logging

from sarah.config import Config

logger = logging.getLogger(__name__)


class Encryptor:
    """
    Handles encryption and decryption of sensitive data
    
    Features:
    - AES-256 encryption for data at rest
    - Fernet for simple symmetric encryption
    - AESGCM for authenticated encryption
    - Key derivation from passwords
    - Secure random generation
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """Initialize encryptor with master key"""
        if master_key:
            self.master_key = master_key.encode()
        else:
            # Try to get from config or environment
            key = os.environ.get('SARAH_MASTER_KEY') or getattr(Config, 'MASTER_KEY', None)
            if key:
                self.master_key = key.encode()
            else:
                # Generate a new key (should be stored securely)
                self.master_key = Fernet.generate_key()
                logger.warning("Generated new master key - ensure this is stored securely!")
                
        self.fernet = Fernet(self.master_key)
        
    def encrypt(self, data: Union[str, bytes]) -> str:
        """
        Encrypt data using Fernet (simple symmetric encryption)
        
        Args:
            data: Data to encrypt (string or bytes)
            
        Returns:
            Base64 encoded encrypted data
        """
        if isinstance(data, str):
            data = data.encode()
            
        encrypted = self.fernet.encrypt(data)
        return base64.b64encode(encrypted).decode()
        
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data encrypted with Fernet
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            
        Returns:
            Decrypted string
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_data)
            decrypted = self.fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data")
            
    def encrypt_with_password(self, data: Union[str, bytes], password: str) -> Dict[str, str]:
        """
        Encrypt data using a password-derived key
        
        Args:
            data: Data to encrypt
            password: Password to derive key from
            
        Returns:
            Dictionary with encrypted data and salt
        """
        if isinstance(data, str):
            data = data.encode()
            
        # Generate salt
        salt = os.urandom(16)
        
        # Derive key from password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode())
        
        # Encrypt with derived key
        f = Fernet(base64.urlsafe_b64encode(key))
        encrypted = f.encrypt(data)
        
        return {
            'encrypted': base64.b64encode(encrypted).decode(),
            'salt': base64.b64encode(salt).decode()
        }
        
    def decrypt_with_password(self, encrypted_data: str, salt: str, password: str) -> str:
        """
        Decrypt data using a password-derived key
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            salt: Base64 encoded salt
            password: Password to derive key from
            
        Returns:
            Decrypted string
        """
        # Decode from base64
        encrypted_bytes = base64.b64decode(encrypted_data)
        salt_bytes = base64.b64decode(salt)
        
        # Derive key from password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt_bytes,
            iterations=100000,
        )
        key = kdf.derive(password.encode())
        
        # Decrypt with derived key
        f = Fernet(base64.urlsafe_b64encode(key))
        decrypted = f.decrypt(encrypted_bytes)
        
        return decrypted.decode()
        
    def encrypt_aes_gcm(self, data: Union[str, bytes], 
                       associated_data: Optional[bytes] = None) -> Dict[str, str]:
        """
        Encrypt using AES-GCM for authenticated encryption
        
        Args:
            data: Data to encrypt
            associated_data: Additional data to authenticate but not encrypt
            
        Returns:
            Dictionary with encrypted data, nonce, and tag
        """
        if isinstance(data, str):
            data = data.encode()
            
        # Generate a random 96-bit nonce
        nonce = os.urandom(12)
        
        # Create AESGCM instance with 256-bit key
        key = self.master_key[:32]  # Use first 32 bytes for AES-256
        aesgcm = AESGCM(key)
        
        # Encrypt
        ciphertext = aesgcm.encrypt(nonce, data, associated_data)
        
        return {
            'ciphertext': base64.b64encode(ciphertext).decode(),
            'nonce': base64.b64encode(nonce).decode()
        }
        
    def decrypt_aes_gcm(self, ciphertext: str, nonce: str, 
                       associated_data: Optional[bytes] = None) -> str:
        """
        Decrypt AES-GCM encrypted data
        
        Args:
            ciphertext: Base64 encoded ciphertext
            nonce: Base64 encoded nonce
            associated_data: Additional authenticated data
            
        Returns:
            Decrypted string
        """
        # Decode from base64
        ciphertext_bytes = base64.b64decode(ciphertext)
        nonce_bytes = base64.b64decode(nonce)
        
        # Create AESGCM instance
        key = self.master_key[:32]
        aesgcm = AESGCM(key)
        
        # Decrypt
        plaintext = aesgcm.decrypt(nonce_bytes, ciphertext_bytes, associated_data)
        
        return plaintext.decode()
        
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(length)
        
    def hash_data(self, data: Union[str, bytes]) -> str:
        """
        Create a SHA-256 hash of data
        
        Args:
            data: Data to hash
            
        Returns:
            Hex-encoded hash
        """
        if isinstance(data, str):
            data = data.encode()
            
        digest = hashes.Hash(hashes.SHA256())
        digest.update(data)
        return digest.finalize().hex()
        
    def encrypt_field(self, field_value: Any) -> str:
        """
        Encrypt a database field value
        
        Args:
            field_value: Value to encrypt (will be JSON serialized)
            
        Returns:
            Encrypted string suitable for database storage
        """
        import json
        json_data = json.dumps(field_value)
        return self.encrypt(json_data)
        
    def decrypt_field(self, encrypted_value: str) -> Any:
        """
        Decrypt a database field value
        
        Args:
            encrypted_value: Encrypted field value
            
        Returns:
            Original value
        """
        import json
        decrypted = self.decrypt(encrypted_value)
        return json.loads(decrypted)


# Global encryptor instance
_encryptor: Optional[Encryptor] = None


def get_encryptor() -> Encryptor:
    """Get the global encryptor instance"""
    global _encryptor
    if _encryptor is None:
        _encryptor = Encryptor()
    return _encryptor


def encrypt(data: Union[str, bytes]) -> str:
    """Convenience function to encrypt data"""
    return get_encryptor().encrypt(data)


def decrypt(encrypted_data: str) -> str:
    """Convenience function to decrypt data"""
    return get_encryptor().decrypt(encrypted_data)


# Import Dict for type hints
from typing import Dict, Any