import requests
import json

#nhashid = 'TI-UIJT835396'
local_name = 'BEB22101'
lab_name = ''
#NHASH_URL = f'https://brain-specimenportal.org/api/v1/nhash_ids/stats'

#NHASH_URL = 'https://brain-specimenportal.org/api/v1/nhash_ids/info?id=DO-CYPH5324'

NHASH_URL = f'https://brain-specimenportal.org/api/v1/nhash_ids/ancestors?id='
#LOCAL_URL = f'https://brain-specimenportal.org/api/v1/nhash_ids/nemo?type:TYPE&amp;name={local_name}&amp;lab={lab_name}&amp;format=csv'
#TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxMjIsImV4cCI6MTcwNTY5NDUxNn0.qVNiYKUOPw2nwIEtalF4405Q5vw9G8BEyOQsdNgzo8c'  # Replace
jwt_token = 'eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxMjIsImV4cCI6MTcxMTQ5ODY4N30.K_oBnrip244Fch38wLHMbqwMpK-G8gd9vupPhpKPhEc'
headers = {
    'Authorization': f'Bearer {jwt_token}'
}

class Specimen_Portal:
    def get_nhash_results(nhashid):
        jwt_token = 'eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxMjIsImV4cCI6MTcxMjAxODA2M30.UBvuErPozugxvCX95ZCGF8ndbqDxEtn6P3VQiW1ZpW0'
        headers = {'Authorization': f'Bearer {jwt_token}'}
        NHASH_URL = f'https://brain-specimenportal.org/api/v1/nhash_ids/ancestors?id='
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
