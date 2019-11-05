"""
Wrapper to plot distribution in beautiful formats!
"""

import numpy as np

from matplotlib import pyplot as plt
from matplotlib.ticker import FixedFormatter


def plot_violinplot(list_data, figsize=(6, 4), baseline=None,
                    face_colours=None, edge_colours=None,
                    fontsize=14, fontweight='bold', rotation=0,
                    xlabel=None, xticklabels=None,
                    xminortick=None, xminorticklabels=None,
                    ylabel=None, ylim=None,
                    plot_median=False, plot_mean=False,
                    save_name=None):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(1, 1, 1)

    num_groups = len(list_data)

    violin_parts = ax.violinplot(
        list_data, showmeans=plot_mean, showmedians=plot_median
    )
    # setting colours
    if face_colours is not None:
        for i, pc in enumerate(violin_parts['bodies']):
            color = face_colours[i]
            pc.set_facecolor(color)
    if edge_colours is not None:
        for i, pc in enumerate(violin_parts['bodies']):
            color = edge_colours[i]
            pc.set_edgecolor(color)

    # the first element of baseline is its value, the second its name
    if baseline is not None:
        baseline_part = ax.axhline(
            y=baseline[0], linestyle=':', linewidth=2, color='r'
        )
        ax.legend(
            [baseline_part], [baseline[1]],
            prop={'weight': fontweight, 'size': fontsize}
        )

    # x-axis
    if xlabel is not None:
        ax.set_xlabel(xlabel, fontsize=fontsize, fontweight=fontweight)
    if xticklabels is not None:
        ax.set_xticks([y + 1 for y in range(num_groups)])
        ax.set_xticklabels(xticklabels, rotation=rotation)
    if xminortick is not None:
        ax.set_xticks(xminortick, minor=True)
        ax.xaxis.set_minor_formatter(FixedFormatter(xminorticklabels))
        ax.xaxis.set_tick_params(bottom=False, which='minor')

    # y-axis
    if ylim is not None:
        ax.set_ylim(ylim)
    ax.yaxis.grid(True)
    if ylabel is not None:
        ax.set_ylabel(ylabel, fontsize=fontsize, fontweight=fontweight)

    # if to be saved
    if save_name is not None:
        fig.tight_layout()
        plt.savefig(save_name)
    plt.show()


def plot_dist1_vs_dist2(dist1, dist2, figsize=(4, 4),
                        color='b', marker='o',
                        fontsize=14, fontweight='bold',
                        xlabel=None, xlim=None,
                        ylabel=None, ylim=None,
                        save_name=None):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(1, 1, 1)

    ax.scatter(dist1, dist2, color=color, marker=marker)
    min_val = np.minimum(dist1.min(), dist2.min())
    max_val = np.maximum(dist1.max(), dist2.max())
    ds = (min_val, max_val)
    de = (min_val, max_val)
    ax.plot(ds, de, '--k')

    # x-axis
    if xlim is not None:
        ax.set_xlim(xlim)
    if xlabel is not None:
        ax.set_xlabel(xlabel, fontsize=fontsize, fontweight=fontweight)

    # y-axis
    if ylim is not None:
        ax.set_ylim(ylim)
    if ylabel is not None:
        ax.set_ylabel(ylabel, fontsize=fontsize, fontweight=fontweight)

    ax.axis('equal')

    # if to be saved
    if save_name is not None:
        fig.tight_layout()
        plt.savefig(save_name)
    plt.show()