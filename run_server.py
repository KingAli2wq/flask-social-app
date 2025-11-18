"""
Helper to run the social server. Prefers waitress when available; falls back to Flask's
development server if waitress isn't installed.

Usage:
  python run_server.py

Environment variables:
  SOCIAL_SERVER_PORT - port to bind (defaults to 5000)
  SOCIAL_SERVER_TOKEN - optional token to require for api access
"""
import os

try:
    # Import the Flask app from server.py
    from server import app
except Exception as e:
    print("Failed to import server.app:", e)
    raise

if __name__ == "__main__":
    port = int(os.environ.get("SOCIAL_SERVER_PORT", "5000"))
    try:
        # Try to use waitress for production-like serving
        from waitress import serve

        print(f"Starting server with waitress on 0.0.0.0:{port}")
        serve(app, host="0.0.0.0", port=port)
    except Exception as e:
        print("waitress not available or failed to start (", e, "), falling back to Flask dev server")
        # Development fallback
        app.run(host="0.0.0.0", port=port, threaded=True)
