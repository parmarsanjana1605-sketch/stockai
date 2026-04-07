from django.contrib import admin
from django.urls import path, include
from dashboard import views

urlpatterns = [
    path('', views.login_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('predict/', views.predict_view, name='predict'),
    path('logout/', views.logout_view, name='logout'),
    path('accounts/', include('allauth.urls')),
    path('live-stock-data/' ,views.live_stock_data,name='live_stock_data'),
    path("stock-search-api/", views.stock_search_api, name="stock_search_api"),

    path("add-watchlist/", views.add_watchlist, name="add_watchlist"),
    path("delete-watchlist/<int:pk>/", views.delete_watchlist, name="delete_watchlist"),

    path("add-portfolio/", views.add_portfolio, name="add_portfolio"),

]