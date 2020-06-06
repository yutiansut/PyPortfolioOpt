.. _plotting:

########
Plotting
########


.. automodule:: pypfopt.plotting

    .. autoclass:: Plotting

        .. automethod:: _plot_io

        .. tip::

            To save the plot, pass ``filename="somefile.png"`` as a keyword argument to any of
            the methods below.

        .. automethod:: plot_covariance

        .. image:: ../media/corrplot.png
            :align: center
            :width: 80%
            :alt: plot of the covariance matrix

        .. automethod:: plot_dendrogram

        .. image:: ../media/dendrogram.png
            :width: 80%
            :align: center
            :alt: return clusters

        .. automethod:: plot_efficient_frontier

        .. image:: ../media/cla_plot.png
            :width: 80%
            :align: center
            :alt: the Efficient Frontier

        .. automethod:: plot_weights

        .. image:: ../media/weight_plot.png
            :width: 80%
            :align: center
            :alt: bar chart to show weights
