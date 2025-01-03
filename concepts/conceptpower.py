import requests,json
import xml.etree.ElementTree as ET
from requests.auth import HTTPBasicAuth


class Conceptpower:
    # Default behavior is to leave these to the constructor.
    endpoint = None
    namespace = None

    def __init__(self, **kwargs):
        # Give first priority to the class definition, if endpoint or namespace are defined (and not None).
        if self.endpoint is None:
            self.endpoint = kwargs.get(
                "endpoint", "http://chps.asu.edu/conceptpower/rest/")

        if self.namespace is None:
            self.namespace = kwargs.get(
               "namespace", "{http://www.digitalhps.org/}")

    def search(self, params=None, headers=None):
        url = "{0}ConceptSearch".format(self.endpoint)

        response = requests.get(url, headers=headers, params=params)
        concepts = []
        if response.status_code == 200:
                data = response.json()
                if 'conceptEntries' in data:
                    for concept_entry in data['conceptEntries']:
                        concept = self.parse_concept(concept_entry)
                        concepts.append(concept)
        return concepts

    def get(self, uri, headers):
        url = "{0}Concept?id={1}".format(self.endpoint, uri)
        response = requests.get(url, headers=headers)
        data = {}
        if response.status_code == 200:
            data = response.json()
            concept_entry = data.get('conceptEntries', [{}])[0]
        else:
            raise ValueError(f"Error fetching concept data: {response.status_code}")
        return concept_entry

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