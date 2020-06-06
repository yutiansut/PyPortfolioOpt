"""
The ``discrete_allocation`` module contains the ``DiscreteAllocation`` class, which
offers multiple methods to generate a discrete portfolio allocation from continuous weights.
"""

import numpy as np
import pandas as pd
import cvxpy as cp
from . import exceptions


def get_latest_prices(prices):
    """
    A helper tool which retrieves the most recent asset prices from a dataframe of
    asset prices, required in order to generate a discrete allocation.

    :param prices: historical asset prices
    :type prices: pd.DataFrame
    :raises TypeError: if prices are not in a dataframe
    :return: the most recent price of each asset
    :rtype: pd.Series
    """
    if not isinstance(prices, pd.DataFrame):
        raise TypeError("prices not in a dataframe")
    return prices.ffill().iloc[-1]


class DiscreteAllocation:
    """
    Generate a discrete portfolio allocation from continuous weights

    Instance variables:

    - Inputs:

        - ``weights`` - dict
        - ``latest_prices`` - pd.Series or dict
        - ``total_portfolio_value`` - int/float
        - ``short_ratio``- float

    - Output: ``allocation`` - dict

    Public methods:

    - ``greedy_portfolio()`` - uses a greedy algorithm
    - ``lp_portfolio()`` - uses linear programming
    """

    def __init__(
        self, weights, latest_prices, total_portfolio_value=10000, short_ratio=0.30
    ):
        """
        :param weights: continuous weights generated from the ``efficient_frontier`` module
        :type weights: dict
        :param latest_prices: the most recent price for each asset
        :type latest_prices: pd.Series
        :param total_portfolio_value: the desired total value of the portfolio, defaults to 10000
        :type total_portfolio_value: int/float, optional
        :param short_ratio: the short ratio, e.g 0.3 corresponds to 130/30
        :type short_ratio: float
        :raises TypeError: if ``weights`` is not a dict
        :raises TypeError: if ``latest_prices`` isn't a series
        :raises ValueError: if ``short_ratio < 0``
        """
        if not isinstance(weights, dict):
            raise TypeError("weights should be a dictionary of {ticker: weight}")
        if not isinstance(latest_prices, pd.Series):
            raise TypeError("latest_prices should be a pd.Series")
        if total_portfolio_value <= 0:
            raise ValueError("total_portfolio_value must be greater than zero")
        if short_ratio <= 0:
            raise ValueError("short_ratio must be positive")

        # Drop any companies with negligible weights. Use a tuple because order matters.
        self.weights = list(weights.items())
        self.latest_prices = latest_prices
        self.total_portfolio_value = total_portfolio_value
        self.short_ratio = short_ratio

    @staticmethod
    def _remove_zero_positions(allocation):
        """
        Utility function to remove zero positions (i.e with no shares being bought)

        :type allocation: dict
        """
        return {k: v for k, v in allocation.items() if v != 0}

    def _allocation_rmse_error(self, verbose=True):
        """
        Utility function to calculate and print RMSE error between discretised
        weights and continuous weights. RMSE was used instead of MAE because we
        want to penalise large variations.

        :param verbose: print weight discrepancies?
        :type verbose: bool
        :return: rmse error
        :rtype: float
        """
        portfolio_val = 0
        for ticker, num in self.allocation.items():
            portfolio_val += num * self.latest_prices[ticker]

        sse = 0  # sum of square errors
        for ticker, weight in self.weights:
            if ticker in self.allocation:
                allocation_weight = (
                    self.allocation[ticker] * self.latest_prices[ticker] / portfolio_val
                )
            else:
                allocation_weight = 0
            sse += (weight - allocation_weight) ** 2
            if verbose:
                print(
                    "{}: allocated {:.3f}, desired {:.3f}".format(
                        ticker, allocation_weight, weight
                    )
                )
        rmse = np.sqrt(sse / len(self.weights))
        print("Allocation has RMSE: {:.3f}".format(rmse))
        return rmse

    def greedy_portfolio(self, verbose=False):
        """
        Convert continuous weights into a discrete portfolio allocation
        using a greedy iterative approach.

        :param verbose: print error analysis?
        :type verbose: bool
        :return: the number of shares of each ticker that should be purchased,
                 along with the amount of funds leftover.
        :rtype: (dict, float)
        """
        # Sort in descending order of weight
        self.weights.sort(key=lambda x: x[1], reverse=True)

        # If portfolio contains shorts
        if self.weights[-1][1] < 0:
            longs = {t: w for t, w in self.weights if w >= 0}
            shorts = {t: -w for t, w in self.weights if w < 0}

            # Make them sum to one
            long_total_weight = sum(longs.values())
            short_total_weight = sum(shorts.values())
            longs = {t: w / long_total_weight for t, w in longs.items()}
            shorts = {t: w / short_total_weight for t, w in shorts.items()}

            # Construct long-only discrete allocations for each
            short_val = self.total_portfolio_value * self.short_ratio

            if verbose:
                print("\nAllocating long sub-portfolio...")
            da1 = DiscreteAllocation(
                longs,
                self.latest_prices[longs.keys()],
                total_portfolio_value=self.total_portfolio_value,
            )
            long_alloc, long_leftover = da1.greedy_portfolio()

            if verbose:
                print("\nAllocating short sub-portfolio...")
            da2 = DiscreteAllocation(
                shorts,
                self.latest_prices[shorts.keys()],
                total_portfolio_value=short_val,
            )
            short_alloc, short_leftover = da2.greedy_portfolio()
            short_alloc = {t: -w for t, w in short_alloc.items()}

            # Combine and return
            self.allocation = long_alloc.copy()
            self.allocation.update(short_alloc)
            self.allocation = self._remove_zero_positions(self.allocation)

            return self.allocation, long_leftover + short_leftover

        # Otherwise, portfolio is long only and we proceed with greedy algo
        available_funds = self.total_portfolio_value
        shares_bought = []
        buy_prices = []

        # First round
        for ticker, weight in self.weights:
            price = self.latest_prices[ticker]
            # Attempt to buy the lower integer number of shares
            n_shares = int(weight * self.total_portfolio_value / price)
            cost = n_shares * price
            if cost > available_funds:
                # Buy as many as possible
                n_shares = available_funds // price
                if n_shares == 0:
                    print("Insufficient funds")
            available_funds -= cost
            shares_bought.append(n_shares)
            buy_prices.append(price)

        # Second round
        while available_funds > 0:
            # Calculate the equivalent continuous weights of the shares that
            # have already been bought
            current_weights = np.array(buy_prices) * np.array(shares_bought)
            current_weights /= current_weights.sum()
            ideal_weights = np.array([i[1] for i in self.weights])
            deficit = ideal_weights - current_weights

            # Attempt to buy the asset whose current weights deviate the most
            idx = np.argmax(deficit)
            ticker, weight = self.weights[idx]
            price = self.latest_prices[ticker]

            # If we can't afford this asset, search for the next highest deficit that we
            # can purchase.
            counter = 0
            while price > available_funds:
                deficit[idx] = 0  # we can no longer purchase the asset at idx
                idx = np.argmax(deficit)  # find the next most deviant asset

                # If either of these conditions is met, we break out of both while loops
                # hence the repeated statement below
                if deficit[idx] < 0 or counter == 10:
                    break

                ticker, weight = self.weights[idx]
                price = self.latest_prices[ticker]
                counter += 1

            if deficit[idx] <= 0 or counter == 10:
                # Dirty solution to break out of both loops
                break

            # Buy one share at a time
            shares_bought[idx] += 1
            available_funds -= price

        self.allocation = self._remove_zero_positions(
            dict(zip([i[0] for i in self.weights], shares_bought))
        )

        if verbose:
            print("Funds remaining: {:.2f}".format(available_funds))
            self._allocation_rmse_error(verbose)
        return self.allocation, available_funds

    def lp_portfolio(self, verbose=False):
        """
        Convert continuous weights into a discrete portfolio allocation
        using integer programming.

        :param verbose: print error analysis?
        :type verbose: bool
        :return: the number of shares of each ticker that should be purchased, along with the amount
                of funds leftover.
        :rtype: (dict, float)
        """
        if any([w < 0 for _, w in self.weights]):
            longs = {t: w for t, w in self.weights if w >= 0}
            shorts = {t: -w for t, w in self.weights if w < 0}

            # Make them sum to one
            long_total_weight = sum(longs.values())
            short_total_weight = sum(shorts.values())
            longs = {t: w / long_total_weight for t, w in longs.items()}
            shorts = {t: w / short_total_weight for t, w in shorts.items()}

            # Construct long-only discrete allocations for each
            short_val = self.total_portfolio_value * self.short_ratio

            if verbose:
                print("\nAllocating long sub-portfolio:")
            da1 = DiscreteAllocation(
                longs,
                self.latest_prices[longs.keys()],
                total_portfolio_value=self.total_portfolio_value,
            )
            long_alloc, long_leftover = da1.lp_portfolio()

            if verbose:
                print("\nAllocating short sub-portfolio:")
            da2 = DiscreteAllocation(
                shorts,
                self.latest_prices[shorts.keys()],
                total_portfolio_value=short_val,
            )
            short_alloc, short_leftover = da2.lp_portfolio()
            short_alloc = {t: -w for t, w in short_alloc.items()}

            # Combine and return
            self.allocation = long_alloc.copy()
            self.allocation.update(short_alloc)
            self.allocation = self._remove_zero_positions(self.allocation)
            return self.allocation, long_leftover + short_leftover

        p = self.latest_prices.values
        n = len(p)
        w = np.fromiter([i[1] for i in self.weights], dtype=float)

        # Integer allocation
        x = cp.Variable(n, integer=True)
        # Remaining dollars
        r = self.total_portfolio_value - p.T * x

        # Objective function is remaining dollars + sum of absolute deviations from ideality.
        objective = r + cp.norm(w * self.total_portfolio_value - cp.multiply(x, p), 1)
        constraints = [r + p.T * x == self.total_portfolio_value, x >= 0, r >= 0]

        opt = cp.Problem(cp.Minimize(objective), constraints)
        opt.solve()

        if opt.status not in {"optimal", "optimal_inaccurate"}:
            raise exceptions.OptimizationError("Please try greedy_portfolio")

        vals = np.rint(x.value)
        self.allocation = self._remove_zero_positions(
            dict(zip([i[0] for i in self.weights], vals))
        )

        if verbose:
            print("Funds remaining: {:.2f}".format(r.value))
            self._allocation_rmse_error()
        return self.allocation, r.value
