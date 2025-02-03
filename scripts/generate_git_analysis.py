# pip install gitpython matplotlib pandas
import git
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import matplotlib.dates as mdates
from matplotlib.dates import DateFormatter
import pytz


def analyze_git_history(repo_path=".", file_extensions=None):
    # Default to common code file extensions if none specified
    if file_extensions is None:
        file_extensions = [".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html"]

    # Initialize repository
    repo = git.Repo(repo_path)

    # Store commit data
    commit_data = []

    # Iterate through all commits
    for commit in repo.iter_commits("main"):
        # Get total lines of code for files with specified extensions
        total_lines = 0

        try:
            # Get the entire tree of the commit
            tree = commit.tree

            for blob in tree.traverse():
                if isinstance(blob, git.Blob):
                    # Check if file has one of the specified extensions
                    if any(blob.path.endswith(ext) for ext in file_extensions):
                        try:
                            # Count lines in the file
                            content = blob.data_stream.read().decode("utf-8")
                            total_lines += len(content.splitlines())
                        except:
                            # Skip files that can't be decoded
                            continue

            commit_data.append(
                {"date": commit.committed_datetime, "lines": total_lines}
            )
        except:
            continue

    # Convert to DataFrame and sort by date
    df = pd.DataFrame(commit_data)

    # Convert dates to PST timezone
    pst = pytz.timezone("America/Los_Angeles")
    df["date"] = df["date"].apply(lambda x: x.astimezone(pst))
    df = df.sort_values("date")

    # Plot styling improvements
    plt.style.use(
        "bmh"
    )  # Using 'bmh' style instead of seaborn for better default looks
    fig, ax = plt.subplots(figsize=(15, 8), facecolor="white")  # Added white background

    # Plot all data first
    ax.plot(
        df["date"],
        df["lines"],
        marker="o",
        linestyle="-",
        linewidth=2,
        markersize=6,
        color="#2E86C1",  # Nice blue color
        alpha=0.8,
    )

    # Highlight first two days of commits
    first_date = df["date"].min()
    two_day_mask = (df["date"] - first_date).dt.total_seconds() <= 2 * 24 * 3600
    first_two_days = df[two_day_mask]

    ax.plot(
        first_two_days["date"],
        first_two_days["lines"],
        marker="o",
        linestyle="-",
        linewidth=2,
        markersize=8,
        color="#E74C3C",  # Highlight color (red)
        alpha=1.0,
    )

    # Set background color
    ax.set_facecolor("white")

    # Improve title and labels
    ax.set_title(
        "Lines of Code Over Time",
        fontsize=16,
        pad=20,
        fontweight="bold",
    )
    ax.set_xlabel("Date", fontsize=12, labelpad=10)
    ax.set_ylabel("Lines of Code", fontsize=12, labelpad=10)

    # Format dates on x-axis
    ax.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())

    # Customize grid
    ax.grid(True, linestyle="--", alpha=0.7)

    # Rotate and align the tick labels so they look better
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    # Add some padding to prevent label cutoff
    plt.tight_layout()

    # Save with higher DPI for better quality
    plt.savefig("code_history.png", dpi=300, bbox_inches="tight")
    print(f"Plot saved as 'code_history.png'")


if __name__ == "__main__":
    # python scripts\git_analysis.py
    repo_path = Path.cwd()
    analyze_git_history(repo_path)
