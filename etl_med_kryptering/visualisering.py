"""Visualisering module.

Each function takes a pandas DataFrame (built by the caller from data
read back out of the database) and renders one chart, with labelled
axes and a title.
"""

import matplotlib.pyplot as plt


def scatter_plot(df):
    """Sepal length (x) vs petal length (y)."""
    fig, ax = plt.subplots()
    ax.scatter(df["sepal_length"], df["petal_length"])
    ax.set_xlabel("Sepallængde (sepal_length)")
    ax.set_ylabel("Kronbladlængde (petal_length)")
    ax.set_title("Scatter Plot: Sepal Length vs Petal Length (Iris-setosa)")
    plt.show()
    return fig


def histogram(df):
    """Distribution of petal_width, ~10 bins."""
    fig, ax = plt.subplots()
    ax.hist(df["petal_width"], bins=10, edgecolor="black")
    ax.set_xlabel("Kronbladsbredde (petal_width)")
    ax.set_ylabel("Frekvens")
    ax.set_title("Histogram: Petal Width (Iris-setosa)")
    plt.show()
    return fig


def boxplot(df):
    """2x2 layout of boxplots, one per numeric measurement."""
    columns = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
    fig, axes = plt.subplots(2, 2, figsize=(8, 8))
    fig.suptitle("Boxplots af alle numeriske Iris-setosa målinger")

    for ax, column in zip(axes.flat, columns):
        ax.boxplot(df[column])
        ax.set_title(column)
        ax.set_ylabel("Værdi")
        ax.set_xticks([])

    plt.tight_layout()
    plt.show()
    return fig
