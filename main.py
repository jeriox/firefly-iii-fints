import argparse
import json
import logging
import os
from datetime import date, timedelta
import getpass

import firefly_iii_client
from dotenv import load_dotenv
from fints.client import FinTS3PinTanClient
from fints.utils import minimal_interactive_cli_bootstrap


def format_transaction(transaction):
    return f"{transaction.data['amount']} @ {transaction.data.get('deviate_applicant') or transaction.data.get('applicant_name')} on {transaction.data['date']}"


def convert_transaction(transaction, firefly_accounts, firefly_account_id):
    data = {
        "amount": str(abs(transaction.data["amount"].amount)),
        "var_date": transaction.data["date"],
        "description": transaction.data.get("deviate_applicant") or transaction.data.get("purpose")
    }

    if transaction.data["status"] == "C":  # credit
        data["destination_id"] = firefly_account_id
        if firefly_source_id := firefly_accounts.get(transaction.data["applicant_iban"]):  # transfer
            data["type"] = "transfer"
            data["source_id"] = firefly_source_id
        else:
            data["source_name"] = transaction.data.get("deviate_applicant") or transaction.data.get(
                "applicant_name")
            data["type"] = "deposit"
    elif transaction.data["status"] == "D":  # debit
        data["source_id"] = firefly_account_id
        if firefly_destination_id := firefly_accounts.get(transaction.data["applicant_iban"]):  # transfer
            data["type"] = "transfer"
            data["destination_id"] = firefly_destination_id
        else:
            data["destination_name"] = transaction.data.get("deviate_applicant") or transaction.data.get(
                "applicant_name")
            data["type"] = "withdrawal"
    return data


def import_transactions(days: int):
    firefly_config = firefly_iii_client.configuration.Configuration(host=os.environ["FIREFLY_URL"],
                                                                    access_token=os.environ["FIREFLY_ACCESS_TOKEN"])
    with firefly_iii_client.ApiClient(firefly_config) as api_client:
        # set up Firefly-III API
        transaction_api = firefly_iii_client.TransactionsApi(api_client)
        accounts_api = firefly_iii_client.AccountsApi(api_client)
        try:
            api_response = accounts_api.list_account(type="asset")
            firefly_accounts = {account.attributes.iban: account.id for account in api_response.data}
        except Exception as e:
            logging.log(logging.ERROR, "Exception when fetching accounts from Firefly: %s\n" % e)
            return

        # set up FinTS connection
        f = FinTS3PinTanClient(
            os.environ["FINTS_BLZ"],
            os.environ["FINTS_USER"],
            os.environ.get("FINTS_PIN") or getpass.getpass('Enter PIN:'),
            os.environ["FINTS_URL"],
            product_id=os.environ["FINTS_PRODUCT_ID"],
        )
        minimal_interactive_cli_bootstrap(f)
        with f:
            # Since PSD2, a TAN might be needed for dialog initialization. Let's check if there is one required
            if f.init_tan_response:
                print("A TAN is required", f.init_tan_response.challenge)
                tan = input('Please enter TAN:')
                f.send_tan(f.init_tan_response, tan)

            # Fetch accounts
            accounts = f.get_sepa_accounts()
            today = date.today()

            for account in accounts:
                if not (firefly_account_id := firefly_accounts.get(account.iban)):
                    print(f"No Firefly account found for {account.iban}")
                    continue
                for transaction in f.get_transactions(account, start_date=today - timedelta(days=days), end_date=today):
                    data = convert_transaction(transaction, firefly_accounts, firefly_account_id)
                    try:
                        api_response = transaction_api.store_transaction({"error_if_duplicate_hash": True, "transactions": [data]})
                        logging.log(logging.INFO, f"Successfully created transaction #{api_response.data.id} ({format_transaction(transaction)})")
                    except Exception as e:
                        if isinstance(e, firefly_iii_client.ApiException) and e.status == 422:
                            reason = json.loads(e.body)["errors"][0]["detail"]
                            logging.log(logging.WARNING, f"Firefly rejected the transaction ({format_transaction(transaction)}): {reason}")
                        else:
                            logging.log(logging.ERROR, f"Exception when calling TransactionsApi->store_transaction: {e}\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--days", type=int, default=7,
                        help="Number of days (backwards from today) to fetch transactions for (default: 7)")
    args = parser.parse_args()
    import_transactions(args.days)
