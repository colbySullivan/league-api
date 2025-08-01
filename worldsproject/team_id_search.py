import requests
import os
from datetime import datetime
import json

# --- Configuration ---
# Your PandaScore API key should be set as an environment variable.
API_KEY = os.getenv("PANDASCORE_API_KEY")

if not API_KEY:
    print("Error: PANDASCORE_API_KEY environment variable is not set.")
    print("Please set your PandaScore API key before running the script.")
    exit()

BASE_URL = "https://api.pandascore.co/lol"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

def search_entity(entity_type, name):
    """
    Searches for an entity by name and returns a list of potential matches.
    """
    endpoint = f"/{entity_type}"
    params = {
        "search[name]": name,
        "per_page": 10
    }
    
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error searching for {entity_type} '{name}': {e}")
        return None

def select_entity(entity_type, name_input, options):
    """
    Guides the user to select the correct entity from a list of options.
    """
    if not options:
        print(f"No {entity_type} found matching '{name_input}'. Please try a different name.")
        return None, None
        
    print(f"\nFound {len(options)} {entity_type}s that are similar to '{name_input}'.")
    print("Please select the correct one from the list:")
    for i, entity in enumerate(options, 1):
        print(f"  {i}. {entity['name']} (ID: {entity['id']})")
        
    while True:
        try:
            choice = int(input(f"Enter your choice (1-{len(options)}): "))
            if 1 <= choice <= len(options):
                selected_entity = options[choice - 1]
                return selected_entity['id'], selected_entity['name']
            else:
                print("Invalid choice. Please enter a number within the range.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def add_teams_to_json():
    """
    Prompts the user for team names, searches for their IDs, and saves them
    to a teams.json file.
    """
    file_path = "teams.json"
    teams_data = {}

    # Load existing teams if the file exists
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                teams_data = json.load(f)
                print(f"Successfully loaded existing teams from '{file_path}'.")
            except json.JSONDecodeError:
                print(f"Warning: '{file_path}' is corrupted or empty. Starting with a new file.")

    while True:
        team_name_input = input("\nEnter a team name to add (e.g., T1, Gen.G) or type 'done' to finish: ")
        if team_name_input.lower() == 'done':
            break

        # Check for duplicates before making a new API call
        if any(team['name'].lower() == team_name_input.lower() for team in teams_data.values()):
            print(f"'{team_name_input}' is already in teams.json.")
            continue

        team_options = search_entity("teams", team_name_input)
        if team_options:
            team_id, team_name = select_entity("team", team_name_input, team_options)
            if team_id:
                teams_data[team_name] = {"id": team_id, "name": team_name}
                print(f"\nAdded {team_name} (ID: {team_id}) to teams.json.")
        else:
            # This branch is executed if team_options is None or empty.
            # The select_entity function already handles the "No team found" message
            # so we can just continue the loop here.
            pass

    # Write the updated teams to the file
    with open(file_path, 'w') as f:
        json.dump(teams_data, f, indent=4)
    print(f"\nFinal team list saved to '{file_path}'.")

if __name__ == "__main__":
    add_teams_to_json()