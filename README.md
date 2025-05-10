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

* Create `data` folder in project root if it does not exist. This is where the DB will be stored and the volume used by the Docker container

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
    * Bare-metal (directly on PC)
        * if using VSCode, just hit debug
        * otherwise:
            ```
            python manage.py runserver
            ```
    * Docker
        * Ensure Docker and docker compose are installed (note: Windows requires installation of Docker Desktop, which includes Docker engine and docker compose)
        * Build and run the docker container. Navigate to the root level directory of the project and enter the following commands:
            ```
            docker build
            docker compose up -d
            ```
            * The `-d` flag runs in detached mode in the background. To see output on the terminal, simply remove `-d` from the `up` command.
    
* Navigate in browser to `127.0.0.1:8000`

### Adding Data from Excel File
* Navigate to the admin panel at ```127.0.0.1:8000/admin```
* Log in with admin credentials set at the ```createsuperuser``` step
* Click on `Core/Orders`, then click the `Import Data` button in the top right
* Follow the prompt to upload the file, then navigating to the `Core/Orders` page should show populated data


## Current structure
- Core Application
    - Holds the logs for each transaction made for an order (a transaction ledger).
    - Information stored in a DB, where each transaction is logged as a separate record (row).
    - unique ID in the DB is for the specific transaction
    - views for orders and graphs
        - basic list view available at `127.0.0.1:8000/dates/<start_date>/<end_date>/`
- Inventory (name TBD)
    - maintains par levels for each unique item inventory should be maintained for
    - provide alerts for when levels are approaching par level or fall under par level
    - unique ID would be for the item number rather than the transaction
    - view for inventory levels over time (and graphs for utilization)
