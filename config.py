import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    RESULT_FOLDER = os.environ.get("RESULT_FOLDER", "results")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

    # Free plan: tasks per month without login
    FREE_TASKS_PER_MONTH = int(os.environ.get("FREE_TASKS_PER_MONTH", 2))

    # Razorpay keys (set real keys in environment)
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_xxxxxxx")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "xxxxxsecret")

    # Plans
    PLAN_MONTHLY = 49
    PLAN_6MONTH = 249
    PLAN_12MONTH = 449

    # Devices rules
    DEVICES_MONTHLY = 1
    DEVICES_6MONTH = 1
    DEVICES_12MONTH = 2
    EXTRA_DEVICE_PRICE = 50
