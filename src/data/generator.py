import sqlite3
import random
from datetime import datetime, timedelta
import uuid

def generate_data(db_path: str = "risk.db", num_trades: int = 1000, num_days: int = 7):
    """Generates mock trading and risk data for the dashboard."""
    print(f"Generating mock data in {db_path}...")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # 1. Trades table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY,
            desk TEXT,
            trader_name TEXT,
            asset_class TEXT,
            instrument TEXT,
            quantity REAL,
            price REAL,
            notional REAL,
            trade_date DATE
        )
        ''')

        # 2. Risk Metrics table (PnL, Greeks, etc.)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_metrics (
            trade_id TEXT,
            calc_date DATE,
            pnl REAL,
            dv01 REAL,
            delta REAL,
            gamma REAL,
            vega REAL,
            FOREIGN KEY(trade_id) REFERENCES trades(trade_id)
        )
        ''')

        # Clear existing data for fresh simulation
        cursor.execute('DELETE FROM risk_metrics')
        cursor.execute('DELETE FROM trades')

        desks = ['FX Spot', 'Rates', 'Options', 'Credit']
        traders = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve']

        asset_classes = {
            'FX Spot': ['FX'],
            'Rates': ['Bonds', 'Swaps'],
            'Options': ['Equity Options', 'FX Options'],
            'Credit': ['Corp Bonds', 'CDS']
        }

        instruments = {
            'FX': ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD'],
            'Bonds': ['US T-Bill 1Y', 'US T-Note 10Y'],
            'Swaps': ['IRS 5Y', 'IRS 10Y'],
            'Equity Options': ['AAPL Call', 'TSLA Put'],
            'FX Options': ['EUR/USD Call', 'GBP/USD Put'],
            'Corp Bonds': ['AAPL 2030', 'MSFT 2028'],
            'CDS': ['CDX IG', 'CDX HY']
        }

        start_date = datetime.now() - timedelta(days=num_days)

        # Generate trades
        for _ in range(num_trades):
            trade_id = str(uuid.uuid4())
            desk = random.choice(desks)
            trader = random.choice(traders)
            asset_class = random.choice(asset_classes[desk])
            instrument = random.choice(instruments[asset_class])

            quantity = round(random.uniform(10, 1000), 2)
            price = round(random.uniform(10, 200), 2)
            notional = round(quantity * price, 2)

            # Random date within the last num_days
            random_days_ago = random.randint(0, num_days - 1)
            trade_date = (start_date + timedelta(days=random_days_ago)).strftime('%Y-%m-%d')

            cursor.execute('''
                INSERT INTO trades (trade_id, desk, trader_name, asset_class, instrument, quantity, price, notional, trade_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (trade_id, desk, trader, asset_class, instrument, quantity, price, notional, trade_date))

            # Generate Risk metrics for the trade (for simplification, daily metrics for the trade date to current date)
            # A real system would have daily snapshots

            pnl = round(random.uniform(-5000, 10000), 2)

            # Specific risk metrics based on desk
            dv01 = round(random.uniform(-1000, 1000), 2) if desk in ['Rates', 'Credit'] else 0.0
            delta = round(random.uniform(-100, 100), 2) if desk == 'Options' else 0.0
            gamma = round(random.uniform(0, 50), 2) if desk == 'Options' else 0.0
            vega = round(random.uniform(0, 100), 2) if desk == 'Options' else 0.0

            cursor.execute('''
                INSERT INTO risk_metrics (trade_id, calc_date, pnl, dv01, delta, gamma, vega)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (trade_id, trade_date, pnl, dv01, delta, gamma, vega))

        conn.commit()
    print("Data generation complete.")

if __name__ == "__main__":
    generate_data()
