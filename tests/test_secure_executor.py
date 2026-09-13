"""Security regression tests for the chart-code sandbox (no API calls)."""

import time

import pandas as pd
import pytest

from datacern.charts.secure_executor import SecurityError, execute_code, validate_source

DF = pd.DataFrame(
    {
        "region": ["N", "N", "S", "S"],
        "rev": [100, 200, 150, 50],
        "profit": [10, 20, 15, 5],
    }
)

VALID_CODE = """
import matplotlib.pyplot as plt
import seaborn as sns
g = df.groupby('region')['rev'].sum()
print('sum by region:', g.to_dict())
fig, ax = plt.subplots(figsize=(6,4))
ax.bar(g.index, g.values)
fig2, ax2 = plt.subplots()
sns.histplot(df['rev'], ax=ax2)
"""


def test_valid_charts_produce_images():
    result = execute_code(VALID_CODE, dataframe=DF)
    assert result["success"] is True
    assert len(result["images"]) == 2
    assert all(len(png) > 5_000 for png in result["images"])
    assert "sum by region" in result["stdout"]


@pytest.mark.parametrize(
    "code",
    [
        "import os\nos.system('echo hi')",
        "f = open('x.txt','w')",
        "x = eval('1+1')",
        "y = getattr(df, '__class__')",
        "import requests",
        "import subprocess\nsubprocess.run(['echo'])",
        "x = df.to_csv('out.csv')",
        "import matplotlib.pyplot as plt\nplt.savefig('x.png')",
    ],
)
def test_blocked_constructs(code):
    with pytest.raises(SecurityError):
        validate_source(code)
    result = execute_code(code, dataframe=DF)
    assert result["success"] is False
    assert result["error"].startswith("SECURITY BLOCKED")


def test_runtime_error_reported():
    result = execute_code("x = 1/0", dataframe=DF)
    assert result["success"] is False
    assert "ZeroDivisionError" in result["error"]


def test_timeout_kills_infinite_loop():
    start = time.perf_counter()
    result = execute_code("while True: pass", dataframe=DF, timeout=2)
    elapsed = time.perf_counter() - start
    assert result["success"] is False
    assert "timed out" in result["error"]
    assert elapsed < 15
