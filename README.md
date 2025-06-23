# Script for creating MMD files using Thredds

## Installation

1. The project uses `uv` to manage dependencies. It can be installed on Linux/MacOS by running the following command: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. When uv has been installed clone the repository by running: `git clone https://github.com/huaracheguarache/mmd_creation.git`

## Running the script

1. Enter the repository directory. It will be named `mmd_creation`, and will be located in the directory where you ran the `git clone` command during the installation.
2. Enter the `src` directory where the script is located. The main script is the file named `main.py`, and the file `example.py` provides an example of how the script works.
3. Run the example file using the following command (it will automatically install the necessary python version and dependencies before running the script): `uv run python example.py`