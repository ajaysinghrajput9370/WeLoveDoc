import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-key")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    RESULT_FOLDER = os.getenv("RESULT_FOLDER", "results")

    # Free tasks per month
    FREE_TASKS_PER_MONTH = int(os.getenv("FREE_TASKS_PER_MONTH", 2))

    # Razorpay
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

    # Amounts in paise
    PLAN_MONTHLY_AMOUNT = int(os.getenv("PLAN_MONTHLY_AMOUNT", 4900))
    PLAN_SIX_MONTH_AMOUNT = int(os.getenv("PLAN_SIX_MONTH_AMOUNT", 24900))
    PLAN_YEARLY_AMOUNT = int(os.getenv("PLAN_YEARLY_AMOUNT", 49900))

    # Durations (days)
    PLAN_MONTHLY_DAYS = int(os.getenv("PLAN_MONTHLY_DAYS", 30))
    PLAN_SIX_MONTH_DAYS = int(os.getenv("PLAN_SIX_MONTH_DAYS", 180))
    PLAN_YEARLY_DAYS = int(os.getenv("PLAN_YEARLY_DAYS", 365))
