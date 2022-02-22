import json
import requests

from typing import Dict


class APIClient():
    """
    Implements a *very* simplified client to make API calls to GitHub.
    """
    def __init__(self, github_token: str):
        self.base_url = 'https://api.github.com'
        self.github_token = github_token
        self.headers = {'Authorization': f'token {github_token}'}


    def get(self, url: str) -> Dict:
        """
        Makes a GET API call to the GitHub API.

        Returns the response as a dictionary.
        """
        response = requests.get(f"{self.base_url}{url}",
                                headers=self.headers)
        return json.loads(response.content)


    def put(self, url: str, data: Dict) -> Dict:
        """
        Makes a PUT API call to the GitHub API.

        Returns the response as a dictionary.
        """
        response = requests.put(f"{self.base_url}{url}",
                                json=data,
                                headers=self.headers)
        return json.loads(response.content)


    def post(self, url: str, data: Dict) -> Dict:
        """
        Makes a POST API call to the GitHub API.

        Returns the response as a dictionary.
        """
        response = requests.post(f"{self.base_url}{url}",
                                 json=data,
                                 headers=self.headers)
        return json.loads(response.content)
