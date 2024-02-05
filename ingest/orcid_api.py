import requests


class Orcid:
    def get_orcid(first_name, last_name):
        api_key = '55277bd0-745f-4650-b5ef-7cd88cb6d893'
        base_url = 'https://pub.orcid.org/v3.0/'

        # Example: Search for ORCID iDs based on a person's name
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }

        url = f'{base_url}expanded-search/?q={first_name}+AND+{last_name}'

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Check for errors

            data = response.json()
            # Process the search results as needed
            return data

        except requests.exceptions.HTTPError as errh:
            print(f"HTTP Error: {errh}")
        except requests.exceptions.ConnectionError as errc:
            print(f"Error Connecting: {errc}")
        except requests.exceptions.Timeout as errt:
            print(f"Timeout Error: {errt}")
        except requests.exceptions.RequestException as err:
            print(f"An unexpected error occurred: {err}")
