import math
import numpy as np


def _cumulative_distribution(n_dist) -> float:
    return 0.5 * (1 + math.erf(n_dist / np.sqrt(2)))

def call_formula(stockPrice, strikePrice, riskFreeInterestRate, timeToExpiration, volatility) -> float:
        d1 = (np.log(stockPrice / strikePrice) +
              (riskFreeInterestRate + 0.5 * volatility ** 2) * timeToExpiration) / \
             (volatility * np.sqrt(timeToExpiration))

        d2 = d1 - volatility * np.sqrt(timeToExpiration)

        return (stockPrice * _cumulative_distribution(d1)
        - strikePrice * math.exp(-riskFreeInterestRate * timeToExpiration) * _cumulative_distribution(d2))
