.. _efficient-frontier:

###############################
Efficient Frontier Optimisation
###############################

Mathematical optimisation is a very difficult problem in general, particularly when we are dealing
with complex objectives and constraints. However, **convex optimisation** problems are a well-understood
class of problems, which happen to be incredibly useful for finance. A convex problem has the following form:

.. math::

    \begin{equation*}
    \begin{aligned}
    & \underset{\mathbf{x}}{\text{minimise}} & & f(\mathbf{x}) \\
    & \text{subject to} & & g_i(\mathbf{x}) \leq 0, i = 1, \ldots, m\\
    &&& A\mathbf{x} = b,\\
    \end{aligned}
    \end{equation*}

where :math:`\mathbf{x} \in \mathbb{R}^n`, and :math:`f(\mathbf{x}), g_i(\mathbf{x})` are convex functions. [1]_

Fortunately, portfolio optimisation problems (with standard and objective constraints) are convex. This
allows us to immediately apply the vast body of theory as well as the refined solving routines -- accordingly,
the main difficulty is inputting our specific problem into a solver.

PyPortfolioOpt aims to do the hard work for you, allowing for one-liners like ``ef.min_volatility()``
to generate a portfolio that minimises the volatility, while at the same time allowing for more
complex problems to be built up from modular units. This is all possible thanks to 
`cvxpy <https://www.cvxpy.org/>`_, the *fantastic* python-embedded modelling
language for convex optimisation upon which PyPortfolioOpt's efficient frontier functionality lies.

As a brief aside, I should note that while "efficient frontier" optimisation is technically a very
specific method, I tend to use it as a blanket term (interchangeably with mean-variance
optimisation) to refer to anything similar, such as minimising variance.

.. tip::

    You can find complete examples in the relevant cookbook `recipe <https://github.com/robertmartin8/PyPortfolioOpt/blob/master/cookbook/2-Mean-Variance-Optimisation.ipynb>`_.


Structure
=========

As shown in the definition of a convex problem, there are essentially two things we need to specify:
the optimisation objective, and the optimisation constraints. For example, the classic portfolio
optimisation problem is to **minimise risk** subject to a **return constraint** (i.e the portfolio
must return more than a certain amount). From an implementation perspective, however, there is
not much difference between an objective and a constraint. Consider a similar problem, which is to
**maximize return** subject to a **risk constraint** -- now, the role of risk and return have swapped. 

To that end, PyPortfolioOpt defines an :py:mod:`objective_functions` module that contains objective functions
(which can also act as constraints, as we have just seen). The actual optimisation occurs in the :py:class:`efficient_frontier.EfficientFrontier` class.
This class provides straightforward methods for optimising different objectives (all documented below).

However, PyPortfolioOpt was designed so that you can easily add new constraints or objective terms to an existing problem.
For example, adding a regularisation objective (explained below) to a minimum volatility objective is as simple as::

    ef = EfficientFrontier(expected_returns, cov_matrix)  # setup
    ef.add_objective(objective_functions.L2_reg)  # add a secondary objective
    ef.min_volatility()  # find the portfolio that minimises volatility and L2_reg

.. tip::
    
    If you would like to plot the efficient frontier, take a look at the :ref:`plotting` module.

Basic Usage
===========

.. automodule:: pypfopt.efficient_frontier

    .. autoclass:: EfficientFrontier
        :members:
        :exclude-members: custom_objective

        .. automethod:: __init__

            .. note::

                As of v0.5.0, you can pass a collection (list or tuple) of (min, max) pairs
                representing different bounds for different assets.

            .. tip::

                If you want to generate short-only portfolios, there is a quick hack. Multiply
                your expected returns by -1, then optimise a long-only portfolio.


        .. automethod:: max_sharpe

            .. caution::

                Because ``max_sharpe()`` makes a variable substitution, additional objectives may
                not work as intended. 


        .. automethod:: max_quadratic_utility

            .. note::

                ``pypfopt.black_litterman`` provides a method for calculating the market-implied
                risk-aversion parameter, which gives a useful estimate in the absence of other
                information!

        .. automethod:: efficient_risk

            .. caution::

                If you pass an unreasonable target into :py:meth:`efficient_risk` or
                :py:meth:`efficient_return`, the optimiser will fail silently and return
                weird weights. *Caveat emptor* applies!

        .. automethod:: portfolio_performance

            .. tip::

                If you would like to use the ``portfolio_performance`` function independently of any
                optimiser (e.g for debugging purposes), you can use:: 

                    from pypfopt import base_optimizer

                    base_optimizer.portfolio_performance(
                        weights, expected_returns, cov_matrix, verbose=True, risk_free_rate=0.02
                    )

Adding objectives and constraints
=================================

EfficientFrontier inherits from the BaseConvexOptimizer class. In particular, the functions to
add constraints and objectives are documented below:


    .. class:: pypfopt.base_optimizer.BaseConvexOptimizer

        .. automethod:: add_constraint

        .. automethod:: add_sector_constraints

        .. automethod:: add_objective


Objective functions
===================

.. automodule:: pypfopt.objective_functions
    :members:


One of the experimental features implemented in PyPortfolioOpt is the L2 regularisation
parameter ``gamma``, which is discussed below.

.. _L2-Regularisation:

More on L2 Regularisation
=========================

As has been discussed in the :ref:`user-guide`, efficient frontier optimisation often
results in many weights being negligible, i.e the efficient portfolio does not end up
including most of the assets. This is expected behaviour, but it may be undesirable
if you need a certain number of assets in your portfolio.

In order to coerce the efficient frontier optimiser to produce more non-negligible
weights, we add what can be thought of as a "small weights penalty" to all
of the objective functions, parameterised by :math:`\gamma` (``gamma``). Considering
the minimum variance objective for instance, we have:

.. math::
    \underset{w}{\text{minimise}} ~ \left\{w^T \Sigma w \right\} ~~~ \longrightarrow ~~~
    \underset{w}{\text{minimise}} ~ \left\{w^T \Sigma w + \gamma w^T w \right\}

Note that :math:`w^T w` is the same as the sum of squared weights (I didn't
write this explicitly to reduce confusion caused by :math:`\Sigma` denoting both the
covariance matrix and the summation operator). This term reduces the number of
negligible weights, because it has a minimum value when all weights are
equally distributed, and maximum value in the limiting case where the entire portfolio
is allocated to one asset. I refer to it as **L2 regularisation** because it has
exactly the same form as the L2 regularisation term in machine learning, though
a slightly different purpose (in ML it is used to keep weights small while here it is
used to make them larger).

.. note::

    In practice, :math:`\gamma` must be tuned to achieve the level
    of regularisation that you want. However, if the universe of assets is small
    (less than 20 assets), then ``gamma=1`` is a good starting point. For larger
    universes, or if you want more non-negligible weights in the final portfolio,
    increase ``gamma``.


.. _custom-optimisation:

Custom optimisation problems
============================

Previously we described an API for adding constraints and objectives to one of the core
optimisation problems in the ``EfficientFrontier`` class. However, what if you aren't interested
in anything related to ``max_sharpe()``, ``min_volatility()``, ``efficient_risk()`` etc and want to
set up a completely new problem to optimise for some custom objective?

The ``EfficientFrontier`` class inherits from the ``BaseConvexOptimizer``, which allows you to
define your own optimisation problem. You can either optimise some generic ``convex_objective``
(which *must* be built using ``cvxpy`` atomic functions -- see `here <https://www.cvxpy.org/tutorial/functions/index.html>`_)
or a ``nonconvex_objective``, which uses ``scipy.optimize`` as the backend and thus has a completely
different API. For examples, check out this `cookbook recipe <https://github.com/robertmartin8/PyPortfolioOpt/blob/master/cookbook/3-Advanced-Mean-Variance-Optimisation.ipynb>`_

    .. class:: pypfopt.base_optimizer.BaseConvexOptimizer

        .. automethod:: convex_objective
        
        .. automethod:: nonconvex_objective


References
==========

.. [1] Boyd, S.; Vandenberghe, L. (2004). `Convex Optimization <https://web.stanford.edu/~boyd/cvxbook/>`_.

