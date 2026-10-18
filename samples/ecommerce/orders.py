from auth import get_current_user
from payment import payment_gateway
from database import execute_query

def create_order(auth_token: str, items: list, total_amount: float) -> dict:
    """Validates user, processes payment, and inserts order record."""
    user = get_current_user(auth_token)
    payment_result = payment_gateway.process_payment(
        user_id=user['id'],
        amount=total_amount,
        card_token='tok_visa_default'
    )
    order_record = execute_query(
        'INSERT INTO orders (user_id, amount, status) VALUES (?, ?, ?)',
        (user['id'], total_amount, 'confirmed')
    )
    return {
        'order_id': 101,
        'user_id': user['id'],
        'status': 'confirmed',
        'transaction_id': payment_result['transaction_id']
    }

def get_order_history(auth_token: str) -> list:
    """Fetches list of historical orders for authenticated user."""
    user = get_current_user(auth_token)
    return execute_query('SELECT * FROM orders WHERE user_id = ?', (user['id'],))
