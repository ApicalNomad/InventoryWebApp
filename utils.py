import os
import csv
import pandas as pd
from apiclient import discovery
from google.oauth2 import service_account
import pytz
from datetime import datetime, date, timedelta  # , time
from .models import Vendor, Product, Procedure, PurchaseOrder, PO_Item, Lifeline
from django.db.models import Q
from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from typing import Union, List, Tuple, Optional

# import json
# import time
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import traceback
import threading
from django.db import transaction
from googleapiclient.errors import HttpError
from dateutil import parser

thread_lock = threading.Lock()

# from .pydb import settings
# settings.configure()

"""
12/07/2023: need to eventually migrate away from pytz, use django.utils.timezone, as so:
timezone.localtime() = datetime.datetime(2023, 12, 7, 11, 59, 23, 512790, tzinfo=zoneinfo.ZoneInfo(key='US/Eastern'))


"""



def recompose_date(
    phrase: str, delim: str = "", db_format: bool = True, return_str: bool = True
) -> Union[str, datetime]:
    """
    Args as follows:
        phrase = str/datetime, what is to be processed;
        delim = str, what to split it by, optional;
        db_format = bool, default is True/"YYYY-MM-DD", else "MM-DD-YYYY";
        return_str = bool, default is True/string type, else datetime object.

    Providing a delim value enforces True on return_str (result of string object),
    as it is excessively branching if delim exists but then return object sought
    is a formatted date object.
    """
    from dateutil.parser import ParserError

    if isinstance(phrase, datetime):
        formatted_date = (
            phrase.strftime("%Y-%m-%d") if db_format else phrase.strftime("%m-%d-%Y")
        )
        return (
            formatted_date
            if return_str
            else datetime.strptime(formatted_date, "%Y-%m-%d")
        )
    phrase = (
        phrase.strip()
    )  # keep original phrase arg separate, as it will get date part replaced if needed
    date_str_text = phrase  # either the phrase is entirely a date string, or getting extracted below
    if delim != "":
        date_str_text = phrase.split(delim.strip())[2]
    try:
        parsed_date_obj = parser.parse(date_str_text).date()
    except (ParserError, ValueError, AttributeError, TypeError, OverflowError):
        print("this is not a date, skipping, in recompose_date func")
        return None
    formatted_date = (
        parsed_date_obj.strftime("%Y-%m-%d")
        if db_format
        else parsed_date_obj.strftime("%m-%d-%Y")
    )
    if not delim and return_str:
        return formatted_date
    if delim and return_str:
        phrase = phrase.replace(date_str_text, formatted_date)
    if not return_str:
        # now = datetime.now(tz=pytz.timezone("US/Eastern"))
        # dateobj_with_tz = pytz.timezone('US/Eastern')
        # dateobj_to_localize = expiry_with_tz.localize(recompose_date(defaults['expiry_date'], return_str=False))
        adding_tz = pytz.timezone("US/Eastern")
        phrase = adding_tz.localize(parser.parse(formatted_date))
        formatted_date = adding_tz.localize(parser.parse(formatted_date))
    return phrase if db_format else formatted_date


# composing Q statement for normal search queries
def construct_or_search_query(queries):
    if len(queries) == 1:
        return queries[0]  # Base case: return the single query
    # Recursive case: combine the first query with the result of the recursive call
    return Q(queries[0]) | construct_or_search_query(queries[1:])


# alternate search final Q statement will use &'s as operator, so AND operator
def construct_and_search_query(queries):
    if len(queries) == 1:
        return queries[0]
    return Q(queries[0]) & construct_and_search_query(queries[1:])


def vendor_list_current() -> list[dict]:
    file = r"/home/omnivascular/pydb4/pydb/vendors.csv"
    data = pd.read_csv(file)
    vendor_dict = data.to_dict(orient="records")
    print("Vendor ID  -  Vendor Name  -  Vendor Abbreviation")
    for v in vendor_dict:
        print(f"{v['id']}  -  {v['name']}  -  {v['abbrev']}")
    return vendor_dict


# 11/08/2023: change this function below, make it just gather Vendors from df of Current Inventory sheet
# and then take Vendor column as Series, then do a count of nunique, then compare to data in csv and add
# if not already present
def sync_vendors_with_csv(
    csv_file_path=r"/home/omnivascular/pydb4/pydb/vendors.csv",
) -> None:
    # want to ensure every vendor from db is saved to csv
    vendors_db = Vendor.objects.all()
    db_df = pd.DataFrame.from_records(vendors_db.values())
    csv_df = pd.read_csv(csv_file_path)
    # need to compare two df's, ['name'] column (can use df1.equals(df2) for single bool returned)

def update_lifelines():
    src_dir = r'/home/omnivascular/pydb4/pydb/lifelines_to_update/'
    main = pd.DataFrame()
    folders_files = os.listdir(src_dir)
    for file in folders_files:
        file_path = os.path.abspath(src_dir + file)
        df = pd.read_csv(file_path)
        df['birth_date'] = pd.to_datetime(df['birth_date'])
        df['screening_date'] = pd.to_datetime(df['screening_date'])
        main = pd.concat([main, df], axis=0, ignore_index=True)
    main.sort_values(by=['distance'], inplace=True)
    print(main.shape)
    print(main.columns)
    # return main
    for i in main.itertuples():
        patient_qs = Lifeline.objects.filter(name=i.first_name + ' ' + i.last_name, birth_date=i.birth_date, zip_code=i.zip_code)
        if patient_qs.exists():
            patient = patient_qs.first()
            patient.screening_code = i.screening_code
            patient.screening_date = i.screening_date #if not datetime obj, then: datetime.strptime(i.screening_date, "%Y-%m-%d")
            patient.save()
            print(f'saved screening data for: {patient.name}')
        if not patient_qs.exists():
            new_patient = Lifeline(name=i.first_name + ' ' + i.last_name,
                        birth_date=i.birth_date,
                        address=i.address,
                        city = i.city,
                        state = i.state,
                        zip_code= i.zip_code,
                        phone=i.phone,
                        reasons=i.reason_for_call,
                        distance=round(i.distance_away_miles, 2),
                        screening_code=i.screening_code,
                        screening_date=i.screening_date,
                        )
            new_patient.save()
            print(f'Added Patient {i.Index}, dob: {i.birth_date} to the database.')


def populate_lifeline_db(src_file):
    # 03/07/2024: update below last file part of string, with latest revised csv, as needed
    # r"/home/omnivascular/pydb4/pydb/pydb4/sorted_revised_0322pm.csv"
    # src_file = r"/home/omnivascular/pydb4/pydb/pydb4/sorted_revised_0322pm.csv"
    # src_file =
    df = pd.read_csv(src_file)
    df['birth_date'] = pd.to_datetime(df['birth_date'])
    df['screening_date'] = pd.to_datetime(df['screening_date'])
    for i in df.itertuples():
        patient = Lifeline(name=i.first_name + ' ' + i.last_name,
                    birth_date=i.birth_date,
                    address=i.address,
                    city = i.city,
                    state = i.state,
                    zip_code= i.zip_code,
                    phone=i.phone,
                    reasons=i.reason_for_call,
                    distance=round(i.distance_away_miles, 2),
                    screening_code=i.screening_code,
                    screening_date=i.screening_date,
                    )
        # df.loc[i.Index, 'populated'] = True
        # df.at[i.Index, 'populated'] = True # dropped this column
        patient.save()
        print(f'Added Patient {i.Index} to the database.')

def erase_lifeline_responses():
    check = input("Are you sure you wish to reset all Lifeline patient responses?")
    if check.lower() == 'yes':
        Lifeline.objects.all().update(q1_response="")
        Lifeline.objects.all().update(q2_response="")
        Lifeline.objects.all().update(q3_response="")
        Lifeline.objects.all().update(q4_response="")
        Lifeline.objects.all().update(q5_response="")
        Lifeline.objects.all().update(q6_response="")


def add_product_to_sheets(
    vendor: str,
    product_name: str,
    product_size: str,
    expiry_date: str,
    reference_id: str,
    lot_number: str,
    barcode: str,
    quantity: int,
    category="N/A",
) -> None:
    """
    These are parameters needed:

    vendor: str,
    product_name: str,
    product_size: str,
    expiry_date: str,
    reference_id: str,
    lot_number: str,
    barcode: str,
    quantity: int = 1,
    category='N/A')
    """
    # 11/02/2023: need to add functionality, to check for uniqueness vs items already in sheets,
    # one way: download data in pandas dataframe, then find + sort.
    SPREADSHEET_ID = "_blank_"  # spreadsheet_id of main Current Inventory
    RANGE_NAME = "Current Inventory"
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    secret_file = os.path.join(os.getcwd(), "client_secret.json")
    creds = service_account.Credentials.from_service_account_file(
        secret_file, scopes=SCOPES
    )
    service = discovery.build("sheets", "v4", credentials=creds)
    values = [
        [
            category,
            quantity,
            vendor,
            product_name,
            product_size,
            expiry_date,
            reference_id,
            lot_number,
            barcode,
        ]
    ]
    body = {"values": values}
    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME,
            valueInputOption="RAW",
            body=body,
        )
        .execute()
    )


def update_product_in_sheets(
    new_quantity: int, ref_id: str, lot_number: str, expiry_date
) -> None:
    SPREADSHEET_ID = ""  # spreadsheet_id of main Current Inventory
    RANGE_NAME = "Current Inventory"
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    secret_file = os.path.join(os.getcwd(), "client_secret_omni_z.json")
    creds = service_account.Credentials.from_service_account_file(
        secret_file, scopes=SCOPES
    )
    service = discovery.build("sheets", "v4", credentials=creds)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME)
        .execute()
    )
    values = result.get("values", [])
    df = pd.DataFrame(data=values[1:], columns=values[0])
    df.rename(
        columns={
            "Vendor": "vendor",
            "Quantity": "quantity",
            "Product Name": "name",
            "Product Size": "size",
            "expiry_date": "expiry_date",
            "reference_id": "ref_id",
            "Lot_Number": "lot_number",
            "Barcode": "barcode",
            "Last Modified On": "last_modified",
        },
        inplace=True,
    )
    df["expiry_date"] = pd.to_datetime(df["expiry_date"], format="mixed")
    # df["last_modified"] = pd.to_datetime(df["last_modified"], format="mixed")
    expiry_date_object = pd.to_datetime(expiry_date)
    expiry_formatted = recompose_date(phrase=expiry_date_object, return_str=False)
    print("expiry_formatted is here: ", expiry_formatted)
    filtered_df = df[
        (df["ref_id"] == ref_id)
        & (df["lot_number"] == lot_number)
        & (df["expiry_date"] == expiry_formatted)
    ]
    # Iterate through the filtered DataFrame and update the cells in the Google Sheet
    for row in filtered_df.itertuples(index=True):
        row_index = row[0] + 2  # adjusting for 0-based index and header row
        print(row_index)
        # column_name = 'Quantity' # column to be updated
        column_name = (
            "B"  # change this if location of quantity changes in column (A1 notation)
        )
        new_value = new_quantity
        print(row)
        print(new_value, "new val at line 285 views")
        # translate row and column information to Google Sheets range, then update
        # cell_range = f"{column_name}{row_index}"
        cell_range = f"Current Inventory!{column_name}{row_index}"
        # Define the request body to update the cell with new_value
        print("cell range is", cell_range)
        update_body = {"values": [[new_value]]}
        # Perform the update request
        try:
            update_result = (
                service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=cell_range,
                    body=update_body,
                    valueInputOption="RAW",  # Use "RAW" for plain text values
                )
                .execute()
            )
            print("Value successfully updated for item via Sheets API.")
        except Exception as e:
            print(
                "Sheet or column range needs to be verified on the main sheet.", str(e)
            )
            traceback.print_exc()


def po_data_from_api(params: list) -> pd.DataFrame:
    """
    Takes a list of exactly 2 arguments;

    First arg:
        RANGE_NAME_PO_FORM_DATA = "Cleaned Up Responses"
    Second arg:
        Either True for returning CSV file, or False for returning DataFrame.

    Access in CLI (and later functions) via:

    results[results['vendor'] == 'Boston Scientific'].iloc[0].dropna()
    (above returns a Series object, centered on where Vendor matches 'Boston Scientific')
    """
    with thread_lock:
        SPREADSHEET_ID_MAIN = ""
        # RANGE_NAME_ITEMS_ADDED = "New Items for Inventory FORM"
        # RANGE_NAME_ITEMS_USED = "Items Used in Procedure FORM"
        # RANGE_NAME_MAIN_INVENTORY = "Current Inventory"
        RANGE_NAME_PO_FORM_DATA_2 = "Cleaned Up Responses"
        range_name = params[0]
        SPREADSHEET_ID = SPREADSHEET_ID_MAIN
        RANGE_NAME = range_name
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        secret_file = os.path.join(os.getcwd(), "client_secret_omni_z.json")
        creds = service_account.Credentials.from_service_account_file(
            secret_file, scopes=SCOPES
        )
        try:
            service = discovery.build("sheets", "v4", credentials=creds)
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME)
                .execute()
            )
            values = result.get("values", [])
            col_names = [
                "Timestamp",
                "Order Date",
                "VENDOR",
                "ACCOUNT #",
                "Number of items being ordered",
                "Item 1 Description",
                "Item 1 Quantity",
                "Item 2 Description",
                "Item 2 Quantity",
                "Item 3 Description",
                "Item 3 Quantity",
                "Item 4 Description",
                "Item 4 Quantity",
                "Item 5 Description",
                "Item 5 Quantity",
                "Item 6 Description",
                "Item 6 Quantity",
                "Item 7 Description",
                "Item 7 Quantity",
                "Item 8 Description",
                "Item 8 Quantity",
                "Item 9 Description",
                "Item 9 Quantity",
                "Item 10 Description",
                "Item 10 Quantity",
                "Item 11 Description",
                "Item 11 Quantity",
                "Item 12 Description",
                "Item 12 Quantity",
            ]
            df = pd.DataFrame(
                data=values[2:],
                columns=[name.lower().replace(" ", "_") for name in col_names],
            )
            df.rename(
                columns={
                    "account_#": "account_number",
                    "number_of_items_being_ordered": "quantity_items_ordered",
                },
                inplace=True,
            )
            # [df.rename(columns={col_A:col_A.replace(' ', '_')}, inplace=True) for col_A in list(df.columns) if ' ' in col_A]
            if params[1] == True:
                CSV_FILE = f"current-{range_name}-asof-{datetime.now().date().strftime('%m-%d-%Y--%H_%M_%S')}.csv"
                df.to_csv(CSV_FILE)
                return CSV_FILE
            return df
        except HttpError as error:
            print(f"An error occurred: {error}")
            traceback.print_exc()
            return error


def po_data_from_api_2(params: list) -> pd.DataFrame:
    """
    Takes a list of 2 params as arguments; for accessing PO report data.

    First arg, one of the following, whole strings:

        RANGE_NAME_REPORTS = "Reports"
        RANGE_NAME_CLEANED_UP_ITEMS = "Cleaned Up Responses"

    Second arg, either True for returning CSV file, or False for returning DataFrame.
    """
    with thread_lock:
        SPREADSHEET_ID_MAIN = "15HDU1RAOBYa5InSzReHRiohlabBzk-CPyyhMsD9Li3s"
        # RANGE_NAME_ITEMS_ADDED = "New Items for Inventory FORM"
        # RANGE_NAME_ITEMS_USED = "Items Used in Procedure FORM"
        # RANGE_NAME_MAIN_INVENTORY = "Current Inventory"
        RANGE_NAME_PO_FORM_DATA_2 = "Cleaned Up Responses"
        RANGE_NAME_REPORTS = "Reports"
        range_name = params[0]
        SPREADSHEET_ID = SPREADSHEET_ID_MAIN
        RANGE_NAME = range_name
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        secret_file = os.path.join(os.getcwd(), "client_secret_omni_z.json")
        creds = service_account.Credentials.from_service_account_file(
            secret_file, scopes=SCOPES
        )
        try:
            service = discovery.build("sheets", "v4", credentials=creds)
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME)
                .execute()
            )
            values = result.get("values", [])
            col_names = [
                "Order Date",
                "VENDOR",
                "PO #",
                "Item",
                "QHD",
                "QRHD",
                "QPHD",
                "QCD",
                "QRCD",
                "QPCD",
                "TQ",
                "QR",
                "QP",
            ]
            df = pd.DataFrame(
                data=values[2:],
                columns=[name.lower().replace(" ", "_") for name in col_names],
            )
            df.rename(
                columns={
                    "po_#": "po_number",
                    "tq": "qty_ordered",
                    "qr": "qty_received",
                    "qp": "qty_pending",
                },
                inplace=True,
            )
            # [df.rename(columns={col_A:col_A.replace(' ', '_')}, inplace=True) for col_A in list(df.columns) if ' ' in col_A]
            if params[1] == True:
                CSV_FILE = f"current-{range_name}-asof-{datetime.now().date().strftime('%m-%d-%Y--%H_%M_%S')}.csv"
                df.to_csv(CSV_FILE)
                return CSV_FILE
            return df
        except HttpError as error:
            print(f"An error occurred: {error}")
            traceback.print_exc()
            return error


def get_data_from_api(params: list, rename_cols: bool = False) -> pd.DataFrame:
    """
    Takes a list of 3 params as arguments.

    First arg, one of the following, whole strings:

        RANGE_NAME_ITEMS_ADDED = "New Items for Inventory FORM"
        RANGE_NAME_ITEMS_USED = "Items Used in Procedure FORM"
        RANGE_NAME_MAIN_INVENTORY = "Current Inventory"

    Second arg, either True for returning CSV file, or False for returning DataFrame.
    Third arg, optional, for renaming columns, default of False.
    """
    with thread_lock:
        SPREADSHEET_ID_MAIN = "1HwJeDoho1MHS3NJxLdJZgse7YP3A-6C1KIw8YzSX9Eo"
        RANGE_NAME_ITEMS_ADDED = "New Items for Inventory FORM"
        RANGE_NAME_ITEMS_USED = "Items Used in Procedure FORM"
        RANGE_NAME_MAIN_INVENTORY = "Current Inventory"
        range_name = params[0]
        SPREADSHEET_ID = SPREADSHEET_ID_MAIN
        RANGE_NAME = range_name
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        secret_file = os.path.join(os.getcwd(), "client_secret_omni_z.json")
        creds = service_account.Credentials.from_service_account_file(
            secret_file, scopes=SCOPES
        )
        try:
            service = discovery.build("sheets", "v4", credentials=creds)
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME)
                .execute()
            )
            values = result.get("values", [])
            df = pd.DataFrame(data=values[1:], columns=values[0])
            if rename_cols:
                df.rename(
                    columns={
                        "Vendor": "vendor",
                        "Quantity": "quantity",
                        "Product Name": "name",
                        "Product Size": "size",
                        "expiry_date": "expiry_date",
                        "reference_id": "ref_id",
                        "Lot_Number": "lot_number",
                        "Barcode": "barcode",
                        "Last Modified On": "last_modified",
                        },
                    inplace=True,
                )
            if params[1] == True:
                CSV_FILE = f"current-{range_name}-asof-{datetime.now().date().strftime('%m-%d-%Y--%H_%M_%S')}.csv"
                df.to_csv(CSV_FILE)
                return CSV_FILE
            return df
        except HttpError as error:
            print(f"An error occurred: {error}")
            traceback.print_exc()
            return error

def update_db_from_inventory_df(df, user):
    print("Starting update to Database:")
    print("Syncing vendors with CSV file..")
    sync_vendors_with_csv()
    print("Updating from current inventory...")
    for r in df.itertuples():
        now = datetime.now(tz=pytz.timezone("US/Eastern"))
        v = df.iloc[r.Index]['vendor'].replace("Medtronic/ev3", "Medtronic").replace("Covidien", "Medtronic")
        # print(r.Index)
        # print(v)
        # print(type(v))
        try:
            vendor = Vendor.objects.get(name__icontains=v)
        except Vendor.DoesNotExist:
            print('need to verify this Vendor at df index:', r.Index)
            continue
        defaults = {
          "name": df.iloc[r.Index]["name"].strip(),
          "reference_id": df.iloc[r.Index]["ref_id"].strip(),
          "expiry_date": recompose_date(df.iloc[r.Index]["expiry_date"].strip()),
          "lot_number": df.iloc[r.Index]["lot_number"].strip(),
          "size": df.iloc[r.Index]["size"].strip(),
          "barcode": df.iloc[r.Index]["barcode"].strip(),
          "vendor": vendor,
          "quantity_on_hand": int(df.iloc[r.Index]["quantity"].strip()),
        }
        try:
            objs = Product.objects.filter(
                reference_id=defaults["reference_id"],
                lot_number=defaults["lot_number"],
                barcode=defaults["barcode"],
            )
            objs_sorted = [
                o
                for o in objs
                if o.expiry_date.date().strftime("%Y-%m-%d")
                == defaults["expiry_date"]
            ]
            # print(objs_sorted)
            # print([o.expiry_date.date for o in objs_sorted])
            if len(objs_sorted) > 1:
                raise Product.MultipleObjectsReturned
            elif len(objs_sorted) == 0:
                raise Product.DoesNotExist
            obj = objs_sorted[0]
            latest_quant = defaults["quantity_on_hand"]
            if obj.quantity_on_hand != latest_quant:
                obj.quantity_on_hand = latest_quant
                obj.last_modified = now
                obj.save(update_fields=["quantity_on_hand", "last_modified"]) # -----------uncomment when ready to deploy
                print(f"{obj.name} updated quantity in db successfully.")
            continue
        except Product.DoesNotExist:
            new_values = defaults
            obj = Product(**new_values)
            obj.last_modified = now
            # obj.expiry_date = expiry_with_tz.localize(recompose_date(obj.expiry_date, return_str=False))
            obj.expiry_date = recompose_date(obj.expiry_date, return_str=False)
            obj.employee = user
            obj.save() # -----------uncomment when ready to deploy
            print(f"{obj.name} created new in db successfully.")
    print("Database update complete, now based on current inventory.")


# below now groups procedures by mrn number, returns a dict object of mrn's: [procedures]
def sorted_procedures_by_mrn() -> dict:
    procedures = Procedure.objects.all()
    grouped = dict()
    for p in procedures:
        grouped.setdefault(p.patient_mrn, []).append(p)
    return grouped


def sorted_procedures_by_date(start: str, end: str) -> QuerySet:
    start = parser.parse(start)
    end = parser.parse(end)
    procedures = Procedure.objects.filter(date_performed__range=(start, end))
    return procedures


def find_unique_product_names():
    """
    This function does .all() query for Product, then creates listcomp of
    each object's name, converts to numpy array, returns array of unique names.
    """
    products = Product.objects.all()
    prod_names = [p.name for p in products]
    import numpy as np

    prod_names_np = np.array(prod_names)
    return np.unique(prod_names_np)


# class Record():
#     """
# 11/30/2023: unneeded, can remove sometime.
#     Should be passed a delta.changes object, after calling diff_against method
#     as follows:

#     delta = new_value.diff_against(old_value)
#     """

#     def __init__(self, changes):
#         self.field = changes[0].field
#         self.old_value = changes[0].old
#         self.new_value = changes[0].new
#         self.modified_date = changes[
#     def _str__(self):
#         return f"Field is {self.field}, with old val: {self.old_value}, and new val: {self.new_value}."


def sorting_histories(obj) -> list:
    """
    Pass an object with history to this function, it will create list of changes
    in this format: [field, old val, new val, date modified] as a sublist within
    returned list.

    If empty list returned, then means only has 1 historical record, so use
    """
    histories = obj.history.all()
    history_list = []
    if histories.count() > 1:
        for idx, n in enumerate(histories):
            if idx < histories.count() - 1:
                delta = n.diff_against(histories[idx + 1])
                # .date().strftime("%m-%d-%Y") --> can add this to date_modified variable, if str desired
                try:
                    [date_modified] = [
                        change.new for change in delta.changes if "modified" in change.field
                    ]
                except ValueError:
                    date_modified = n.history_date.strftime("%m-%d-%Y, %H%M")
                # [(field, old_value, new_value)]
                for change in delta.changes:
                    if "modified" not in change.field:
                        change_data = [change.field, change.old, change.new, date_modified]
                        history_list.append(change_data)
                # [
                #     history_list.append(change.field, change.old, change.new)
                #     for change in delta.changes
                #     if "modified" not in change.field
                # ]
                # history_list.append([field, old_value, new_value, date_modified])
    return history_list


def create_po_objects_from_sheets_data(user_id) -> None:
    df = po_data_from_api_2(["Reports", False])
    new_po_indices = df[df["item"].isnull()].index.tolist()
    new_pos = [0] + new_po_indices + [len(df)]
    list_of_dfs = [
        df.iloc[new_pos[n] : new_pos[n + 1]] for n in range(len(new_pos) - 1)
    ]
    revised_list_dfs = [df.dropna() for df in list_of_dfs]
    for df_po in revised_list_dfs:
        target_po = df_po.po_number.iloc[0]
        items_sheets = df_po.item.tolist()
        db_po = PurchaseOrder.objects.filter(po_number=target_po).first()
        items_db = db_po.po_items.all()
        items_db_names = [x.name for x in items_db]
        for idx, row in df_po.iterrows():
            if row['item'] not in items_db_names:
                obj = PO_Item.objects.create(name=row['item'], qty_ordered=row['qty_ordered'], qty_received=row['qty_received'])
                db_po.po_items.add(obj)
        # Iterate over each item in the database for the given PurchaseOrder
        for item_db in items_db:
            # Find the corresponding row in the DataFrame based on the item's name
            matching = df_po[df_po['item'] == item_db.name]
            if not matching.empty:
                matching_row = matching.iloc[0]

                # Update the quantity fields of the item in the database
                if item_db.qty_ordered != matching_row['qty_ordered']:
                    item_db.qty_ordered = matching_row['qty_ordered']
                if item_db.qty_received != matching_row['qty_received']:
                    item_db.qty_received = matching_row['qty_received']

                # Save the changes to the item in the database
                item_db.save()
    # 04/17/2024: still need to add logic here, where it checks the qty_pending (which is a calculated value
    # based on qty_received and qty_ordered obj values.
# use this:

    #                 completed_check = all(
    #                     [p.qty_pending == 0 for p in po_obj.po_items.all()]
    #                 )
    #                 partial_check = any(
    #                     [p.qty_pending < p.qty_ordered for p in po_obj.po_items.all()]
    #                 ) and not all([p.qty_pending == 0 for p in po_obj.po_items.all()])
    #                 initial = po_obj.status
    #                 if completed_check:
    #                     po_obj.status = "PO Completed"
    #                 if partial_check:
    #                     po_obj.status = "PO Pending/Partially Received"
    #                 if po_obj.status != initial or item_delta:
    #                     now = datetime.now(tz=pytz.timezone("US/Eastern"))
    #                     po_obj.notes += [f"Modified on: {now}"]
    #                     po_obj.save()
# -------------------------------------
    # for po in revised_list_dfs:
    #     item_delta = False
    #     item_names = po["item"].tolist()
    #     item_qty_ordered = po["qty_ordered"].tolist()
    #     item_qty_received = po["qty_received"].tolist()
    #     item_qty_received = [
    #         n.replace("", "0") for n in item_qty_received if n == ""
    #     ]
    #     # item_qty_pending = po['qty_pending'].tolist()
    #     i_names = item_names.copy()
    #     i_ord = item_qty_ordered.copy()
    #     i_rec = item_qty_received.copy()
    #     items_df = list(zip(i_names, i_ord, i_rec))
    #     # items_df = list(zip(item_names, item_qty_ordered, item_qty_received_revised))
    #     try:
    #         temp_po = PurchaseOrder.objects.get(po_number=po.po_number.tolist()[0])
    #         results = [
    #             (item[0], int(item[1]), int(item[2]))
    #             == (p.name, p.qty_ordered, p.qty_received)
    #             for item, p in zip(items_df, temp_po.po_items.all())
    #             if p.name == item[0]
    #         ]
    #         located_false = [
    #             idx for idx, r in enumerate(results) if r == False
    #         ]  # can capture tuples (r, idx) if needed
    #         if len(located_false) > 0:
    #             print("found this temp_po which has a unmatched quant value:")
    #             print(temp_po, located_false)
    #             # raise ValueError
    #             # break
    #     except PurchaseOrder.DoesNotExist:
    #         pass
    #     r = range(len(items_df))
    #     target_po = po.po_number.tolist()[0]
    #     target_po_date_time = datetime.strptime(
    #         "-".join(target_po.split("-")[1:]), "%m%d%Y-%H%M"
    #     )
    #     if PurchaseOrder.objects.filter(po_number=target_po).exists():
    #         po_obj = PurchaseOrder.objects.get(po_number=target_po)
    #         items_of_po = po_obj.po_items.all()
    #         check = [
    #             (items_df[n][0], int(items_df[n][1]), int(items_df[n][2]))
    #             == (item.name, int(item.qty_ordered), int(item.qty_received))
    #             for n, item in zip(r, items_of_po)
    #             if item.name == items_df[n][0]
    #         ]
    #         if all(check):
    #             print(
    #                 f"All aspects of PO #{po_obj.po_number} checks out, moving on to next."
    #             )
    #             continue
    #         for n, item in zip(r, items_of_po):
    #             if item.name == items_df[n][0].strip():
    #                 attribs = {
    #                     "qty_ordered": items_df[n][1],
    #                     "qty_received": items_df[n][2],
    #                 }
    #                 if all([getattr(item, k) == v for k, v in attribs.items()]):
    #                     print(
    #                         f"PO Item {item.name} from {po_obj.po_number} checks out, moving on to next."
    #                     )
    #                     continue
    #                 else:
    #                     [
    #                         setattr(item, k, v)
    #                         for k, v in attribs.items()
    #                         if getattr(item, k) != v
    #                     ]
    #                     item.save()
    #                     item_delta = True
    #                 completed_check = all(
    #                     [p.qty_pending == 0 for p in po_obj.po_items.all()]
    #                 )
    #                 partial_check = any(
    #                     [p.qty_pending < p.qty_ordered for p in po_obj.po_items.all()]
    #                 ) and not all([p.qty_pending == 0 for p in po_obj.po_items.all()])
    #                 initial = po_obj.status
    #                 if completed_check:
    #                     po_obj.status = "PO Completed"
    #                 if partial_check:
    #                     po_obj.status = "PO Pending/Partially Received"
    #                 if po_obj.status != initial or item_delta:
    #                     now = datetime.now(tz=pytz.timezone("US/Eastern"))
    #                     po_obj.notes += [f"Modified on: {now}"]
    #                     po_obj.save()
    #                     print(f"PO #{po_obj.po_number} updated in db successfully.")
    #         continue
    #     else:
    #         po_item_objs = []
    #         po_number = po["po_number"].iloc[0]
    #         po_date = target_po_date_time
    #         v = po["vendor"].iloc[0] if not 'ev3' in po["vendor"].iloc[0] else 'Medtronic'
    #         vendor = Vendor.objects.get(name__icontains=v)
    #         employee = User.objects.get(pk=user_id)
    #         defaults = {
    #             "po_number": po_number,
    #             "vendor": vendor,
    #             "employee": employee,
    #             "po_date": po_date,
    #         }
    #         for item in items_df:
    #             print(items_df)
    #             print("above is items_df which is a tuple of 3 values, names/ordered/recvd")
    #             qty_recvd_revised = 0 if not items_df[0][2] else int(items_df[0][2])
    #             po_item = PO_Item(
    #                 name=items_df[0][0].strip(),
    #                 qty_ordered=int(items_df[0][1]),
    #                 qty_received=qty_recvd_revised,
    #             )
    #             po_item.save()
    #             po_item_objs.append(po_item)
    #         new_values = defaults
    #         po_obj_new = PurchaseOrder(**new_values)
    #         po_obj_new.save()
    #         po_obj_new.po_items.add(*po_item_objs)
    #         print(f"PO #{po_obj_new.po_number} created new in db successfully.")

        # try:
        #     po_obj = PurchaseOrder.objects.get(po_number=po_number)
        #     item_delta = False
        #     for item in items:
        #         try:
        #             po_item = po_obj.po_items.all().get(name__icontains=item[0])
        #             attribs = {'qty_ordered': item[1], 'qty_received': item[2]}
        #             if all([getattr(po_item, k) == v for k, v in attribs.items()]):
        #                 continue
        #             else:
        #                 [setattr(po_item, k, v) for k, v in attribs.items() if getattr(po_item, k) != v]
        #                 po_item.save()
        #                 item_delta = True
        #                 # po_obj.save()
        #         except PO_Item.DoesNotExist:
        #             print(f"{item[0]} not present in this PO: {po}, skipping.")
        #             raise PO_Item.DoesNotExist
        #     completed_check = all([p.qty_pending == 0 for p in po_obj.po_items.all()])
        #     partial_check = any([p.qty_pending <  p.qty_ordered for p in po_obj.po_items.all()]) and not all([p.qty_pending == 0 for p in po_obj.po_items.all()])
        #     initial = po_obj.status
        #     if completed_check:
        #         po_obj.status = 'PO Completed'
        #     if partial_check:
        #         po_obj.status = 'PO Pending/Partially Received'
        #     if po_obj.status != initial or item_delta:
        #         now = datetime.now(tz=pytz.timezone("US/Eastern"))
        #         po_obj.notes += [f'Modified on: {now}']
        #         po_obj.save()
        # if all([getattr(po_obj, k) == v for k, v in defaults.items()]):
        #     # 11/27/2023: maybe add logic for checking to see if po_obj.po_items.all() match up with items list above, then
        #   continue
        # else:
        #   [setattr(po_obj, k, v) for k, v in defaults.items() if getattr(po_obj, k) != v]
        #   po_obj.save()
        # #   po_obj.po_items.add(*po_item_objs)
        #   print(f"PO #{po_number} updated in db successfully.")
        # except PurchaseOrder.DoesNotExist:
        #     new_values = defaults
        #     po_obj = PurchaseOrder(**new_values)
        #     po_obj.save()
        #     po_obj.po_items.add(*po_item_objs)
        #     print(f"PO #{po_number} created new in db successfully.")


def create_procedure_objects_from_sheets_data() -> None:
    df = get_data_from_api(["Items Used in Procedure FORM", False])
    df_sorted = df.sort_values(by=["MRN-Procedure Name", "Procedure Date"])
    df_grouped_obj = df_sorted.groupby("MRN-Procedure Name")
    CSV_FILE = f"backup-procedures-asof-{datetime.now().date().strftime('%m-%d-%Y--%H_%M_%S')}.csv"
    df_sorted.to_csv(CSV_FILE)
    # now = datetime.now(tz=pytz.timezone("US/Eastern"))
    # expiry_with_tz = pytz.timezone('US/Eastern')
    # dateobj_to_localize = expiry_with_tz.localize(recompose_date(defaults['expiry_date'], return_str=False))
    for group in df_grouped_obj:
        data = df_grouped_obj.get_group(group[0])
        products_used = []
        procedure = data["MRN-Procedure Name"].values[0]
        date_performed = recompose_date(data["Procedure Date"].values[0])
        procedure_extracted = " ".join(procedure.split("-")[1:])
        mrn_extracted = procedure.split("-")[0]
        qr_codes_used = list(data["Barcode"])
        data['Quantity Used'] = pd.to_numeric(data['Quantity Used'], errors='raise')
        multiple_quant_df = data[data['Quantity Used'] > 1]
        quant_plus_qr_codes =  list(zip(data['Quantity Used'].tolist(), data['Barcode'].tolist()))
        # for q in qr_codes_used:
        for q in quant_plus_qr_codes:
            # can be made more flexible here, if barcode needed instead of qr_code, ensure product used exists
            if int(q[0]) > 1:
                for n in range(int(q[0])):
                    products_used.append((Product.objects.filter(qr_code__icontains=q[1]).first()))
            if int(q[0]) == 1:
                products_used.append((Product.objects.filter(qr_code__icontains=q[1]).first()))
        defaults = {
            "procedure": procedure_extracted,
            "patient_mrn": mrn_extracted,
            "date_performed": date_performed,
            "qr_codes_used": qr_codes_used,
        }
        try:
            objs = Procedure.objects.filter(
                procedure=procedure_extracted, patient_mrn=mrn_extracted
            )
            objs_sorted = [
                o
                for o in objs
                if o.date_performed.date().strftime("%Y-%m-%d")
                == defaults["date_performed"]
            ]
            if len(objs_sorted) > 1:
                raise ValueError
            elif len(objs_sorted) == 0:
                raise Procedure.DoesNotExist
            obj = objs_sorted[0]
            continue

            # if all([getattr(obj, k) == v for k, v in defaults.items() if k != 'date_performed']) and obj.date_performed.strftime("%Y-%m-%d") == date_performed:
            #     continue
            # else:
            #     # [setattr(obj, k, v) for k, v in defaults.items() if getattr(obj, k) != v and k != 'date_performed']
            #     # obj.last_modified = now
            #     # obj.save()
            #     # obj.products_used.add(*products_used)
            #     print(defaults)
            #     print(obj.procedure, obj.patient_mrn, obj.date_performed.strftime('%m-%d-%Y'), obj.qr_codes_used)
            #     traceback.print_exc()
            #     raise ValueError
            #     print(f"{procedure} updated in db successfully.")
        except Procedure.DoesNotExist:
            now = datetime.now(tz=pytz.timezone("US/Eastern"))
            new_values = defaults
            obj = Procedure(**new_values)
            obj.notes += [f"Modified on: {now}"]
            if not multiple_quant_df.empty:
                multiple_quant_df.rename(
                    columns={
                        'Quantity Used': 'qty_used',
                        'Barcode': 'barcode',
                        'Status': 'status',
                        'MRN-Procedure Name': 'mrn_procedure_name',
                        'Procedure Date': 'procedure_date',
                        'Timestamp': 'timestamp',
                    },
                    inplace=True,
                )
                obj.notes += [f"Multiples used: "]
                for m in multiple_quant_df.itertuples():
                    p = Product.objects.filter(qr_code__icontains=m.barcode).first()
                    obj.notes += [f"Qty: {m.qty_used} - Name: {p.name} - Product ID: {p.id}"]
            obj.save()
            print(products_used)
            obj.products_used.add(*products_used)
            print(f"{procedure} created new in db successfully.")
            print(str(obj.procedure), str(obj.patient_mrn))


def items_added_30days(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df.rename(
            columns={
                "Quantity Received": "quantity_received",
                "Category": "category",
                "Vendor": "vendor",
                "Product Name": "name",
                "Product Size": "size",
                "expiry_date": "expiry_date",
                "reference_id": "reference_id",
                "Lot_Number": "lot_number",
                "Barcode": "barcode",
                "Timestamp": "date_added",
            },
            inplace=True,
        )
        df["expiry_date"] = pd.to_datetime(df["expiry_date"], format="mixed")
        df["date_added"] = pd.to_datetime(df["date_added"], format="mixed")
        start_date = pd.to_datetime(date.today())
        end_date = pd.to_datetime(start_date - timedelta(days=1 * 30))
        date_condition = (df["date_added"] <= start_date) & (
            df["date_added"] >= end_date
        )
        filtered_df = df[date_condition]
        # filtered_df.sort_values(by="expiry_date", inplace=True)
        filtered_df.sort_values(by="date_added", inplace=True)
        return filtered_df
    except OSError:
        traceback.print_exc()


def items_used_30days(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df.rename(
            columns={
                "Quantity Used": "quantity_used",
                "Vendor": "vendor",
                "Product Name": "name",
                "Product Size": "size",
                # "expiry_date": "expiry_date", # removed expiry_date here, not present as column in sheet
                "reference_id": "ref_id",
                "Lot_Number": "lot_number",
                "Barcode": "barcode",
                "MRN-Procedure Name": "mrn_procedure",
                "Procedure Date": "date_used",
                "Timestamp": "date_inventory_updated",  # this isn't converted to_datetime yet, might need to be later
            },
            inplace=True,
        )
        # df["expiry_date"] = pd.to_datetime(df["expiry_date"], format="mixed")
        df["date_used"] = pd.to_datetime(df["date_used"], format="mixed")
        start_date = pd.to_datetime(date.today())
        end_date = pd.to_datetime(start_date - timedelta(days=1 * 30))
        date_condition = (df["date_used"] <= start_date) & (df["date_used"] >= end_date)
        filtered_df = df[date_condition]
        filtered_df.sort_values(by="date_used", inplace=True)
        return filtered_df
    except OSError:
        traceback.print_exc()


# def update_last_modified_product(product, result) -> None:

#     # print(product.last_modified, result.last_modified)
#     if product.quantity_on_hand != result.quantity_on_hand:
#         result.last_modified = now
#     else:
#         result.last_modified = product.last_modified


# @transaction.atomic
def update_db_from_inventory_csv(file, user):
    print("Starting update to Database:")
    print("Syncing vendors with CSV file..")
    sync_vendors_with_csv()
    print("Updating from current inventory...")


    with thread_lock:
        with open(file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for index, row in enumerate(reader, start=1):
                now = datetime.now(tz=pytz.timezone("US/Eastern"))
                expiry_with_tz = pytz.timezone("US/Eastern")
                # vendor = row["Vendor"].strip() if not any([p for p in ['ev3', 'Covidien'] if p in 'Medtronic/ev3/Covidien']) else 'Medtronic'

                try:
                    v = (
                        row["Vendor"]
                        .strip()
                        .replace("Medtronic/ev3", "Medtronic")
                        .replace("Covidien", "Medtronic")
                    )
                    vendor = Vendor.objects.get(name__icontains=v)
                except Vendor.DoesNotExist:
                    print(v, ": not found in csv to db match.")
                    continue
                # row_number = index
                defaults = {
                    "name": row["Product Name"].strip(),
                    "reference_id": row["reference_id"].strip(),
                    "expiry_date": recompose_date(row["expiry_date"].strip()),
                    "lot_number": row["Lot_Number"].strip(),
                    "size": row["Product Size"].strip(),
                    "barcode": row["Barcode"].strip(),
                    "vendor": vendor,
                    "quantity_on_hand": int(row["Quantity"].strip()),
                }
                try:
                    objs = Product.objects.filter(
                        reference_id=defaults["reference_id"],
                        lot_number=defaults["lot_number"],
                        barcode=defaults["barcode"],
                    )
                    objs_sorted = [
                        o
                        for o in objs
                        if o.expiry_date.date().strftime("%Y-%m-%d")
                        == defaults["expiry_date"]
                    ]
                    # print(objs_sorted)
                    # print([o.expiry_date.date for o in objs_sorted])
                    if len(objs_sorted) > 1:
                        raise Product.MultipleObjectsReturned
                    elif len(objs_sorted) == 0:
                        raise Product.DoesNotExist
                    obj = objs_sorted[0]
                    latest_quant = defaults["quantity_on_hand"]
                    if obj.quantity_on_hand != latest_quant:
                        obj.quantity_on_hand = latest_quant
                        obj.last_modified = now
                        obj.save(update_fields=["quantity_on_hand", "last_modified"])
                    continue

                    # if all([getattr(obj, k) == v for k, v in defaults.items() if k != 'expiry_date']):
                    #     continue
                    # else:
                    #     print([(getattr(obj, k), k, v) for k, v in defaults.items() if k != 'expiry_date'] + [defaults['expiry_date'], recompose_date(obj.expiry_date)])
                    #     print([[getattr(obj, k) == v for k, v in defaults.items() if k != 'expiry_date'] + [defaults['expiry_date'] == recompose_date(obj.expiry_date)]])
                    #     [setattr(obj, k, v) for k, v in defaults.items() if getattr(obj, k) != v and k != 'expiry_date']
                    #     obj.last_modified = now
                    #     # obj.expiry_date = expiry_with_tz.localize(recompose_date(defaults['expiry_date'], return_str=False))
                    #     obj.expiry_date = recompose_date(defaults['expiry_date'], return_str=False)
                    #     obj.employee = user
                    #     obj.save()
                    #     print(f"{obj.name} updated in db successfully.")
                except Product.DoesNotExist:
                    new_values = defaults
                    obj = Product(**new_values)
                    obj.last_modified = now
                    # obj.expiry_date = expiry_with_tz.localize(recompose_date(obj.expiry_date, return_str=False))
                    obj.expiry_date = recompose_date(obj.expiry_date, return_str=False)
                    obj.employee = user
                    obj.save()
                    print(f"{obj.name} created new in db successfully.")
        print("Database update complete, now based on current inventory.")
