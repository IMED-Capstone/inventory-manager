# Inventory Manager
Django application for managing inventory in the UIC IR department.

## Getting Started
* Clone repository

    ```
    git clone https://github.com/IMED-Capstone/inventory-manager.git
    ```
* Create virtual environment and install requirements

    ```
    cd inventory-manager
    python3 -m venv ./venv
    python3 -m pip install -r requirements.txt
    ```
* Run project
    * if using VSCode, just hit debug
    * otherwise:
        ```
        python3 manage.py runserver
        ```


## Current structure
- Core Application
    - Holds the logs for each transaction made for an item (a transaction ledger).
    - Information stored in a DB, where each transaction is logged as a separate record (row).
    - unique ID in the DB is for the specific transaction
    - views for orders and graphs
        - basic list view available at `127.0.0.1:8000/dates/<start_date>/<end_date>/`
- Inventory (name TBD)
    - maintains par levels for each unique item inventory should be maintained for
    - provide alerts for when levels are approaching par level or fall under par level
    - unique ID would be for the item number rather than the transaction
    - view for inventory levels over time (and graphs for utilization)
