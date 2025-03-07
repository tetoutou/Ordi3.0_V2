from functools import wraps
from flask import jsonify
import traceback

def api_error_handler(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_traceback = traceback.format_exc()
            print(f"API Error: {str(e)}")
            print(f"Traceback: {error_traceback}")
            return jsonify({
                'error': str(e),
                'trace': error_traceback,
                'success': False
            }), 500
    return decorated_function
