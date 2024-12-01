# Firefly III FinTS Importer
This is a simple Python script to import FinTS (formerly known as HBCI) data into Firefly III.
It is based on the [Firefly III API](https://firefly-iii.readthedocs.io/en/latest/api/index.html) used via the [python client](https://github.com/ms32035/firefly-iii-client) and [PyFinTS](https://github.com/raphaelm/python-fints).
It was heavily inspired by the [existing Firefly III FinTS importer](https://github.com/bnw/firefly-iii-fints-importer).

> [!NOTE]  
> I was frustrated with the way the existing importer treated the data and wanted to customize it. This script just reflects my needs, but maybe it is useful for someone else as well.

## Installation
1. Clone the repository
2. Create and activate a virtual environment
3. Install the requirements and the package with `poetry install` or `pip install -e .`
4. Copy the `.env.example` file to `.env` and adjust the settings

## Usage
From inside the virtual environment, run the script with `python main.py`.
If `FINTS_PIN` is not set in the `.env` file, you will be prompted to enter it.
If your bank requires 2FA, you will be prompted to execute the required steps.
By default, the script will import all transactions from the last 7 days. You can change this by passing the `--days` argument.
You don't need to worry about duplicate imports, as Firefly III will reject transactions that are already present.
