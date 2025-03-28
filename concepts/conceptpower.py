import requests,json
from requests.auth import HTTPBasicAuth


class Conceptpower:

    def __init__(self, endpoint, namespace):
        """
        Initialize a Conceptpower instance.

        Args:
            endpoint (str): The base URL for the Conceptpower API.
            namespace (str): The namespace for the API.

        Raises:
            ValueError: If either 'endpoint' or 'namespace' is missing or invalid.
        """
        
        if not endpoint or not namespace:
            raise ValueError("Conceptpower endpoint and namespace are required and must be a non-empty string.")
        self.endpoint = endpoint
        self.namespace = namespace

    def search(self, params=None, headers=None):
        url = "{0}ConceptSearch".format(self.endpoint)

        response = requests.get(url, headers=headers, params=params)
        concepts = []
        if response.status_code == requests.codes.ok:
                data = response.json()
                if not data or 'conceptEntries' not in data:
                    return concepts  # Return an empty list if no concept entries exist

                for concept_entry in data.get('conceptEntries', []):
                    concepts.append(self.parse_concept(concept_entry))
                return concepts
        else:
            raise ValueError(f"Error searching Conceptpower: {response.status_code}")
        return concepts

    def get(self, uri, headers):
        url = "{0}Concept?id={1}".format(self.endpoint, uri)
        response = requests.get(url, headers=headers)
        data = {}
        if response.status_code == requests.codes.ok:
            data = response.json()
            concept_entries = data.get('conceptEntries', [])
        else:
            raise ValueError(f"Error fetching concept data: {response.status_code}")
        return concept_entries[0] if concept_entries else {}

    def create(self, user, password, label, pos, conceptlist, description,
               concepttype, synonym_ids=[], equal_to=[], similar_uris=[]):

        auth = HTTPBasicAuth(user,password)
        rest_url = "{0}concept/add".format(self.endpoint)

        concept_data = {
            "word": label,
            "pos": pos,
            "conceptlist": conceptlist,
            "description": description,
            "type": concepttype,
            "synonymids": synonym_ids,
            "equal_to": equal_to,
            "similar": similar_uris
        }

        r = requests.post(url=rest_url, data=json.dumps(concept_data), auth=auth)

        if r.status_code != requests.codes.ok:
            raise RuntimeError(r.status_code, r.text)

        # Returned data after successful response
        return r.json()
    
    def parse_concept(self,concept_entry):
        """
        Parse a concept and return a dictionary with the required fields.

        Args:
            concept_entry (dict): A dictionary representing a concept entry from the ConceptPower API. 
            Example:
            {
                "id": "CONcQyweoHkr156",
                "lemma": "kingdom",
                "pos": "NOUN",
                "description": "a domain in which something is dominant",
                "conceptList": "list1",
                "type": {
                    "type_id": "52cbe154-1ee7-4ee1-861f-67fb3c7d9511",
                    "type_uri": "http://www.digitalhps.org/types/TYPE_52cbe154-1ee7-4ee1-861f-67fb3c7d9511",
                    "type_name": "test type"
                },                
                "deleted": false,
                "concept_uri": "http://www.digitalhps.org/concepts/CONcQyweoHkr156",
                "creator_id": "user1",
                "equal_to": "",
                "modified_by": "",
                "similar_to": "",
                "synonym_ids": "",
                "wordnet_id": "WID-12504805-N-01-kingdom",
                "alternativeIds": [
                    { "concept_id": "CONcQyweoHkr156", "concept_uri": "http://www.digitalhps.org/concepts/CONcQyweoHkr156" },
                    { "concept_id": "WID-12504805-N-01-kingdom", "concept_uri": "http://www.digitalhps.org/concepts/WID-12504805-N-01-kingdom" }
                ]
            }

        Returns:
            dict: A dictionary containing the parsed concept details with the required fields. 
            Example:
            {
                "id": "CONcQyweoHkr056",
                "label": "kingdom",
                "pos": "NOUN",
                "type": {
                    "type_id": "52cbe154-1ee7-4ee1-861f-67fb3c7d9511",
                    "type_uri": "http://www.digitalhps.org/types/TYPE_52cbe154-1ee7-4ee1-861f-67fb3c7d9511",
                    "type_name": "test type"
                },
                "conceptList": "list1",
                "uri": "http://www.digitalhps.org/concepts/CONcQyweoHkr056",
                "description": "a domain in which something is dominant"
            }
        """
        concept = {}
        concept['label'] = concept_entry.get('lemma', '')
        concept['id'] = concept_entry.get('id', '')
        concept['pos'] = concept_entry.get('pos', '')
        concept['type'] = concept_entry.get('type','')
        concept['conceptList'] = concept_entry.get('conceptList', '')
        concept['uri'] = concept_entry.get('concept_uri', '')

        description = concept_entry.get('description', '')
        try:
            concept['description'] = json.loads(f'"{description}"')
        except json.JSONDecodeError:
            concept['description'] = description
        return concept