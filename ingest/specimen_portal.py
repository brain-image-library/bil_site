import requests
import json
from django.conf import settings


class Specimen_Portal:
    def get_nhash_results(nhashid):
        jwt_token = settings.SPECIMEN_PORTAL_JWT
        headers = {'Authorization': f'Bearer {jwt_token}'}
        NHASH_URL = f'https://brain-specimenportal.org/api/v1/nhash_ids/ancestors?id_only=false&id='
        NHASH_URL = NHASH_URL + nhashid
        #print(NHASH_URL)
        try:
            response = requests.get(NHASH_URL, headers=headers)
            parsed_response = response.json()
            

    # Check if the request was successful (status code 200)
            if response.status_code == 200:
                # Process the response content here
                #print(json.dumps(parsed_response, indent=4))
                return parsed_response
            else:
                print(f"Request failed with status code {response.status_code}")

        except requests.RequestException as e:
            print(f"An error occurred: {e}")
