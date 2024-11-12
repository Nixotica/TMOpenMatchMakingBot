import logging
import threading
from flask import Flask, jsonify


def listen_for_health_checks() -> None:
    logging.info("Initializing Flask app...")
    app = Flask(__name__)

    @app.route("/health", methods=["GET"])
    def health_check():
        logging.info("Health check endpoint hit")
        return jsonify(status="healthy"), 200

    # Print all routes for debugging
    for rule in app.url_map.iter_rules():
        logging.info(f"Registered route: {rule}")

    logging.info("Starting Flask app...")
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)


def start_health_check_in_thread() -> None:
    logging.info("Starting health check in a separate thread...")
    thread = threading.Thread(target=listen_for_health_checks, daemon=True)
    thread.start()
