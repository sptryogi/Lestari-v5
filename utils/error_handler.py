import logging
from functools import wraps
from flask import jsonify

logger = logging.getLogger(__name__)

def handle_chatbot_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            return jsonify({"error": "Terjadi kesalahan internal. Silakan coba lagi."}), 500
    return wrapper