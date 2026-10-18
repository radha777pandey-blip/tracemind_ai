from config import config
from auth import login
from orders import create_order, get_order_history

def handle_login_request(request: dict) -> dict:
    """Entrypoint for customer authentication."""
    username = request.get('username', '')
    password = request.get('password', '')
    token = login(username, password)
    return {'status': 'ok', 'token': token}

def handle_checkout_request(request: dict) -> dict:
    """Entrypoint for order placement and checkout."""
    token = request.get('token', '')
    items = request.get('items', [])
    amount = request.get('total_amount', 0.0)
    order = create_order(token, items, amount)
    return {'status': 'success', 'order': order}

if __name__ == '__main__':
    print('Starting Ecommerce Service on port 5000...')
