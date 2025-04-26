import datetime

# Adapted from https://stackoverflow.com/a/48457168
def trunc_datetime(date:datetime.datetime):
    return date.replace(hour=0, minute=0, second=0, microsecond=0)