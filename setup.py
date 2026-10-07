from setuptools import setup, find_packages

setup(
    name="futures-research-backtester",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.12",
    entry_points={"console_scripts": ["backtester=backtester.__main__:main"]},
    extras_require={"test": ["pytest==8.4.2"], "databento": ["databento==0.87.0"]},
)
