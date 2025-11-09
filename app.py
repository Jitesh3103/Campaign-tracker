import os
import traceback
from flask import Flask, render_template, request, redirect, url_for, jsonify

# Wrap startup so we log any import-time failures instead of letting the process exit
try:
    app = Flask(__name__)

    # -----------------------------
    # MONGO URI handling (secure)
    # -----------------------------
    MONGO_URI = os.environ.get("MONGO_URI")

    # For local development only: allow fallback when FLASK_ENV=development
    if not MONGO_URI and os.environ.get("FLASK_ENV", "").lower() == "development":
        MONGO_URI = "mongodb://localhost:27017/campaign_db"

    # Log masked presence so you can verify in Vercel build/runtime logs
    if MONGO_URI:
        masked = (MONGO_URI[:20] + "...") if len(MONGO_URI) > 20 else MONGO_URI
        print(f"🔒 MONGO_URI provided (masked): {masked}")
        app.config["MONGO_URI"] = MONGO_URI
    else:
        print("⚠️ MONGO_URI not provided. DB operations will fail until you add MONGO_URI env var in Vercel.")

    # -----------------------------
    # Lazy initialize PyMongo (only when MONGO_URI exists)
    # -----------------------------
    mongo = None

    def get_mongo():
        """Lazily initialize and return the PyMongo instance, or None on failure or if no URI."""
        global mongo
        # Don't even try if we don't have a config
        if not app.config.get("MONGO_URI"):
            # Clear explicit message to logs
            print("⚠️ get_mongo called but no MONGO_URI in app.config; skipping PyMongo init.")
            return None

        if mongo is None:
            try:
                # import inside function to delay potential import-time issues
                from flask_pymongo import PyMongo
                mongo = PyMongo(app)
                # After init, ensure .db is available
                if not getattr(mongo, "db", None):
                    print("⚠️ PyMongo initialized but no .db attribute present. Check MONGO_URI and requirements.")
                    return None
                print("✅ PyMongo initialized.")
            except Exception as e:
                # Log the error and keep mongo as None (so the app can still start)
                print("⚠️ Failed to initialize PyMongo:", e)
                traceback.print_exc()
                mongo = None
        return mongo

    def get_collection():
        """Return the campaigns collection or raise a clear runtime error."""
        m = get_mongo()
        if not m:
            # Raise a clear runtime error that your route handlers will catch and report
            raise RuntimeError(
                "MongoDB is not configured or failed to initialize. "
                "Set the MONGO_URI environment variable in Vercel (Project → Settings → Environment Variables)."
            )
        # safe to access m.db now
        return m.db.campaigns

    # -----------------------------
    # Routes
    # -----------------------------
    @app.route('/health')
    def health():
        """Simple health check that does not require DB."""
        return jsonify({"status": "ok"}), 200

    @app.route('/')
    def index():
        # if templates are missing, render a simple message instead of crashing
        try:
            return render_template('index.html')
        except Exception as e:
            print("⚠️ Failed to render index.html:", e)
            traceback.print_exc()
            return "<h1>Index template missing or rendering failed</h1>", 200

    @app.route('/campaigns')
    def table():
        try:
            campaigns_collection = get_collection().find()
            return render_template('table.html', campaigns=campaigns_collection)
        except Exception as e:
            print("⚠️ /campaigns error:", e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route('/add', methods=['POST'])
    def add_campaign():
        try:
            name = request.form.get('name')
            client = request.form.get('client')
            start_date = request.form.get('start-date')
            status = request.form.get('status')

            coll = get_collection()
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
            from bson.objectid import ObjectId
            coll = get_collection()
            coll.delete_one({'_id': ObjectId(id)})
            return redirect(url_for('table'))
        except Exception as e:
            print("⚠️ /delete error:", e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route('/update/<id>', methods=['POST'])
    def update_campaign(id):
        try:
            from bson.objectid import ObjectId
            new_status = request.form.get('status')
            coll = get_collection()
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
            status_filter = request.form.get('status_filter', 'All')

            if status_filter == 'All':
                campaigns_collection = get_collection().find()
            else:
                campaigns_collection = get_collection().find({'status': status_filter})

            return render_template('report.html', campaigns=campaigns_collection, current_filter=status_filter)
        except Exception as e:
            print("⚠️ /report error:", e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

except Exception as e:
    # Catch any unexpected startup error and present a simple app that surfaces it.
    print("🔥 Startup error:", e)
    traceback.print_exc()
    app = Flask(__name__)

    @app.route("/")
    def startup_error():
        return jsonify({"startup_error": str(e)}), 500


# DO NOT enable debug mode in production (Vercel uses serverless functions)
if __name__ == '__main__':
    # For local development only (use FLASK_ENV=development to allow localhost fallback)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)
