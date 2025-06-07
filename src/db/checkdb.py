import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError  # Import specific exceptions
from dotenv import load_dotenv

def verify_database_connection():
    """
    Attempts to connect to the database specified by the DATABASE_URL
    environment variable and optionally runs a simple query.
    """
    print("--- Database Connection Verification ---")

    # 1. Load Environment Variables
    print("Loading environment variables from .env file...")
    load_dotenv()  # Load variables from .env file if it exists
    db_url = "postgresql://postgres:1234@localhost:5432/resumeapp"

    # 2. Check if DATABASE_URL is set
    if not db_url:
        print("\nERROR: DATABASE_URL environment variable not found.")
        print("Please ensure it's set in your .env file or system environment.")
        # sys.exit(1) # Optional: exit if URL is missing
        return False # Indicate failure

    # Mask credentials for printing - simple masking
    masked_url = db_url
    if "@" in db_url:
        parts = db_url.split('@')
        credentials_part = parts[0].split('://')[-1]
        if ':' in credentials_part: # user:password format
             masked_url = db_url.replace(credentials_part.split(':')[1], "****")

    print(f"Using Database URL: {masked_url}")

    # 3. Attempt to Create Engine and Connect
    engine = None
    try:
        print("\nAttempting to create SQLAlchemy engine...")
        # Using pool_size=0 avoids creating a connection pool just for this test
        engine = create_engine(db_url, pool_size=0, echo=False) # Set echo=True for detailed SQL logs

        print("Attempting to establish connection...")
        # The 'with' statement ensures the connection is closed automatically
        with engine.connect() as connection:
            print("Connection successful!")

            # Optional: Try executing a simple query to ensure readiness
            try:
                print("Attempting a simple query (e.g., SELECT 1)...")
                # Use text() for executing raw SQL compatible with most DBs
                result = connection.execute(text("SELECT 1"))
                scalar_result = result.scalar() # Try to get the result
                print(f"Simple query successful! (Result: {scalar_result})")
            except (OperationalError, SQLAlchemyError) as query_e:
                print(f"\nWARNING: Connection worked, but a simple query failed.")
                print(f"Query Error: {query_e}")
                print("This might indicate issues with permissions, database state, or query syntax.")
            except Exception as query_e_unexp:
                print(f"\nWARNING: An unexpected error occurred during the test query.")
                print(f"Unexpected Query Error: {query_e_unexp}")


        print("\nVerification finished successfully.")
        return True # Indicate success

    except ImportError as import_e:
        # Specific check for missing drivers
        print(f"\nERROR: Missing database driver.")
        print(f"Details: {import_e}")
        if 'psycopg2' in str(import_e).lower() and db_url.startswith('postgresql'):
            print("Suggestion: Run 'pip install psycopg2-binary'")
        elif 'sqlite' in str(import_e).lower() and db_url.startswith('sqlite'):
             print("SQLite should be built-in, check Python installation or SQLAlchemy version.")
        # Add suggestions for other drivers if needed
        return False

    except OperationalError as op_e:
        # Common connection errors (wrong host, port, DB name, server down, firewall)
        print(f"\nERROR: Could not connect to the database (OperationalError).")
        print(f"Details: {op_e}")
        print("Check: Database server running? Correct host/port? Firewall rules? Database exists?")
        return False

    except SQLAlchemyError as e:
        # Other SQLAlchemy errors (authentication, URL format)
        print(f"\nERROR: An SQLAlchemy error occurred during connection.")
        print(f"Details: {e}")
        print("Check: Correct username/password? Correct database name? URL format?")
        return False

    except Exception as e:
        # Catch any other unexpected errors during the process
         print(f"\nERROR: An unexpected error occurred.")
         print(f"Details: {e}")
         return False

    finally:
        # Dispose of the engine to explicitly close any pooled connections (though pool_size=0 helps)
        if engine:
            engine.dispose()
            print("Engine disposed.")


if __name__ == "__main__":
    if verify_database_connection():
        print("\nDatabase connection appears to be working.")
        sys.exit(0) # Exit with success status
    else:
        print("\nDatabase connection verification failed.")
        sys.exit(1) # Exit with error status