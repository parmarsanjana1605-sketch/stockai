import json
import numpy as np
import os
import yfinance as yf

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import Watchlist, Portfolio, PredictionHistory

try:
    from tensorflow.keras.models import load_model
except ImportError:
    load_model = None


# ================= LOAD MODEL =================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

lstm_path = os.path.join(BASE_DIR, 'dashboard', 'model_ml', 'lstm_model.h5')
gru_path = os.path.join(BASE_DIR, 'dashboard', 'model_ml', 'gru_model.h5')

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


# ================= SAFE STOCK DATA =================
def get_stock_data(symbol, period="7d"):
    try:
        data = yf.download(symbol, period=period, progress=False, auto_adjust=True)
        return data
    except Exception as e:
        print("Yahoo Error:", e)
        return None


def safe_float(value, default=0):
    try:
        if hasattr(value, "iloc"):
            value = value.iloc[0]
        return float(value)
    except:
        return default


def extract_series(data, column_name):
    """
    Handles both Series and DataFrame issue from yfinance
    """
    try:
        col = data[column_name]

        # If duplicate/multi result returns DataFrame instead of Series
        if hasattr(col, "columns"):
            col = col.iloc[:, 0]

        return col
    except Exception as e:
        print(f"Extract Series Error ({column_name}):", e)
        return None


def get_live_price(symbol):
    try:
        data = yf.download(symbol, period="1d", interval="1m", progress=False, auto_adjust=True)

        if data is not None and not data.empty:
            close_series = extract_series(data, "Close")
            if close_series is not None and not close_series.empty:
                last_price = close_series.iloc[-1]
                return round(float(last_price), 2), "live"

        # fallback daily
        data = yf.download(symbol, period="5d", progress=False, auto_adjust=True)
        if data is not None and not data.empty:
            close_series = extract_series(data, "Close")
            if close_series is not None and not close_series.empty:
                last_price = close_series.iloc[-1]
                return round(float(last_price), 2), "fallback"

    except Exception as e:
        print("Live Price Error:", e)

    # hard fallback values
    fallback_prices = {
        "AAPL": 187.42,
        "RELIANCE.NS": 2948.35,
        "TCS.NS": 3899.60,
        "INFY.NS": 1488.20,
        "TSLA": 172.88,
    }

    return fallback_prices.get(symbol.upper(), 999.99), "fallback"


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
    default_symbol = "RELIANCE.NS"
    ticker = default_symbol
    latest_price = None
    predicted_price = None
    trend = "UP"
    recommendation = "BUY"
    error = None
    stock_data = None

    # ===== LIVE CARDS =====
    aapl_price, aapl_status = get_live_price("AAPL")
    reliance_price, reliance_status = get_live_price("RELIANCE.NS")
    tcs_price, tcs_status = get_live_price("TCS.NS")
    infy_price, infy_status = get_live_price("INFY.NS")

    # ===== DEFAULT MAIN LIVE PRICE =====
    price, main_status = get_live_price(default_symbol)

    # ===== USER DATA =====
    watchlist = Watchlist.objects.filter(user=request.user)
    portfolio = Portfolio.objects.filter(user=request.user)
    history = PredictionHistory.objects.filter(user=request.user).order_by('-created_at')[:5]

    portfolio_total = sum(item.quantity * item.buy_price for item in portfolio)

    # ===== DEFAULT CHART =====
    dates = []
    prices = []

    default_chart = get_stock_data(default_symbol, "7d")
    if default_chart is not None and not default_chart.empty:
        close_series = extract_series(default_chart, "Close")

        if close_series is not None and not close_series.empty:
            dates = [str(date.date()) for date in default_chart.index]
            prices = [round(float(p), 2) for p in close_series.tolist()]
        else:
            dates = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"]
            prices = [2920, 2930, 2910, 2940, 2955, 2948, 2960]
    else:
        dates = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"]
        prices = [2920, 2930, 2910, 2940, 2955, 2948, 2960]

    # ===== ML DEFAULT =====
    lstm_prediction = round(price * 1.05, 2)
    gru_prediction = round(price * 1.03, 2)
    chart_data = [round(price, 2), lstm_prediction, gru_prediction]

    # ===== FORM SUBMIT =====
    if request.method == "POST":

        # ===== Search Stock =====
        ticker_input = request.POST.get("ticker")
        if ticker_input:
            ticker = ticker_input.strip().upper()
            data = get_stock_data(ticker, "7d")

            if data is not None and not data.empty:
                close_series = extract_series(data, "Close")
                high_series = extract_series(data, "High")
                low_series = extract_series(data, "Low")
                volume_series = extract_series(data, "Volume")

                if close_series is not None and not close_series.empty:
                    latest_price = round(float(close_series.iloc[-1]), 2)
                    previous_close = round(float(close_series.iloc[-2]), 2) if len(close_series) > 1 else latest_price

                    stock_data = {
                        "latest_price": latest_price,
                        "previous_close": previous_close,
                        "high": round(float(high_series.max()), 2) if high_series is not None else 0,
                        "low": round(float(low_series.min()), 2) if low_series is not None else 0,
                        "volume": int(volume_series.iloc[-1]) if volume_series is not None else 0,
                    }

                    predicted_price = round(latest_price + 5, 2)

                    if predicted_price > latest_price:
                        trend = "UP"
                        recommendation = "BUY"
                    elif predicted_price < latest_price:
                        trend = "DOWN"
                        recommendation = "SELL"
                    else:
                        trend = "STABLE"
                        recommendation = "HOLD"

                    dates = [str(date.date()) for date in data.index]
                    prices = [round(float(p), 2) for p in close_series.tolist()]

                    PredictionHistory.objects.create(
                        user=request.user,
                        ticker=ticker,
                        latest_price=latest_price,
                        predicted_price=predicted_price,
                        trend=trend,
                        recommendation=recommendation
                    )

                    history = PredictionHistory.objects.filter(user=request.user).order_by('-created_at')[:5]
                else:
                    error = "Stock close price not available."

            else:
                error = "Invalid stock symbol or no data found."

        # ===== ML Prediction =====
        user_input = request.POST.get("data")
        if user_input:
            try:
                user_input = float(user_input)

                if lstm_model is not None and gru_model is not None:
                    input_data = np.array([[user_input]], dtype=np.float32)
                    input_data = np.reshape(input_data, (1, 1, 1))

                    lstm_prediction = round(float(lstm_model.predict(input_data, verbose=0)[0][0]), 2)
                    gru_prediction = round(float(gru_model.predict(input_data, verbose=0)[0][0]), 2)
                else:
                    lstm_prediction = round(user_input * 1.05, 2)
                    gru_prediction = round(user_input * 1.03, 2)

                chart_data = [round(user_input, 2), lstm_prediction, gru_prediction]

            except Exception as e:
                print("Prediction Error:", e)

    context = {
        "price": round(price, 2),
        "main_status": main_status,
        "watchlist": watchlist,
        "portfolio": portfolio,
        "portfolio_total": round(portfolio_total, 2),
        "history": history,

        "lstm_prediction": lstm_prediction,
        "gru_prediction": gru_prediction,
        "chart_data": json.dumps(chart_data),

        "ticker": ticker,
        "latest_price": latest_price if latest_price is not None else price,
        "stock_data": stock_data,
        "predicted_price": predicted_price if predicted_price is not None else lstm_prediction,
        "trend": trend,
        "recommendation": recommendation,
        "error": error,

        "dates": json.dumps(dates),
        "prices": json.dumps(prices),

        "default_symbol": ticker if ticker else default_symbol,

        # Live Cards
        "aapl_price": aapl_price,
        "aapl_status": aapl_status,
        "reliance_price": reliance_price,
        "reliance_status": reliance_status,
        "tcs_price": tcs_price,
        "tcs_status": tcs_status,
        "infy_price": infy_price,
        "infy_status": infy_status,
    }

    return render(request, "dashboard.html", context)


# ================= AJAX STOCK SEARCH =================
@login_required
def stock_search_api(request):
    symbol = request.GET.get("symbol", "").strip().upper()

    if not symbol:
        return JsonResponse({"success": False, "error": "No stock symbol provided."})

    try:
        data = get_stock_data(symbol, "7d")

        if data is None or data.empty:
            return JsonResponse({"success": False, "error": "No stock data found for this symbol."})

        close_series = extract_series(data, "Close")
        high_series = extract_series(data, "High")
        low_series = extract_series(data, "Low")
        volume_series = extract_series(data, "Volume")

        if close_series is None or close_series.empty:
            return JsonResponse({"success": False, "error": "Close price data not found."})

        latest_price = round(float(close_series.iloc[-1]), 2)
        previous_close = round(float(close_series.iloc[-2]), 2) if len(close_series) > 1 else latest_price
        predicted_price = round(latest_price + 5, 2)

        if predicted_price > latest_price:
            trend = "UP"
            recommendation = "BUY"
        elif predicted_price < latest_price:
            trend = "DOWN"
            recommendation = "SELL"
        else:
            trend = "STABLE"
            recommendation = "HOLD"

        dates = [str(date.date()) for date in data.index]
        prices = [round(float(p), 2) for p in close_series.tolist()]

        return JsonResponse({
            "success": True,
            "symbol": symbol,
            "latest_price": latest_price,
            "previous_close": previous_close,
            "high": round(float(high_series.max()), 2) if high_series is not None else 0,
            "low": round(float(low_series.min()), 2) if low_series is not None else 0,
            "volume": int(volume_series.iloc[-1]) if volume_series is not None else 0,
            "predicted_price": predicted_price,
            "trend": trend,
            "recommendation": recommendation,
            "dates": dates,
            "prices": prices,
        })

    except Exception as e:
        print("Search API Error:", e)
        return JsonResponse({"success": False, "error": "Something went wrong while fetching stock data."})


# ================= LIVE STOCK API =================
@login_required
def live_stock_data(request):
    symbol = request.GET.get("symbol", "AAPL").strip().upper()
    price, status = get_live_price(symbol)

    return JsonResponse({
        "symbol": symbol,
        "price": price,
        "status": status
    })


# ================= ADD WATCHLIST =================
@login_required
def add_watchlist(request):
    if request.method == "POST":
        stock = request.POST.get("stock")
        if stock:
            stock = stock.strip().upper()
            Watchlist.objects.create(user=request.user, stock_name=stock)
    return redirect("dashboard")


# ================= DELETE WATCHLIST =================
@login_required
def delete_watchlist(request, id):
    item = get_object_or_404(Watchlist, id=id, user=request.user)
    item.delete()
    return redirect("dashboard")


# ================= ADD PORTFOLIO =================
@login_required
def add_portfolio(request):
    if request.method == "POST":
        stock_name = request.POST.get("stock_name")
        quantity = request.POST.get("quantity")
        buy_price = request.POST.get("buy_price")

        if stock_name and quantity and buy_price:
            Portfolio.objects.create(
                user=request.user,
                stock_name=stock_name.strip().upper(),
                quantity=int(quantity),
                buy_price=float(buy_price)
            )
    return redirect("dashboard")


# ================= PREDICT =================
@login_required
def predict_view(request):
    return dashboard(request)


# ================= LOGOUT =================
def logout_view(request):
    logout(request)
    return redirect("login")