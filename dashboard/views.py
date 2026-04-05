import json
import numpy as np
import os
import yfinance as yf

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required

from .models import Watchlist, Portfolio

try:
    from tensorflow.keras.models import load_model
except ImportError:
    load_model = None


# ================= LOAD MODEL =================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

lstm_path = os.path.join(BASE_DIR, 'dashboard', 'model_ml', 'lstm_model.h5')
gru_path = os.path.join(BASE_DIR, 'dashboard', 'model_ml', 'gru_model.h5')

print("LSTM exists:", os.path.exists(lstm_path))
print("GRU exists:", os.path.exists(gru_path))

lstm_model = None
gru_model = None

try:
    if load_model:
        if os.path.exists(lstm_path):
            lstm_model = load_model(lstm_path)
        if os.path.exists(gru_path):
            gru_model = load_model(gru_path)
except Exception as e:
    print("Model Load Error:", e)


# ================= LOGIN =================
def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect("dashboard")
        else:
            return render(request, "login.html", {"error": "Invalid username or password"})

    return render(request, "login.html")


# ================= SIGNUP =================
def signup_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            return render(request, "signup.html", {"error": "Passwords do not match"})

        if User.objects.filter(username=username).exists():
            return render(request, "signup.html", {"error": "Username already exists"})

        user = User.objects.create_user(username=username, email=email, password=password1)

        send_mail(
            "Welcome to StockAI 🚀",
            "Your account has been created successfully!",
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=True,
        )

        return render(request, "signup.html", {"success": "Account created successfully! Please login."})

    return render(request, "signup.html")


# ================= DASHBOARD =================
@login_required
def dashboard(request):
    stock_symbol = "AAPL"

    # ===== LIVE STOCK PRICE =====
    try:
        stock_data = yf.download(stock_symbol, period="1mo", progress=False, auto_adjust=True)

        if stock_data.empty:
            raise ValueError("No stock data found")

        close_data = stock_data["Close"]

        # Handle case where Close is Series or DataFrame
        if hasattr(close_data, "iloc"):
            last_close = close_data.iloc[-1]

            # If still Series, take first value
            if hasattr(last_close, "iloc"):
                last_close = last_close.iloc[0]

            price = float(last_close)
        else:
            price = 145.93

    except Exception as e:
        print("Stock Price Error:", e)
        price = 145.93  # fallback

    # ===== USER DATA =====
    watchlist = Watchlist.objects.filter(user=request.user)
    portfolio = Portfolio.objects.filter(user=request.user)

    # ===== DEFAULT VALUES =====
    lstm_prediction = 0
    gru_prediction = 0
    chart_data = []

    # ===== FORM SUBMIT =====
    if request.method == "POST":
        user_input = request.POST.get("data")
        stock = request.POST.get("stock")

        # ===== Add Stock to Watchlist =====
        if stock:
            stock = stock.strip().upper()
            if stock != "":
                Watchlist.objects.create(user=request.user, stock_name=stock)

        # ===== Predict =====
        if user_input:
            try:
                user_input = float(user_input)

                if lstm_model is not None and gru_model is not None:
                    input_data = np.array([[user_input]], dtype=np.float32)
                    input_data = np.reshape(input_data, (1, 1, 1))

                    lstm_prediction = round(float(lstm_model.predict(input_data, verbose=0)[0][0]), 2)
                    gru_prediction = round(float(gru_model.predict(input_data, verbose=0)[0][0]), 2)
                else:
                    # fallback if model not loaded
                    lstm_prediction = round(user_input * 1.05, 2)
                    gru_prediction = round(user_input * 1.03, 2)

                price = round(user_input, 2)
                chart_data = [price, lstm_prediction, gru_prediction]

            except Exception as e:
                print("Prediction Error:", e)
                lstm_prediction = 0
                gru_prediction = 0
                chart_data = [price, 0, 0]

    # ===== Default chart if no prediction =====
    if not chart_data:
        chart_data = [price, round(price * 1.05, 2), round(price * 1.03, 2)]

    # ===== CONTEXT =====
    context = {
        "price": round(price, 2),
        "watchlist": watchlist,
        "portfolio": portfolio,
        "lstm_prediction": lstm_prediction,
        "gru_prediction": gru_prediction,
        "chart_data": json.dumps(chart_data),
    }

    return render(request, "dashboard.html", context)


# ================= PREDICT =================
@login_required
def predict_view(request):
    return dashboard(request)


# ================= LOGOUT =================
def logout_view(request):
    logout(request)
    return redirect("login")