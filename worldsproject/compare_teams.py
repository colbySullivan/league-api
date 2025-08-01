import requests
import os
import json
from itertools import combinations
from collections import defaultdict
import time
import glob

# --- Configuration ---
# Your PandaScore API key should be set as an environment variable.
API_KEY = os.getenv("PANDASCORE_API_KEY")

if not API_KEY:
    raise ValueError("Error: PANDASCORE_API_KEY environment variable is not set. Please set it before running the script.")

BASE_URL = "https://api.pandascore.co/lol"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

# --- Ranking System Configuration ---
BASE_WIN_POINTS = 100
SERIES_MULTIPLIERS = {
    1: 1.0,  # Best-of-1
    3: 1.2,  # Best-of-3
    5: 1.5   # Best-of-5
}

# Weights for different leagues. You will need to find and add the numerical IDs.
# Higher weight for more prestigious leagues.
LEAGUE_WEIGHTS = {
    # Example IDs and weights
    # 4194: 1.5,  # LCK (Korea)
    # 4235: 1.5,  # LPL (China)
    # 4265: 1.2,  # LCS (North America)
    # 4198: 1.2,  # LEC (Europe)
}

def choose_json_file():
    """
    Asks the user to choose a JSON file from the current directory.
    
    Returns:
        str: The path to the selected file, or None if the user cancels or no files are found.
    """
    json_files = glob.glob("*.json")
    if not json_files:
        print("No JSON files found in the current directory.")
        return None

    print("Please choose a JSON file to load the teams from:")
    for i, file in enumerate(json_files):
        print(f"[{i+1}] {file}")

    while True:
        try:
            choice = input("Enter the number of your choice: ")
            if not choice:
                print("Selection cancelled.")
                return None
            
            index = int(choice) - 1
            if 0 <= index < len(json_files):
                return json_files[index]
            else:
                print("Invalid choice. Please enter a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def load_teams_from_json(file_path):
    """
    Loads team names and IDs from a JSON file.
    """
    try:
        with open(file_path, 'r') as f:
            teams_data = json.load(f)
            if not teams_data or len(teams_data) < 2:
                print(f"Error: Not enough teams in '{file_path}' to compare. Please add at least two teams.")
                return None
            return teams_data
    except FileNotFoundError:
        print(f"Error: '{file_path}' not found. The file may have been moved or deleted.")
        return None
    except json.JSONDecodeError:
        print(f"Error: '{file_path}' is empty or corrupted. Please check the file.")
        return None

def fetch_matches_for_pair(team1_id, team2_id, team_id_name_map):
    """
    Fetches all head-to-head matches between two specific teams.
    
    Args:
        team1_id (int): ID of the first team.
        team2_id (int): ID of the second team.
        team_id_name_map (dict): A map from team IDs to team names.
        
    Returns:
        list: A list of match data or an empty list on failure.
    """
    endpoint = "/matches"
    params = {
        "filter[opponent_id]": f"{team1_id},{team2_id}",
        "sort": "-end_at",
        "per_page": 50,
        "include": "opponents,winner,games,league"
    }
    
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params)
        response.raise_for_status()
        matches_between_pair = response.json()
        
        filtered_matches = [
            match for match in matches_between_pair
            if any(opp['opponent']['id'] == team1_id for opp in match.get('opponents', []))
            and any(opp['opponent']['id'] == team2_id for opp in match.get('opponents', []))
        ]
        
        if filtered_matches:
            print(f"Found {len(filtered_matches)} matches between {team_id_name_map[team1_id]} and {team_id_name_map[team2_id]}.")
        
        return filtered_matches
    except requests.exceptions.RequestException as e:
        print(f"Error fetching matches between teams '{team_id_name_map[team1_id]}' and '{team_id_name_map[team2_id]}': {e}")
        return []

def get_all_head_to_head_matches(teams):
    """
    Fetches all head-to-head matches for every unique pair of teams.
    """
    team_ids = [team['id'] for team in teams.values()]
    team_id_name_map = {team['id']: name for name, team in teams.items()}
    all_matches = []
    
    team_pairs = list(combinations(team_ids, 2))
    print(f"Fetching matches for {len(team_pairs)} unique team pairs...")

    for team1_id, team2_id in team_pairs:
        matches_for_pair = fetch_matches_for_pair(team1_id, team2_id, team_id_name_map)
        all_matches.extend(matches_for_pair)
        time.sleep(1) 
            
    return all_matches, team_id_name_map

def calculate_weighted_rankings(matches, team_id_name_map):
    """
    Calculates weighted rankings based on winrate, series length, league prestige,
    and a new normalized points per game metric.
    """
    ranking_data = defaultdict(lambda: {"wins": 0, "losses": 0, "points": 0, "name": "", "total_games": 0, "normalized_points": 0})
    
    for team_id, team_name in team_id_name_map.items():
        ranking_data[team_id]["name"] = team_name

    # First pass: Calculate initial wins, losses, and total games to determine winrates
    for match in matches:
        winner = match.get('winner')
        if winner and 'id' in winner:
            winner_id = winner['id']
            opponents = [opp['opponent']['id'] for opp in match.get('opponents', []) if 'opponent' in opp and 'id' in opp['opponent']]
            loser_id = next((opp_id for opp_id in opponents if opp_id != winner_id), None)
            
            if winner_id in ranking_data:
                ranking_data[winner_id]["wins"] += 1
            if loser_id in ranking_data:
                ranking_data[loser_id]["losses"] += 1
        
        # Calculate total games played by each team
        games = match.get('games', [])
        num_games = len(games)
        if len(opponents) == 2:
            team1_id, team2_id = opponents
            if team1_id in ranking_data:
                ranking_data[team1_id]["total_games"] += num_games
            if team2_id in ranking_data:
                ranking_data[team2_id]["total_games"] += num_games

    # Calculate winrates for all teams
    winrates = {}
    for team_id, data in ranking_data.items():
        total_matches = data["wins"] + data["losses"]
        winrates[team_id] = data["wins"] / total_matches if total_matches > 0 else 0
        
    # Second pass: Award points with weighting
    for match in matches:
        winner = match.get('winner')
        if winner and 'id' in winner:
            winner_id = winner['id']
            opponents = [opp['opponent']['id'] for opp in match.get('opponents', []) if 'opponent' in opp and 'id' in opp['opponent']]
            loser_id = next((opp_id for opp_id in opponents if opp_id != winner_id), None)
            
            if winner_id and loser_id:
                # --- League Weighting ---
                league_id = match.get('league', {}).get('id')
                league_multiplier = LEAGUE_WEIGHTS.get(league_id, 1.0)
                
                # --- Series Length Weighting ---
                games = match.get('games', [])
                num_games = len(games)
                series_multiplier = SERIES_MULTIPLIERS.get(num_games, 1.0)

                # --- Winrate Weighting (Upset Bonus) ---
                winner_winrate = winrates.get(winner_id, 0)
                loser_winrate = winrates.get(loser_id, 0)
                
                winrate_multiplier = 1.0
                if winner_winrate < loser_winrate:
                    winrate_multiplier = 1.0 + (loser_winrate - winner_winrate)
                
                points_awarded = BASE_WIN_POINTS * series_multiplier * winrate_multiplier * league_multiplier
                ranking_data[winner_id]["points"] += points_awarded
                
    # Final pass: Calculate normalized points
    for team_id, data in ranking_data.items():
        if data["total_games"] > 0:
            ranking_data[team_id]["normalized_points"] = data["points"] / data["total_games"]
                
    ranked_list = list(ranking_data.values())
    ranked_list.sort(key=lambda x: x["normalized_points"], reverse=True)
    
    return ranked_list

def calculate_head_to_head_records(matches):
    """
    Calculates and returns the total head-to-head match win/loss record for each pair.
    """
    h2h_records = defaultdict(lambda: defaultdict(int))

    for match in matches:
        winner = match.get('winner')
        if winner and 'id' in winner:
            winner_id = winner['id']
            opponents = [opp['opponent']['id'] for opp in match.get('opponents', []) if 'opponent' in opp and 'id' in opp['opponent']]
            loser_id = next((opp_id for opp_id in opponents if opp_id != winner_id), None)

            if winner_id and loser_id:
                pair_key = tuple(sorted((winner_id, loser_id)))
                h2h_records[pair_key][winner_id] += 1
                h2h_records[pair_key][loser_id] += 0
    
    return h2h_records

def format_weighted_rankings(ranked_teams):
    """
    Formats the weighted rankings into a single string.
    """
    output = ["--- Team Rankings (Normalized Points) ---",
              "{:<5} {:<20} {:<10} {:<10} {:<10} {:<15}".format("Rank", "Team", "Wins", "Losses", "Games", "Normalized Points"),
              "-" * 75]
    
    for i, team in enumerate(ranked_teams, 1):
        output.append("{:<5} {:<20} {:<10} {:<10} {:<10} {:<15.2f}".format(
            i,
            team['name'],
            team['wins'],
            team['losses'],
            team['total_games'],
            team['normalized_points']
        ))
    return "\n".join(output)

def format_head_to_head_records(h2h_records, team_id_name_map):
    """
    Formats the head-to-head records into a single string.
    """
    output = ["\n--- Head-to-Head Breakdown ---"]
    
    for pair, record in h2h_records.items():
        team1_id, team2_id = pair
        team1_name = team_id_name_map.get(team1_id, "Unknown")
        team2_name = team_id_name_map.get(team2_id, "Unknown")
        
        team1_wins = record.get(team1_id, 0)
        team2_wins = record.get(team2_id, 0)
        
        if team1_wins + team2_wins > 0:
            output.append(f"\n{team1_name} vs. {team2_name}: {team1_wins}-{team2_wins}")
    
    return "\n".join(output)

def main():
    """
    Main function to orchestrate the team ranking process.
    """
    try:
        file_path = choose_json_file()
        if not file_path:
            return

        teams = load_teams_from_json(file_path)
        if not teams:
            return
            
        print(f"Loaded {len(teams)} teams from '{file_path}'.")
        
        matches, team_id_name_map = get_all_head_to_head_matches(teams)
        
        if not matches:
            print("\nNo head-to-head matches found for the listed teams. Exiting.")
            return
            
        ranked_teams = calculate_weighted_rankings(matches, team_id_name_map)
        ranking_output = format_weighted_rankings(ranked_teams)
        
        h2h_records = calculate_head_to_head_records(matches)
        h2h_output = format_head_to_head_records(h2h_records, team_id_name_map)

        # Print all output to the console
        print(ranking_output)
        print(h2h_output)
        
        # Ask the user if they want to save the results
        save_choice = input("\nDo you want to save the results to a text file? (y/n): ").lower()
        if save_choice == 'y':
            filename = input("Enter the filename to save as (e.g., 'rankings.txt'): ")
            
            # Use a default filename if the user doesn't provide one
            if not filename:
                filename = "lol_rankings_results.txt"
                print(f"Using default filename: '{filename}'")
            
            full_output = ranking_output + "\n" + h2h_output
            
            try:
                with open(filename, 'w') as f:
                    f.write(full_output)
                print(f"\nResults successfully saved to '{filename}'.")
            except IOError as e:
                print(f"\nError: Could not save file to '{filename}'. Reason: {e}")
        else:
            print("\nResults not saved. Exiting.")


    except ValueError as e:
        print(e)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()