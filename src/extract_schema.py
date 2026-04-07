import os
import psycopg2
import pandas as pd
import warnings

warnings.filterwarnings('ignore')  # Ignore pandas read_sql warning about only checking 10 rows

def load_env(filepath):
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

print("Loading environment variables...")
load_env('.env')

print("Connecting to the database...")
try:
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )
    print("Successfully connected to the database.")
    
    query = """
    SELECT 
        c.table_name AS "테이블명",
        obj_description(pc.oid) AS "테이블 설명",
        c.column_name AS "컬럼명",
        col_description(pc.oid, c.ordinal_position) AS "컬럼 설명",
        c.data_type AS "데이터 타입",
        COALESCE(c.character_maximum_length::text, c.numeric_precision::text, '') AS "길이/정밀도",
        c.is_nullable AS "Null 허용",
        c.column_default AS "기본값"
    FROM information_schema.columns c
    JOIN pg_class pc ON pc.relname = c.table_name
    JOIN pg_namespace pn ON pn.oid = pc.relnamespace AND pn.nspname = c.table_schema
    WHERE c.table_schema = 'visual'
    ORDER BY c.table_name, c.ordinal_position;
    """
    
    print("Executing query to extract schema definitions...")
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        print("No tables found in the 'visual' schema.")
    else:
        output_file = 'visual_schema_definition.xlsx'
        print(f"Exporting {len(df)} rows to {output_file}...")
        df.to_excel(output_file, index=False)
        print(f"Extraction complete! Saved to {output_file}")
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if 'conn' in locals():
        conn.close()
        print("Database connection closed.")
