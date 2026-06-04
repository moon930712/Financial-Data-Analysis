import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    try:
                        k, v = line.split('=', 1)
                        os.environ[k.strip()] = v.strip()
                    except: pass

load_env()

def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def analyze_trend():
    conn = get_connection()
    # Get daily average price to see 2024 trend
    query = """
    SELECT date, AVG(close) as avg_price 
    FROM visual.vsl_anly_stocks_price_subindex01 
    WHERE date >= '2024-01-01' AND date <= '2025-12-31'
    GROUP BY date 
    ORDER BY date
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    df['date'] = pd.to_datetime(df['date'])
    print(df.head(20))
    print(df.tail(20))
    
    # Simple calculation to find sideways periods
    # (Checking volatility and trend)
    return df

if __name__ == "__main__":
    analyze_trend()
