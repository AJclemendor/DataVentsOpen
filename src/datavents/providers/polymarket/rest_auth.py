from dotenv import load_dotenv
import os
import sys
import logging
load_dotenv()
try:
    from ..config import Config
except Exception:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config  # type: ignore

from eth_account import Account


logger = logging.getLogger(__name__)


class PolymarketAuth:   

    def __init__(self, config: Config):
        
        if config == Config.NOAUTH:
            logger.debug("Creating a polymarket auth instance with no auth config (CLOB, lvl 0)")
            return
        elif config == Config.PAPER:
            raise NotImplementedError("Polymarket does not currently support paper trading")

        self.config = config
        self.api_key: str = os.getenv("POLYMARKET_API_KEY")
        self.secret_key: str = os.getenv("POLYMARKET_API_SECRET")
        self.api_passphrase: str = os.getenv("POLYMARKET_API_PASSPHRASE")
        self.private_key: str = os.getenv("POLYMARKET_PRIVATE_KEY")
        self.account = self.init_account()
        self.address = self.get_address()
        self.chain_id = self.account.chain_id

        # For now dont worry abt clob, signing, just want to match silly dome kids 
        


        """
        There are 3 lvls, lvl 0 (read only), lvl 1 Pkey Auth, Lvl 2 API + pkeyauth

        """

        

    def init_account(self):
        return Account.from_key(self.private_key)

    def get_address(self):
        return self.account.address

    def get_chain_id(self):
        return self.chain_id

    def sign(self, message_hash):
        return Account._sign_hash(message_hash, self.private_key).signature.hex()
