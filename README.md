# Inventory Manager
Django application for managing inventory in the UIC IR department.

## Getting Started
* Clone repository

    ```
    git clone https://github.com/IMED-Capstone/inventory-manager.git
    ```
* Create and activate virtual environment

    ```
    cd inventory-manager
    python -m venv ./venv
    ```

    * Windows (PowerShell)
        ```
        .\venv\Scripts\Activate.ps1
        ```
    * MacOS/Linux
        ```
        source ./venv/bin/activate
        ```
    
* Install requirements
    ```
    python -m pip install -r requirements.txt
    ```

* Run DB migrations
    ```
    python manage.py migrate
    ```

* Create Django superuser
    ```
    python manage.py createsuperuser
    ```
    * follow the prompts to set admin user username and password

* Run project
    * if using VSCode, just hit debug
    * otherwise:
        ```
        python manage.py runserver
        ```
    
* Navigate in browser to `127.0.0.1:8000`

### Adding Data from Excel File
* Navigate to the admin panel at ```127.0.0.1:8000/admin```
* Log in with admin credentials set at the ```createsuperuser``` step
* Click on `Core/Items`, then click the `Import Data` button in the top right
* Follow the prompt to upload the file, then navigating to the `Core/Items` page should show populated data


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
