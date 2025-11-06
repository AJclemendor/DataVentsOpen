try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:  # pragma: no cover
    # Optional dependency; proceed without .env loading if unavailable
    def load_dotenv(*args, **kwargs):  # type: ignore
        return False
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import os
from typing import Any, Dict
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature

import os
import sys
import logging
try:
    from ..config import Config
except Exception:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config  # type: ignore

logger = logging.getLogger(__name__)

class KalshiAuth:
    def __init__(self, config: Config):
        if config == Config.NOAUTH:
            logger.debug("Creating a kalshi auth instance with no auth config")
            return
        env_key_path = "KALSHI_PRIVATE_KEY" if config == Config.LIVE else "KALSHI_PRIVATE_KEY_PAPER"
        key_path = "KALSHI_API_KEY" if config == Config.LIVE else "KALSHI_API_KEY_PAPER"
        self.private_key: rsa.RSAPrivateKey = self._load_private_key_from_file(
            os.getenv(env_key_path)
        )
        self.api_key: str = os.getenv(key_path)

        assert (
            self.api_key is not None
        ), "API key is not set"
        assert (
            self.private_key is not None
        ), "Private key is not set"

    
    def _load_private_key_from_file(self, file_path) -> rsa.RSAPrivateKey:
        # from https://docs.kalshi.com/getting_started/api_keys
        with open(file_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,  # or provide a password if your key is encrypted
                backend=default_backend(),
            )
        return private_key

    def sign_pss_text(self, text: str) -> str:
        message = text.encode("utf-8")
        try:
            signature = self.private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH,
                ),
                hashes.SHA256(),
            )
            return base64.b64encode(signature).decode("utf-8")
        except InvalidSignature as e:
            raise ValueError("RSA sign PSS failed") from e

# Note: orderbook helper lives on the signed KalshiRestAuth client and uses
# its inherited `get(...)` method from BaseKalshiClient to ensure proper
# request signing and header construction.
