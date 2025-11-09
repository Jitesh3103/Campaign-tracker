import os
import traceback
from flask import Flask, render_template, request, redirect, url_for, jsonify

# IMPORTANT: set this early so TLS uses certifi's CA bundle
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    print("Using certifi CA bundle at:", certifi.where())
except Exception as e:
    print("Could not load certifi:", e)

try:
    app = Flask(__name__)

    # -------------------------
    # MONGO URI handling
    # -------------------------
    MONGO_URI = os.environ.get("MONGO_URI")
    if not MONGO_URI and os.environ.get("FLASK_ENV", "").lower() == "development":
        MONGO_URI = "mongodb://localhost:27017/campaign_db"

    if MONGO_URI:
        masked = (MONGO_URI[:20] + "...") if len(MONGO_URI) > 20 else MONGO_URI
        print(f"🔒 MONGO_URI provided (masked): {masked}")
        app.config["MONGO_URI"] = MONGO_URI
    else:
        print("⚠️ MONGO_URI not provided in environment.")

    # -------------------------
    # Lazy PyMongo initialization with diagnostics
    # -------------------------
    mongo = None
    mongo_init_error = None
    mongo_init_attempted = False

    def try_init_mongo_once():
        """Attempt to initialize PyMongo once and capture any exception."""
        global mongo, mongo_init_error, mongo_init_attempted
        if mongo_init_attempted:
            return
        mongo_init_attempted = True

        if not app.config.get("MONGO_URI"):
            mongo_init_error = "MONGO_URI not set"
            print("⚠️ try_init_mongo_once: MONGO_URI not set")
            return

        try:
            # ensure certifi is used (again, in case)
            try:
                import certifi
                os.environ.setdefault("SSL_CERT_FILE", certifi.where())
            except Exception:
                pass

            # Lazy import to avoid import-time failures
            from flask_pymongo import PyMongo
            mongo = PyMongo(app)

            # explicit None check — Database objects don't support truth testing
            if getattr(mongo, "db", None) is None:
                mongo_init_error = "PyMongo initialized but .db missing"
                print("⚠️ PyMongo initialized but .db missing")
                mongo = None
            else:
                print("✅ PyMongo initialized.")
        except Exception as e:
            mongo = None
            mongo_init_error = repr(e)
            print("⚠️ Exception during PyMongo init:", mongo_init_error)
            traceback.print_exc()

    def get_mongo():
        try_init_mongo_once()
        return mongo

    def get_collection():
        m = get_mongo()
        if m is None:
            raise RuntimeError("Mongo not initialized: " + (mongo_init_error or "unknown"))
        return m.db.campaigns

    # -------------------------
    # Debug and health endpoints
    # -------------------------
    @app.route('/debug')
    def debug_info():
        """Returns masked diagnostics about MONGO_URI and PyMongo init status."""
        try_init_mongo_once()
        has_mongo_uri = bool(app.config.get("MONGO_URI"))
        masked = None
        if has_mongo_uri:
            uri = app.config["MONGO_URI"]
            masked = (uri[:20] + "...") if len(uri) > 20 else uri
        return jsonify({
            "has_mongo_uri": has_mongo_uri,
            "masked_mongo_uri": masked,
            "mongo_init_ok": mongo is not None,
            "mongo_init_error": mongo_init_error,
            "ssl_cert_file": os.environ.get("SSL_CERT_FILE")
        }), 200

    @app.route('/health')
    def health():
        """Simple health check not requiring DB."""
        return jsonify({"status": "ok"}), 200

    # -------------------------
    # App routes (guarded)
    # -------------------------
    @app.route('/')
    def index():
        try:
            return render_template('index.html')
        except Exception as e:
            print("⚠️ Failed to render index.html:", e)
            traceback.print_exc()
            return "<h1>Index template missing or rendering failed</h1>", 200

    @app.route('/campaigns')
    def table():
        try:
            coll = get_collection()
        except Exception as e:
            print("⚠️ /campaigns: DB not available:", e)
            traceback.print_exc()
            return jsonify({"error": "Database not available: " + str(e)}), 500

        try:
            campaigns_collection = coll.find()
            return render_template('table.html', campaigns=campaigns_collection)
        except Exception as e:
            print("⚠️ /campaigns error while querying:", e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route('/add', methods=['POST'])
    def add_campaign():
        try:
            coll = get_collection()
        except Exception as e:
            print("⚠️ /add: DB not available:", e)
            traceback.print_exc()
            return jsonify({"error": "Database not available: " + str(e)}), 500

        try:
            name = request.form.get('name')
            client = request.form.get('client')
            start_date = request.form.get('start-date')
            status = request.form.get('status')

            coll.insert_one({
                'name': name,
                'client': client,
                'startDate': start_date,
                'status': status
            })
            return redirect(url_for('table'))
        except Exception as e:
            print("⚠️ /add error:", e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route('/delete/<id>', methods=['POST'])
    def delete_campaign(id):
        try:
            coll = get_collection()
        except Exception as e:
            print("⚠️ /delete: DB not available:", e)
            traceback.print_exc()
            return jsonify({"error": "Database not available: " + str(e)}), 500

        try:
            from bson.objectid import ObjectId
            coll.delete_one({'_id': ObjectId(id)})
            return redirect(url_for('table'))
        except Exception as e:
            print("⚠️ /delete error:", e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route('/update/<id>', methods=['POST'])
    def update_campaign(id):
        try:
            coll = get_collection()
        except Exception as e:
            print("⚠️ /update: DB not available:", e)
            traceback.print_exc()
            return jsonify({"error": "Database not available: " + str(e)}), 500

        try:
            from bson.objectid import ObjectId
            new_status = request.form.get('status')
            coll.update_one(
                {'_id': ObjectId(id)},
                {'$set': {'status': new_status}}
            )
            return redirect(url_for('table'))
        except Exception as e:
            print("⚠️ /update error:", e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route('/report', methods=['GET', 'POST'])
    def report():
        try:
            coll = get_collection()
        except Exception as e:
            print("⚠️ /report: DB not available:", e)
            traceback.print_exc()
            return jsonify({"error": "Database not available: " + str(e)}), 500

        try:
            status_filter = request.form.get('status_filter', 'All')

            if status_filter == 'All':
                campaigns_collection = coll.find()
            else:
                campaigns_collection = coll.find({'status': status_filter})

            return render_template('report.html', campaigns=campaigns_collection, current_filter=status_filter)
        except Exception as e:
            print("⚠️ /report error:", e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

except Exception as e:
    # Catch unexpected startup error and show it via a simple app
    print("🔥 Startup error:", e)
    traceback.print_exc()
    app = Flask(__name__)
    @app.route("/")
    def startup_error():
        return jsonify({"startup_error": str(e)}), 500

# Local dev run
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)

