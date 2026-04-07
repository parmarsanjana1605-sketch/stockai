from django.db import models
from django.contrib.auth.models import User

class Watchlist(models.Model):

    user = models.ForeignKey(User,on_delete=models.CASCADE)
    stock_name = models.CharField(max_length=50)

    def __str__(self):
        return self.stock_name


class Portfolio(models.Model):

    user = models.ForeignKey(User,on_delete=models.CASCADE)
    stock_name = models.CharField(max_length=50)
    quantity = models.IntegerField()
    buy_price = models.FloatField()

class PredictionHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ticker = models.CharField(max_length=20)
    latest_price = models.FloatField()
    predicted_price = models.FloatField()
    trend = models.CharField(max_length=20)
    recommendation = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    
def __str__(self):
    return f"{self.stock_name} - {self.user.username}"