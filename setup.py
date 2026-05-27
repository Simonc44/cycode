from setuptools import setup, find_packages

setup(
    name="cycode",
    version="2.0.100",
    packages=find_packages(),
    install_requires=[
        "rich>=13.0.0",
        "prompt_toolkit>=3.0.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "cycode=src.cycode_cli:main",
        ],
    },
    python_requires=">=3.9",
)
