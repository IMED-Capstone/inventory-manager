import pandas as pd
import matplotlib.pyplot as plt
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

#there are receving quantityes as - and their associated sum is in () so does that mean that they are returns?
#there are a few items from the year 2022-2023, since we are getting this based on the PO_DATE, should we remove those?



# Read the Excel file
df = pd.read_excel('/Users/adrianaene/Desktop/UICOM/IMED/inventory-manager/stats/data/RAD_NEURO_ANGIOGRAPHY.xlsx')


def get_basic_stats(column):
    cl = df[column].unique()
    cl_value = df[column].value_counts()
    return cl, cl_value


def get_all_unique_values(column):
    """
    Retrieve the count of unique values and the list of unique values from a specified column.
    """
    unique_values = df[column].unique()
    return len(unique_values), unique_values


def monthly_orders(df):
    # Ensure PO_DATE is in datetime format
    df['PO_DATE'] = pd.to_datetime(df['PO_DATE'])
    
    # Group by month and calculate stats for TOTAL COST and DESCR
    monthly_stats = df.groupby(df['PO_DATE'].dt.to_period('M')).agg({
        'TOTAL COST': 'sum',
        'DESCR': 'count'
    }).rename(columns={'DESCR': 'ORDER_COUNT'})
    
    return monthly_stats


def item_monthly_stats(df,item_column, cost_column, date_column):
    """
    Calculate the total cost of an item per month and the number of times the same item was ordered.
    """
    # Ensure the date column is in datetime format
    df[date_column] = pd.to_datetime(df[date_column])
    
    df[date_column] = pd.to_datetime(df[date_column])

    # Extract month-period
    df['Month'] = df[date_column].dt.to_period('M')

    # Group by item and month, calculate total cost and count
    stats = df.groupby([item_column, 'Month']).agg(
        TOTAL_COST=(cost_column, 'sum'),
        ORDER_COUNT=(item_column, 'count')
    ).reset_index()

    return stats

monthly_orders = monthly_orders(df)
monthly_stats = item_monthly_stats(df,'DESCR', 'TOTAL COST', 'PO_DATE')
print(monthly_stats)

def clean_data(df):
    """
    Clean the DataFrame by removing rows with NaN values and duplicates.
    """
    # Remove rows with NaN values
    missing_values = df.isnull().sum()
    df = df.dropna()
    duplicates = df.duplicated().sum()
    # Remove duplicates
    df = df.drop_duplicates()
    print(f"Missing values: {missing_values}")
    #TODO if there are missing values, should we remove them or fill them with 0? No duplicates were found in either dataset which makes sense
    return df


def mfr_cat_info(df):
   # Returns a DataFrame pivoted with each MFR_CAT in a unique row, months formatted as MM/YYYY:

    # Ensure PO_DATE is datetime and formatted correctly
    df['PO_DATE'] = pd.to_datetime(df['PO_DATE'])
    df['Month-Year'] = df['PO_DATE'].dt.strftime('%m/%Y')

    # Sort months chronologically
    sorted_months = sorted(df['Month-Year'].unique(), key=lambda x: pd.to_datetime(x, format='%m/%Y'))

    # Pivot QTY_RECEIVED per month (allows negatives)
    qty_pivot = df.pivot_table(
        index='MFR CAT',
        columns='Month-Year',
        values='RECV QTY',
        aggfunc='sum',
        fill_value=0
    ).reindex(columns=sorted_months, fill_value=0)

    # Rename columns explicitly
    qty_pivot.columns = [month for month in qty_pivot.columns]

    # Cost per month pivot
    cost_pivot = df.pivot_table(
        index='MFR CAT',
        columns='Month-Year',
        values='TOTAL COST',
        aggfunc='sum',
        fill_value=0).reindex(columns=sorted_months, fill_value=0)

    cost_pivot.columns = [f'Cost_{month}' for month in cost_pivot.columns]
    yearly_totals = df.groupby('MFR CAT').agg(
        TOTAL_QTY_RECEIVED_PER_YEAR=('RECV QTY', 'sum'),
        TOTAL_COST_PER_YEAR=('TOTAL COST', 'sum'))
    avg_qty_per_month = qty_pivot.mean(axis=1).rename('AVG_QTY_RECEIVED_PER_MONTH')
    avg_cost_per_month = cost_pivot.mean(axis=1).rename('AVG_COST_PER_MONTH')
    summary_df = pd.concat(
        [qty_pivot, cost_pivot, avg_qty_per_month, avg_cost_per_month, yearly_totals],
        axis=1
    ).reset_index()

    # Final ordering of columns
    final_columns = (
        ['MFR CAT'] +
        list(qty_pivot.columns) +
        list(cost_pivot.columns) +
        ['AVG_QTY_RECEIVED_PER_MONTH', 'AVG_COST_PER_MONTH', 
         'TOTAL_QTY_RECEIVED_PER_YEAR', 'TOTAL_COST_PER_YEAR']
    )

    summary_df = summary_df[final_columns]

    return summary_df



mfr_cat = mfr_cat_info(df)
#mfr_cat.to_csv('/Users/adrianaene/Desktop/UICOM/IMED/inventory-manager/stats/data/mfr_cat.csv', index=False)
#x, y graph



##this is the database that we should add on the website to be able to search each item's cost and quantity by month or total.

def order_forecasting(df,date):
    df['PO_DATE'] = pd.to_datetime(df['PO_DATE'])
    df['Month'] = df['PO_DATE'].dt.to_period('M').dt.to_timestamp()
    monthly_orders = df.groupby(['Month', 'MFR CAT']).agg({'RECV QTY': 'sum', 'TOTAL COST': 'sum'}).reset_index()
    print(monthly_orders)
    #insert lag features to predict time forecasting values, we are going to include
    #the prvious months
    #cyclic yearly pattern
    #3 month cyclic pattern for seasonal items?
    #TODO ask for more than one year for a better understanding of the broad of the program
    #need this due to the fact that I plan on using linear regression programs (XBOOST (can deal with nonbinary values) and linear regression or Random Forest)
    monthly_orders['Month_num'] = monthly_orders['Month'].dt.month
    monthly_orders['Year'] = monthly_orders['Month'].dt.year
    # Lag features
    monthly_orders['Lag_1'] = monthly_orders.groupby('MFR CAT')['QTY_RECEIVED'].shift(1)
    monthly_orders['Lag_2'] = monthly_orders.groupby('MFR CAT')['QTY_RECEIVED'].shift(2)
    # Rolling average
    monthly_orders['Rolling_mean_3'] = monthly_orders.groupby('MFR CAT')['QTY_RECEIVED'].shift(1).rolling(window=3).mean()
    # Drop NaNs due to lagging
    monthly_orders.dropna(inplace=True)
    train = monthly_orders[monthly_orders['Month'] < date]
    test = monthly_orders[monthly_orders['Month'] >= date]
    return train,test


train,test = (order_forecasting(df), '05-01-2024',)

features = ['Month_num', 'Year', 'Lag_1', 'Lag_2', 'Rolling_mean_3']
X_train = train[features]
y_train = train['RECV QTY']

X_test = test[features]
y_test = test['RECV QTY']


model = XGBRegressor(n_estimators=200, learning_rate=0.1)
model.fit(X_train, y_train)

# Predictions
predictions = model.predict(X_test)

# Evaluate model
mae = mean_absolute_error(y_test, predictions)
rmse = np.sqrt(mean_squared_error(y_test, predictions))
print(f'Mean Absolute Error: {mae}')
print(f'Root Mean Squared Error: {rmse}')

