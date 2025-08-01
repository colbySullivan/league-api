import requests
import json
import os

def get_teams_from_region(api_key, game_slug, region_name):
    """
    Fetches teams for a specific game and region from the PandaScore API
    by finding tournaments within the league and then getting teams from those tournaments.
    
    Args:
        api_key (str): Your PandaScore API key.
        game_slug (str): The slug of the video game (e.g., 'lol', 'cs-go').
        region_name (str): The name of the region/league to search for (e.g., 'lcs').
    """
    if not api_key:
        print("Error: API key not found. Please set the PANDASCORE_API_KEY environment variable.")
        return
        
    base_url = f'https://api.pandascore.co'
    game_url = f'{base_url}/{game_slug}'
    headers = {'Authorization': f'Bearer {api_key}'}

    # Step 1: Find the league for the specified region
    leagues_url = f'{game_url}/leagues'
    leagues_params = {'filter[slug]': region_name}
    
    try:
        leagues_response = requests.get(leagues_url, headers=headers, params=leagues_params)
        leagues_response.raise_for_status()
        leagues = leagues_response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching league for region {region_name}: {e}")
        return

    if not leagues:
        print(f"No league found for region: {region_name}")
        return

    league_id = leagues[0]['id']
    league_name = leagues[0]['name']
    print(f"Found league '{league_name}' with ID: {league_id}")

    # Step 2: Get all tournaments for that league
    tournaments_url = f'{leagues_url}/{league_id}/tournaments'
    print(f"Fetching tournaments for '{league_name}'...")

    try:
        tournaments_response = requests.get(tournaments_url, headers=headers)
        tournaments_response.raise_for_status()
        tournaments = tournaments_response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching tournaments for {league_name}: {e}")
        return

    if not tournaments:
        print(f"No tournaments found for league '{league_name}'.")
        return

    all_teams = {}
    print(f"Found {len(tournaments)} tournaments. Now fetching teams...")

    # Step 3: Get teams for each tournament and combine them
    for tournament in tournaments:
        tournament_id = tournament['id']
        tournament_name = tournament['name']
        
        # CORRECTED URL PATH: Teams are a sub-resource of a tournament, not a league.
        teams_url = f'{base_url}/tournaments/{tournament_id}/teams'
        
        try:
            teams_response = requests.get(teams_url, headers=headers)
            teams_response.raise_for_status()
            teams = teams_response.json()
            for team in teams:
                # Use a dictionary to avoid duplicate teams from multiple tournaments
                all_teams[team['id']] = team
            print(f"  -> Found {len(teams)} teams for tournament '{tournament_name}'.")
        except requests.exceptions.RequestException as e:
            # Note: The free plan may not have data for all tournaments, causing a 404
            print(f"  -> Warning: Could not fetch teams for tournament '{tournament_name}': {e}")
            continue

    if not all_teams:
        print(f"No teams found in any tournaments for '{league_name}'.")
        return

    # Convert dictionary values back to a list for saving
    teams_list = list(all_teams.values())
    
    print(f"\nFound a total of {len(teams_list)} unique teams in '{league_name}'.")

    # Step 4: Save the teams to a JSON file
    filename = f"{region_name}_{game_slug}_teams.json"
    try:
        with open(filename, 'w') as f:
            json.dump(teams_list, f, indent=4)
        print(f"Successfully saved team data to {filename}")
    except IOError as e:
        print(f"Error writing to file: {e}")

if __name__ == "__main__":
    API_KEY = os.getenv("PANDASCORE_API_KEY")

    # Get user input for the game and region
    GAME_SLUG = input("Enter the game slug (e.g., lol, cs-go): ").strip().lower()
    REGION = input("Enter the region slug (e.g., lcs, lck, lec): ").strip().lower()
    
    get_teams_from_region(API_KEY, GAME_SLUG, REGION)