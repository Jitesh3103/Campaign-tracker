from flask import Flask, render_template, request, redirect, url_for
from flask_pymongo import PyMongo
from bson.objectid import ObjectId

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://localhost:27017/campaign_db"
mongo = PyMongo(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/campaigns')
def table():
    campaigns_collection = mongo.db.campaigns.find()
    return render_template('table.html', campaigns=campaigns_collection)

@app.route('/add', methods=['POST'])
def add_campaign():
    name = request.form.get('name')
    client = request.form.get('client')
    start_date = request.form.get('start-date')
    status = request.form.get('status')
    
    mongo.db.campaigns.insert_one({
        'name': name,
        'client': client,
        'startDate': start_date,
        'status': status
    })
    return redirect(url_for('table'))

@app.route('/delete/<id>', methods=['POST'])
def delete_campaign(id):
    mongo.db.campaigns.delete_one({'_id': ObjectId(id)})
    return redirect(url_for('table'))

@app.route('/update/<id>', methods=['POST'])
def update_campaign(id):
    new_status = request.form.get('status')
    
    mongo.db.campaigns.update_one(
        {'_id': ObjectId(id)},
        {'$set': {'status': new_status}}
    )
    return redirect(url_for('table'))

@app.route('/report', methods=['GET', 'POST'])
def report():
    status_filter = request.form.get('status_filter', 'All')

    if status_filter == 'All':
        campaigns_collection = mongo.db.campaigns.find()
    else:
        campaigns_collection = mongo.db.campaigns.find({'status': status_filter})
    
    return render_template('report.html', campaigns=campaigns_collection, current_filter=status_filter)

if __name__ == '__main__':
    app.run(debug=True)