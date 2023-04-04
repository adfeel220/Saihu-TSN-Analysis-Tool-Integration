from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="saihu",
    version="1.0.0",
    author="Chun-Tso Tsai",
    author_email="chun-tso.tsai@epfl.ch",
    license="BSD",
    description="Saihu Common Interface for Worst-Case Delay Analysis of Time-Sensitive Networks",
    long_description=long_description,
    packages=[
        "saihu",
        "saihu.panco",
        "saihu.javapy",
        "saihu.xtfa",
        "saihu.Linear_TFA",
        "saihu.netscript",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Java",
        "Operating System :: OS Independent",
        "Natural Language :: English",
    ],
    install_requires=["numpy", "matplotlib", "pulp", "networkx", "mdutils"],
    python_requires=">=3.9",
)
