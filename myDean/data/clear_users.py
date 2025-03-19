import json
import os
import sys

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import file_utils as fu

def clear_users():
    # Reset users.json to empty users dictionary
    empty_users = {
        "users": {}
    }
    
    # Write the empty users dictionary to users.json
    fu.save_json('./users.json', empty_users)

if __name__ == "__main__":
    print("Clearing users.json...")
    clear_users()
    print("Users cleared successfully. Profiles in data/profiles/ are preserved.") 
