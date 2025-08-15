from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import pandas as pd
import PyPDF2
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from io import BytesIO
import razorpay
from functools import wraps
import uuid
import time

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Razorpay configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Subscription plans (in paise for Razorpay)
PLANS = {
    '1m1d': {'name': '1 Month (1 Device)', 'price': 19900, 'duration': 30, 'devices': 1},
    '1m2d': {'name': '1 Month (2 Devices)', 'price': 24900, 'duration': 30, 'devices': 2},
    '3m1d': {'name': '3 Months (1 Device)', 'price': 49900, 'duration': 90, 'devices': 1},
    '3m2d': {'name': '3 Months (2 Devices)', 'price': 54900, 'duration': 90, 'devices': 2},
    '1y5d': {'name': '1 Year (5 Devices)', 'price': 200000, 'duration': 365, 'devices': 5}
}

# Mock database (in production use a real database)
users_db = {}
subscriptions_db = {}
user_tasks = {}

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Home route
@app.route('/')
def home():
    user = session.get('user')
    is_subscribed = False
    sub_expiry_date = None
    
    if user and user in subscriptions_db:
        sub = subscriptions_db[user]
        if sub['expiry_date'] > datetime.now():
            is_subscribed = True
            sub_expiry_date = sub['expiry_date'].strftime('%d %b %Y')
    
    return render_template('index.html', user=user, is_subscribed=is_subscribed, sub_expiry_date=sub_expiry_date)

# Highlight route
@app.route('/highlight', methods=['POST'])
@login_required
def highlight_route():
    user = session['user']
    
    # Check subscription or free limit
    if user not in subscriptions_db or subscriptions_db[user]['expiry_date'] <= datetime.now():
        if user not in user_tasks:
            user_tasks[user] = {'count': 0, 'last_reset': datetime.now()}
        
        # Reset counter if new month
        if user_tasks[user]['last_reset'].month != datetime.now().month:
            user_tasks[user] = {'count': 0, 'last_reset': datetime.now()}
        
        if user_tasks[user]['count'] >= 2:
            flash('Free limit exceeded (2 tasks/month). Please subscribe to continue.', 'error')
            return redirect(url_for('plans'))
        
        user_tasks[user]['count'] += 1
    
    # Get uploaded files
    pdf_file = request.files['pdf_file']
    excel_file = request.files['excel_file']
    highlight_type = request.form['highlight_type']
    
    # Save files temporarily
    pdf_filename = secure_filename(f"{uuid.uuid4()}.pdf")
    excel_filename = secure_filename(f"{uuid.uuid4()}.xlsx")
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
    excel_path = os.path.join(app.config['UPLOAD_FOLDER'], excel_filename)
    pdf_file.save(pdf_path)
    excel_file.save(excel_path)
    
    try:
        # Process files
        if highlight_type == 'uan':
            highlighted_pdf, missing_data = highlight_uan_numbers(pdf_path, excel_path)
        else:
            highlighted_pdf, missing_data = highlight_esic_numbers(pdf_path, excel_path)
        
        # Prepare response
        timestamp = int(time.time())
        highlighted_filename = f"highlighted_{timestamp}.pdf"
        missing_filename = f"missing_{timestamp}.xlsx"
        
        return send_file(
            highlighted_pdf,
            as_attachment=True,
            download_name=highlighted_filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f'Error processing files: {str(e)}', 'error')
        return redirect(url_for('home'))
    
    finally:
        # Clean up
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(excel_path):
            os.remove(excel_path)

# Subscription plans
@app.route('/plans')
@login_required
def plans():
    return render_template('plans.html', plans=PLANS, key_id=RAZORPAY_KEY_ID, user=session['user'])

# Create payment order
@app.route('/create-order', methods=['POST'])
@login_required
def create_order():
    plan_id = request.form['plan_id']
    if plan_id not in PLANS:
        return {'error': 'Invalid plan'}, 400
    
    plan = PLANS[plan_id]
    order = client.order.create({
        'amount': plan['price'],
        'currency': 'INR',
        'receipt': f"sub_{session['user']}_{datetime.now().strftime('%Y%m%d')}",
        'notes': {
            'plan': plan_id,
            'user': session['user']
        }
    })
    
    return {'order_id': order['id']}

# Payment success callback
@app.route('/payment-success', methods=['POST'])
@login_required
def payment_success():
    payment_id = request.form['razorpay_payment_id']
    order_id = request.form['razorpay_order_id']
    signature = request.form['razorpay_signature']
    
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })
        
        order = client.order.fetch(order_id)
        plan_id = order['notes']['plan']
        user = order['notes']['user']
        
        # Update subscription
        expiry_date = datetime.now() + timedelta(days=PLANS[plan_id]['duration'])
        subscriptions_db[user] = {
            'plan_id': plan_id,
            'plan_name': PLANS[plan_id]['name'],
            'start_date': datetime.now(),
            'expiry_date': expiry_date,
            'devices': PLANS[plan_id]['devices']
        }
        
        return redirect(url_for('success'))
    
    except Exception as e:
        flash('Payment verification failed. Please contact support.', 'error')
        return redirect(url_for('plans'))

# Success page
@app.route('/success')
@login_required
def success():
    return render_template('success.html')

# Login, logout, signup routes (similar implementations)
# ...

if __name__ == '__main__':
    app.run(debug=True)
