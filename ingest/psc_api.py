import requests

class Psc:

    def get_user_info(request, username):
        url = 'https://info-int.psc.edu/api/graph/graphql'
        headers = {'Content-Type': 'application/json', 
                'Authorization': f'JWT eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjIwMTY4NTE3MjYsImlhdCI6MTcwMTI3NTcyNiwianRpIjoiYzhlZWFiMWUtMzcyNi00MzFhLTkyZjEtOGUyOTgxYzg2YjgyIiwic3ViIjoiYXBwL2JpbGRhdGFzdWJtaXNzaW9ucG9ydGFsIiwidHlwZSI6ImFjY2VzcyJ9.5ei2tvh2efDQ5nDi1XMLJ-hiYtpyeEk39SxU-GNLshg'}

        query = """
        query GetUserAndAllocationUsers($username: String) {
            user(username: $username) {
                name {
                    first
                    last
                }
            affiliation
            {
            organization {
                name
            }

            }
                email{
                    primary
                }
            }
            }
        """


            # GraphQL variables
        variables = {
            "username": username
        }

            # Make the API call
        response = requests.post(url, json={'query': query, 'variables': variables}, headers=headers)
        if response.status_code == 200:
            result = response.json()  # Assuming the response is in JSON format
            # Process the result as needed
            #print(result)
            return result
        else:
            # Handle the error
            print(f"Error: {response.status_code}")
            print(response.text)  # Print the response content for debugging
