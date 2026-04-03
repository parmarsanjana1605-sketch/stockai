from django.db import models
from django.contrib.auth.models import User

class Watchlist(models.Model):

    user = models.ForeignKey(User,on_delete=models.CASCADE)
    stock_name = models.CharField(max_length=20)

    def __str__(self):
        return self.stock_name


class Portfolio(models.Model):

    user = models.ForeignKey(User,on_delete=models.CASCADE)
    stock_name = models.CharField(max_length=20)
    quantity = models.IntegerField()
    buy_price = models.FloatField()

def __str__(self):
    return f"{self.stock_name} - {self.user.username}"