from setuptools import setup

setup(
    name="saihu",
    version="1.0.0",
    author="Chun-Tso Tsai",
    author_email="chun-tso.tsai@epfl.ch",
    license="MIT",
    description="Saihu Common Interface for Worst-Case Delay Analysis of Time-Sensitive Networks",
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
