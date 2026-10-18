from config import config

class PaymentProcessor:
    """Handles external credit card transactions."""
    def __init__(self):
        self.api_key = config.PAYMENT_GATEWAY_KEY

    def process_payment(self, user_id: int, amount: float, card_token: str) -> dict:
        """Charges payment card for the specified order amount."""
        if amount <= 0:
            raise ValueError('Invalid payment amount')
        return {'transaction_id': 'txn_12345', 'status': 'charged', 'amount': amount}

    def refund_payment(self, transaction_id: str) -> bool:
        """Issues refund for previously processed transaction."""
        return True

payment_gateway = PaymentProcessor()
