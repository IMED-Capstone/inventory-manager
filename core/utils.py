import datetime
import pandas as pd

# Adapted from https://stackoverflow.com/a/48457168
def trunc_datetime(date:datetime.datetime):
    return date.replace(hour=0, minute=0, second=0, microsecond=0)

def dict_from_excel_row(row: pd.Series) -> dict:
    data = {}
    try:
        if "ITEM" in row:
            data["item"] = row["ITEM"]
        if "MFR" in row:
            data["mfr"] = row["MFR"]
        if "MFR CAT" in row:
            data["mfr_cat"] = row["MFR CAT"]
        if "VENDOR" in row:
            data["vendor"] = row["VENDOR"]
        if "VEND CAT" in row:
            data["vend_cat"] = row["VEND CAT"]
        if "DESCR" in row:
            data["descr"] = row["DESCR"]
        if "RECV QTY" in row:
            data["recv_qty"] = row["RECV QTY"]
        if "UM" in row:
            data["um"] = row["UM"]
        if "PRICE" in row:
            data["price"] = row["PRICE"]
        if "TOTAL COST" in row:
            data["total_cost"] = row["TOTAL COST"]
        if "Expr1010" in row:
            data["expr1010"] = row["Expr1010"]
        if "PO_NO" in row:
            data["po_no"] = row["PO_NO"]
        if "PO_DATE" in row:
            data["po_date"] = row["PO_DATE"].tz_localize(tz="America/Chicago").tz_convert("UTC")
        if "VEND_CODE" in row:
            data["vend_code"] = row["VEND_CODE"]
        if "ITEM_NO" in row:
            data["item_no"] = row["ITEM_NO"]
        if "dbo_VEND.NAME" in row:
            data["dbo_vend_name"] = row["dbo_VEND.NAME"]
    except KeyError as e:
        raise Exception("Missing required field value") from e
    
    if "dbo_CC.NAME" in row:
        data["dbo_cc_name"] = row["dbo_CC.NAME"]
    elif "Expr1016" in row:
        data["dbo_cc_name"] = row["Expr1016"]
    else:
        raise KeyError("Key either \"dbo_CC.NAME\" or \"Expr1016\" required.")
    
    if "ACCT_NO" in row:
        data["acct_no"] = row["ACCT_NO"]
    elif "Expr1017" in row:
        data["acct_no"] = row["Expr1017"]
    else:
        raise KeyError("Key either \"ACCT_NO\" or \"Expr1017\" required.")
    
    if "RCV_DATE" in row:   # should otherwise automatically put null here on object creation if not exists
        data["rcv_date"] = row["RCV_DATE"].tz_localize(tz="America/Chicago").tz_convert("UTC")
    
    return data
    

    

    
