import os
import traceback
from flask import Flask, render_template, request, redirect, url_for, jsonify

# -------------------------
# Main app wrapper
# -------------------------
try:
    app = Flask(__name__)

    # -------------------------
    # MONGO URI handling
    # -------------------------
    # In production (Vercel) set MONGO_URI in Project -> Settings -> Environment Variables
    MONGO_URI = os.environ.get("MONGO_URI")

    # Allow local dev fallback only when FLASK_ENV=development
    if not MONGO_URI and os.environ.get("FLASK_ENV", "").lower() == "development":
        MONGO_URI = "mongodb://localhost:27017/campaign_db"

    # Log masked presence so you can verify in Vercel build/runtime logs
    if MONGO_URI:
        masked = (MONGO_URI[:20] + "...") if len(MONGO_URI) > 20 else MONGO_URI
        print(f"🔒 MONGO_URI provided (masked): {masked}")
        app.config["MONGO_URI"] = MONGO_URI
    else:
        print("⚠️ MONGO_URI not provided. DB operations will fail until you add MONGO_URI env var in Vercel.")

    # -------------------------
    # Lazy PyMongo initialization
    # -------------------------
    mongo = None

    def get_mongo():
        """Lazily initialize and return the PyMongo instance, or None on failure or if not configured."""
        global mongo
        # if no config, skip initialization
        if not app.config.get("MONGO_URI"):
            print("⚠️ get_mongo called but no MONGO_URI in app.config; skipping PyMongo init.")
            return None

        if mongo is None:
            try:
                from flask_pymongo import PyMongo
                mongo = PyMongo(app)
                # ensure .db exists after initialization
                if not getattr(mongo, "db", None):
                    print("⚠️ PyMongo initialized but no .db attribute present. Check MONGO_URI and requirements.")
                    return None
                print("✅ PyMongo initialized.")
            except Exception as e:
                print("⚠️ Failed to initialize PyMongo:", e)
                traceback.print_exc()
                mongo = None
        return mongo

    def get_collection():
        """Return the campaigns collection or raise a runtime error explaining the issue."""
        m = get_mongo()
        if not m:
            raise RuntimeError(
                "MongoDB is not configured or failed to initialize. "
                "Set the MONGO_URI environment variable in Vercel (Project → Settings → Environment Variables)."
            )
        return m.db.campaigns

    # -------------------------
    # Routes
    # -------------------------
    @app.route('/health')
    def health():
        """A simple health check not requiring DB."""
        return jsonify({"status": "ok"}), 200

    @app.route('/')
    def index():
        """Render index.html or return a friendly message if template fails."""
        try:
            return render_template('index.html')
        except Exception as e:
            print("⚠️ Failed to render index.html:", e)
            traceback.print_exc()
            return "<h1>Index template missing or rendering failed</h1>", 200

    @app.route('/campaigns')
    def table():
        """Show campaigns table (DB required)."""
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
        """Add a new campaign to the DB."""
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
        """Delete a campaign by ObjectId."""
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
        """Update a campaign's status by ObjectId."""
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
        """Generate a simple report (filter by status)."""
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
    # Crashed at import-time: present a simple app showing the startup error
    print("🔥 Startup error:", e)
    traceback.print_exc()
    app = Flask(__name__)

    @app.route("/")
    def startup_error():
        return jsonify({"startup_error": str(e)}), 500


# Local dev server only
if __name__ == '__main__':
    # Only enable debug locally; Vercel runs serverless functions.
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)
