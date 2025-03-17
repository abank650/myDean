import json

def clear_users():
    # Reset users.json to empty users dictionary
    empty_users = {
        "users": {}
    }
    
    # Write the empty users dictionary to users.json
    with open('./users.json', 'w') as f:
        json.dump(empty_users, f, indent=4)

if __name__ == "__main__":
    print("Clearing users.json...")
    clear_users()
    print("Users cleared successfully. Profiles in data/profiles/ are preserved.") 