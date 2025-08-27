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
            docker compose up -d --build
            ```
            * The `-d` flag runs in detached mode in the background. To see output on the terminal, simply remove `-d` from the `up` command.
            * If running an existing image, can run without the `build` flag:
                ```
                docker compose up -d
                ```
        
        * To optionally build container with Sphinx documentation, refer to the [Documentation](#documentation) section below.
    
* Navigate in browser to `127.0.0.1:8000`
    * For the rest of this documentation, `<base-url>` will be used. If running locally, this will be the same as `127.0.0.1` or `localhost`, but serves to be more clear for other environments where this may be different.

### Adding Data from Excel File
* Navigate to the admin panel at ```<base-url>:8000/admin```
* Log in with admin credentials set at the ```createsuperuser``` step
* Click on `Core/Orders`, then click the `Import Data` button in the top right
* Follow the prompt to upload the file, then navigating to the `Core/Orders` page should show populated data


## Current structure
- Core Application
    - Holds the logs for each transaction made for an order (a transaction ledger).
    - Information stored in a DB, where each transaction is logged as a separate record (row).
    - unique ID in the DB is for the specific transaction
    - views for items/orders and graphs
        - basic list view available at `<base-url>:8000/orders/`
        - graph views available at `<base-url>:8000/orders_advanced/`
        - list view of item transactions available at `<base-url>:8000/item-transactions/`
    - inventory for a specific item can be updated at
        - `<base-url>:8000/manage_inventory/`
    - various settings and information are available at
        - `<base-url>:8000/settings/` (general application and deployment settings)
        - `<base-url>:8000/profile/` (will support updating profile settings)
        - `<base-url>:8000/about/` (information about the application)

## Documentation
Sphinx documentation has been set up for Inventory Manager. To generate:
* Directly on PC
    * Enter the `docs` folder
        ```
        cd docs/
        ```
    
    * Generate HTML documentation
        ```
        make html
        ```
    
        * **Note**: if on Windows (and using Powershell), be sure to include the extension (`.\make.bat html`)
    
    * Navigate to the output folder
        ```
        cd _build/html
        ```
    
    * Open the main page at `index.html`.

* In Docker
    * To build documentation as well as the main Inventory Manager, use the `docs` profile on the `compose` command:
        ```
        docker compose --profile docs up --build
        ```
    
    * Navigate to `<base-url>:8010`

## Project Roadmap
- maintains par levels for each unique item inventory should be maintained for
- provide alerts for when levels are approaching par level or fall under par level
- unique ID would be for the item number rather than the transaction
- view for inventory levels over time (and graphs for utilization)
